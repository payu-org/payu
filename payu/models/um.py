"""payu.models.um
   ==============

   The payu interface for the UM atmosphere model

   :copyright: Copyright 2011 Marshall Ward, see AUTHORS for details
   :license: Apache License, Version 2.0, see LICENSE for details
"""
from __future__ import print_function

# Standard Library
import datetime
import fileinput
import glob
import os
import shutil
import string

# Extensions
import f90nml
import yaml

# Local
from payu.fsops import mkdir_p, make_symlink
from payu.models.model import Model
import payu.calendar as cal


class UnifiedModel(Model):

    def __init__(self, expt, name, config):
        super(UnifiedModel, self).__init__(expt, name, config)

        self.model_type = 'um'
        self.default_exec = 'um'
        self.restart_calendar_file = self.model_type + '.res.yaml'

        # TODO: many of these can probably be ignored.
        self.config_files = [
            'errflag',
            'hnlist', 'ihist',
            'namelists', 'prefix.PRESM_A',
            'STASHC', 'UAFILES_A', 'UAFLDS_A',
            'cable.nml', 'um_env.yaml'
            ]
        self.optional_config_files.extend(['input_atm.nml', 'parexe'])

        self.restart = 'restart_dump.astart'

    def set_model_pathnames(self):
        super(UnifiedModel, self).set_model_pathnames()

        self.work_input_path = os.path.join(self.work_path, 'INPUT')

    def archive(self):
        super(UnifiedModel, self).archive()

        # Delete all the stdout log files except the root PE
        # Sorts to ensure root PE is first entry
        files = sorted(glob.glob(
                       os.path.join(self.work_path, 'atm.fort6.pe*')),
                       key=lambda name: int(name.rpartition('.')[-1][2:]))
        if len(files) > 1:
            for f_path in files[1:]:
                os.remove(f_path)

        mkdir_p(self.restart_path)

        # Need to figure out the end date of the model.
        nml_path = os.path.join(self.work_path, 'namelists')
        nml = f90nml.read(nml_path)

        resubmit_inc = nml['NLSTCALL']['RUN_RESUBMIT_INC']
        runtime = um_time_to_time(resubmit_inc)
        # runtime = datetime.timedelta(seconds=runtime)

        basis_time = nml['NLSTCALL']['MODEL_BASIS_TIME']
        init_date = um_date_to_date(basis_time)

        end_date = cal.date_plus_seconds(init_date,
                                         runtime,
                                         cal.GREGORIAN)

        # Save model time to restart next run
        with open(os.path.join(self.restart_path,
                  self.restart_calendar_file), 'w') as restart_file:
            restart_file.write(yaml.dump({'end_date': end_date},
                               default_flow_style=False))

        end_date = date_to_um_dump_date(end_date)

        restart_dump = os.path.join(self.work_path,
                                    'aiihca.da{0}'.format(end_date))
        f_dst = os.path.join(self.restart_path, self.restart)
        if os.path.exists(restart_dump):
            shutil.copy(restart_dump, f_dst)
        else:
            print('payu: error: Model has not produced a restart dump file:\n'
                  '{} does not exist.\n'
                  'Check DUMPFREQim in namelists'.format(restart_dump))

        # Now remove restart files from work directory so they're not
        # unnecessarily archived to output
        for f_path in glob.glob(os.path.join(self.work_path, 'aiihca.da*')):
            os.remove(f_path)

    def collate(self):
        pass

    def setup(self):
        # Raise a deprecation error if the um_env.yaml file is not found
        # This could be removed down the line, once older configurations 
        # have swapped to um_env.yaml files.
        deprecated_um_env = os.path.join(self.control_path, 'um_env.py')
        new_um_env = os.path.join(self.control_path, 'um_env.yaml')
        if (not os.path.isfile(new_um_env)) and os.path.isfile(deprecated_um_env):
            raise RuntimeError(
                (
                    "The `um_env.py` configuration file is no longer "
                    "supported and should be replaced with a yaml file. "
                    "Convert `um_env.py` to `um_env.yaml` using "
                    "https://github.com/ACCESS-NRI/esm1.5-scripts/blob/main/config-files/UM/um_env_to_yaml.py"
                )
            ) 

        # Commence normal setup
        super(UnifiedModel, self).setup()

        # Set up environment variables needed to run UM.
        um_env_path = os.path.join(self.control_path, 'um_env.yaml')
        with open(um_env_path, 'r') as um_env_yaml:
            um_env_vars = yaml.safe_load(um_env_yaml)


        # Stage the UM restart file.
        if self.prior_restart_path and not self.expt.repeat_run:
            f_src = os.path.join(self.prior_restart_path, self.restart)
            f_dst = os.path.join(self.work_input_path, self.restart)

            if os.path.isfile(f_src):
                make_symlink(f_src, f_dst)
                # every run is an NRUN with an updated ASTART file
                um_env_vars['ASTART'] = self.restart
                um_env_vars['TYPE'] = 'NRUN'

        # Set paths in environment variables.
        for k in um_env_vars.keys():
            um_env_vars[k] = um_env_vars[k].format(
                                    input_path=self.input_paths[0],
                                    work_path=self.work_path
            )
        os.environ.update(um_env_vars)

        # parexe removed from newer configurations - retain the
        # old processing if parexe file exists for backwards compatibility
        parexe = os.path.join(self.work_path, 'parexe')
        if os.path.isfile(parexe):
            # The above needs to be done in parexe also.
            # FIXME: a better way to do this or remove.
            for line in fileinput.input(parexe, inplace=True):
                line = line.format(input_path=self.input_paths[0],
                                   work_path=self.work_path)
                print(line, end='')


        work_nml_path = os.path.join(self.work_path, 'namelists')
        work_nml = f90nml.read(work_nml_path)

        restart_calendar_path = os.path.join(self.work_init_path,
                                             self.restart_calendar_file)

        # Modify namelists for a continuation run.
        if self.prior_restart_path and not self.expt.repeat_run \
           and os.path.exists(restart_calendar_path):

            run_start_date = self.read_calendar_file(restart_calendar_path)

            # Write out and save new calendar information.
            run_start_date_um = date_to_um_date(run_start_date)
            work_nml['NLSTCALL']['MODEL_BASIS_TIME'] = run_start_date_um
            work_nml['NLSTCALL']['ANCIL_REFTIME'] = run_start_date_um

        else:
            run_start_date = work_nml['NLSTCALL']['MODEL_BASIS_TIME']
            run_start_date = um_date_to_date(run_start_date)

        # Set the runtime for this run.
        if self.expt.runtime:
            run_runtime = cal.runtime_from_date(
                run_start_date,
                self.expt.runtime['years'],
                self.expt.runtime['months'],
                self.expt.runtime['days'],
                self.expt.runtime.get('seconds', 0),
                cal.GREGORIAN)
            run_runtime = time_to_um_time(run_runtime)
            work_nml['NLSTCALL']['RUN_RESUBMIT_INC'] = run_runtime
            work_nml['NLSTCALL']['RUN_TARGET_END'] = run_runtime
            work_nml['STSHCOMP']['RUN_TARGET_END'] = run_runtime

        work_nml.write(work_nml_path, force=True)

    def read_calendar_file(self, restart_calendar_path):
        """
        Read date from a restart calendar file

        Parameters
        ----------
        restart_calendar_path: Path to restart calendar file

        Returns
        -------
        datetime.datetime or datetime.date
        """
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

    def get_restart_datetime(self, restart_path):
        """
        Given a restart path, parse the restart files and
        return a cftime datetime (for date-based restart pruning)

        Parameters
        ----------
        restart_path: Path to UM restart directory

        Returns
        -------
        cftime.datetime object
        """
        calendar_path = os.path.join(restart_path,
                                     self.restart_calendar_file)

        restart_date = self.read_calendar_file(calendar_path)

        # Date-based restart pruning requires cftime.datetime object and
        # Payu UM always uses proleptic Gregorian calendar
        return cal.date_to_cftime(restart_date, "proleptic_gregorian")


def date_to_um_dump_date(date):
    """
    Convert a time date object to a um dump format date which is
    <decade><year><month><day>0

    To accommodate two digit months and days the UM uses letters. e.g. 1st oct
    is writing 01a10.
    """

    assert(date.month <= 12)

    decade = date.year // 10
    # UM can only handle 36 decades then goes back to the beginning.
    decade = decade % 36
    year = date.year % 10
    month = date.month
    day = date.day

    um_d = string.digits + string.ascii_letters[:26]

    um_dump_date = (
        '{decade}{year}{month}{day}0'.format(
            decade=um_d[decade],
            year=um_d[year],
            month=um_d[month],
            day=um_d[day]
        )
    )
    return um_dump_date


def date_to_um_date(date):
    """
    Convert a date object to 'year, month, day, hour, minute, second.'
    """

    assert date.hour == 0 and date.minute == 0 and date.second == 0

    return [date.year, date.month, date.day, 0, 0, 0]


def um_date_to_date(d):
    """
    Convert a string with format 'year, month, day, hour, minute, second'
    to a datetime date.
    """

    return datetime.datetime(year=d[0], month=d[1], day=d[2],
                             hour=d[3], minute=d[4], second=d[5])


def um_time_to_time(d):
    """
    Convert a list with format [year, month, day, hour, minute, second]
    to a number of seconds.

    Only days are supported.
    """

    assert d[0] == 0 and d[1] == 0 and d[3] == 0 and d[4] == 0 and d[5] == 0

    return d[2]*86400


def time_to_um_time(seconds):
    """
    Convert a number of seconds to a list with format [year, month, day, hour,
       minute, second]

    Only days are supported.
    """

    assert(seconds % 86400 == 0)

    return [0, 0, seconds // 86400, 0, 0, 0]
