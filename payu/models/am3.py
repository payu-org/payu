"""payu.models.cable
   ================

   Driver interface to AM3

   :copyright: Copyright 2021 Marshall Ward, see AUTHORS for details
   :license: Apache License, Version 2.0, see LICENSE for details
"""

import os
import shutil

import cftime
import datetime
import f90nml
import glob
import yaml

# Local
from payu.models.model import Model
from payu.models.um import um_time_to_time, time_to_um_time, date_to_um_date
from payu.fsops import make_symlink


class Am3(Model):

    def __init__(self, expt, name, config):
        super(Am3, self).__init__(expt, name, config)

        self.model_type = 'access-am3'

        self.config_files = [
            "ATMOSCNTL", "IDEALISE", "IOSCNTL", "RECONA", "SHARED",
            "SIZES", "STASHC", "STASHmaster_A", "um_env.yaml"
        ]

        # UM runid used for naming outputs
        self.restart = "restart_dump.astart"
        self.restart_calendar_file = "am3.res.yaml"

    def set_model_pathnames(self):
        super(Am3, self).set_model_pathnames()

        self.work_input_path = os.path.join(self.work_path, 'INPUT')

        self.work_restart_path = os.path.join(self.work_path, 'RESTART')
        # self.restart_calendar_file = self.model_type + '.res.yaml'
        # self.restart_calendar_path = os.path.join(self.work_init_path,
        #                                           self.restart_calendar_file)

        # self.cable_nml_path = os.path.join(self.work_path,
        #                                    self.cable_nml_fname)

    def _get_runid(self):
        um_env_path = os.path.join(self.control_path, 'um_env.yaml')
        with open(um_env_path, 'r') as um_env_yaml:
            um_env_vars = yaml.safe_load(um_env_yaml)

        runid = um_env_vars["RUNID"]
        return runid

    def setup(self):
        super(Am3, self).setup()

        # Set up environment variables needed to run UM.
        um_env_path = os.path.join(self.control_path, 'um_env.yaml')
        with open(um_env_path, 'r') as um_env_yaml:
            um_env_vars = yaml.safe_load(um_env_yaml)

        os.environ.update(um_env_vars)

        if not self.prior_restart_path:
            raise RuntimeError("AM3 requires prior_restart_path to be set")

        # Stage the UM restart file.
        f_src = os.path.join(self.prior_restart_path, self.restart)
        f_dst = os.path.join(self.work_input_path, self.restart)

        if os.path.isfile(f_src):
            make_symlink(f_src, f_dst)

        work_shared_nml_path = os.path.join(self.work_path, 'SHARED')
        shared_nml = f90nml.read(work_shared_nml_path)

        restart_calendar_path = os.path.join(self.work_init_path,
                                             self.restart_calendar_file)

        # Modify namelists for a continuation run.
        if os.path.exists(restart_calendar_path):
            run_start_date = self.read_calendar_file(restart_calendar_path)
            # Write out and save new calendar information.
            run_start_date_um = date_to_um_date(run_start_date)
            shared_nml['NLSTCALL']['MODEL_BASIS_TIME'] = run_start_date_um
            shared_nml['NLSTCALL']['ANCIL_REFTIME'] = run_start_date_um

        else:
            raise FileNotFoundError(f"Cannot find restart date file {restart_calendar_path}")

        # Set the runtime for this run.
        if self.expt.runtime:
            run_runtime = runtime_360(
                self.expt.runtime['years'],
                self.expt.runtime['months'],
                self.expt.runtime['days'],
                self.expt.runtime.get('seconds', 0),
            )
            run_runtime = time_to_um_time(run_runtime)
            shared_nml['NLSTCALL']['RUN_TARGET_END'] = run_runtime

        shared_nml.write(work_shared_nml_path, force=True)

    def archive(self, **kwargs):
        super(Am3, self).archive()
        # run.da19820201_00

        # Delete all the stdout log files except the root PE
        # Sorts to ensure root PE is first entry
        # files = sorted(glob.glob(
        #                os.path.join(self.work_path, 'atm.fort6.pe*')),
        #                key=lambda name: int(name.rpartition('.')[-1][2:]))
        # if len(files) > 1:
        #     for f_path in files[1:]:
        #         os.remove(f_path)

        os.makedirs(self.restart_path, exist_ok=True)

        # Need to figure out the end date of the model.
        shared_nml_path = os.path.join(self.work_path, 'SHARED')
        nml = f90nml.read(shared_nml_path)

        basis_time = nml['NLSTCALL']['MODEL_BASIS_TIME']
        init_date = cftime.datetime(*basis_time, calendar="360_day")

        target_end = nml['NLSTCALL']['RUN_TARGET_END']
        runtime_seconds = um_time_to_time(target_end)

        end_date = init_date + datetime.timedelta(seconds=runtime_seconds)

        # yaml.dump requires a datetime rather than cftime object
        end_date_dt = datetime.datetime(end_date.year,
                                        end_date.month,
                                        end_date.day,
                                        end_date.hour,
                                        end_date.minute,
                                        end_date.second)

        # Save model time to restart next run
        with open(os.path.join(self.restart_path,
                  self.restart_calendar_file), 'w') as restart_file:
            restart_file.write(yaml.dump({'end_date': end_date_dt},
                               default_flow_style=False))

        # Not sure whether this is always correct
        end_date_str = end_date.strftime("%Y%m%d")
        runid = self._get_runid()
        restart_dump = os.path.join(self.work_path,
                                    f'{runid}.da{end_date_str}_00')

        f_dst = os.path.join(self.restart_path, self.restart)
        if os.path.exists(restart_dump):
            shutil.copy(restart_dump, f_dst)
        else:
            print('payu: error: Model has not produced a restart dump file:\n'
                  '{} does not exist.\n'
                  'Check DUMPFREQim in namelists'.format(restart_dump))

        # Now remove restart files from work directory so they're not
        # unnecessarily archived to output
        for f_path in glob.glob(os.path.join(self.work_path, f'{runid}.da*')):
            os.remove(f_path)

    def collate(self):
        pass

    def read_calendar_file(self, restart_calendar_path):
        """Read date from a restart calendar file"""
        if not os.path.exists(restart_calendar_path):
            raise FileNotFoundError(
                f"Cannot find restart calendar file {restart_calendar_path}."
            )

        with open(restart_calendar_path, 'r') as calendar_file:
            date_info = yaml.safe_load(calendar_file)

        restart_date = date_info['end_date']
        if not isinstance(restart_date, datetime.date):
            raise TypeError(
                "Failed to parse restart calendar file contents into "
                "datetime object. "
                f"Calendar file: {restart_calendar_path}"
            )

        return restart_date


def runtime_360(years, months, days, seconds):
    return (years*360 + months*30 + days)*86400 + seconds
