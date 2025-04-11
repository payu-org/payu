# coding: utf-8
"""
The payu interface for the ACCESS coupled climate model
-------------------------------------------------------------------------------
Contact: Marshall Ward <marshall.ward@anu.edu.au>
-------------------------------------------------------------------------------
Distributed as part of Payu, Copyright 2011 Marshall Ward
Licensed under the Apache License, Version 2.0
http://www.apache.org/licenses/LICENSE-2.0
"""
from __future__ import print_function

# Standard Library
import os
import re
import shutil

# Extensions
import f90nml
from netCDF4 import Dataset
from datetime import date, timedelta

# Local
from payu.fsops import make_symlink
from payu.models.model import Model
import payu.calendar as cal

INIT_DATE = 10101 #aka 0001/01/01

class AccessEsm1p6(Model):

    def __init__(self, expt, name, config):
        super(AccessEsm1p6, self).__init__(expt, name, config)

        self.model_type = 'access-esm1.6'

        for model in self.expt.models:
            if model.model_type == 'cice':
                raise RuntimeError(
                    "cice submodel not supported in access-esm1.6 model,"
                    " either use cice5 submodel or access model"
                )

            if model.model_type == 'cice5':
                model.config_files = ['cice_in.nml',
                                      'input_ice.nml']

                model.ice_nml_fname = 'cice_in.nml'

                model.access_restarts = ['mice.nc']
                model.copy_restarts = True 

                model.set_timestep = model.set_access_timestep

                # Structure of model coupling namelist
                model.cpl_fname = 'input_ice.nml'
                model.cpl_group = 'coupling'
                # model.start_date_nml_name = "restart_date.nml"
                # Experiment initialisation date
                model.init_date_key = "init_date"
                # Start date for new run
                model.inidate_key = "inidate"
                # Total time in seconds since initialisation date
                model.runtime0_key = 'runtime0'
                # Simulation length in seconds for new run
                model.runtime_key = "runtime"

            if model.model_type == 'um':
                # Additional Cable 3 namelists

                # Using set as this initialised twice and would otherwise
                # contain duplicates
                model.optional_config_files = list(
                    set(['pft_params.nml', 'soil.nml']) |
                    set(model.optional_config_files)
                )

    def setup(self):
        if not self.top_level_model:
            return

        # Keep track of this in order to set the oasis runtime.
        run_runtime = 0

        for model in self.expt.models:

            if model.model_type == 'cice5':

                # Horrible hack to make a link to o2i.nc in the
                # work/ice/RESTART directory
                f_name = 'o2i.nc'
                f_src = os.path.join(model.work_path, f_name)
                f_dst = os.path.join(model.work_restart_path, f_name)

                if os.path.isfile(f_src):
                    make_symlink(f_src, f_dst)

                # Stage the supplemental input files
                if model.prior_restart_path:
                    for f_name in model.access_restarts:
                        f_src = os.path.join(model.prior_restart_path, f_name)
                        f_dst = os.path.join(model.work_input_path, f_name)

                        if os.path.isfile(f_src):
                            make_symlink(f_src, f_dst)

                # Update the supplemental OASIS namelists
                # cpl_nml is the coupling namelist copied from the control to
                # work directory.
                cpl_fpath = os.path.join(model.work_path, model.cpl_fname)
                cpl_nml = f90nml.read(cpl_fpath)
                cpl_group = cpl_nml[model.cpl_group]

                # Which calendar are we using, noleap or Gregorian.
                caltype = cpl_group['caltype']

                # Experiment initialisation date
                init_date = cal.int_to_date(INIT_DATE)

                # Get timing information for the new run.
                if model.prior_restart_path and not self.expt.repeat_run:

                    # Read the start date from last the restart
                    iced_file = model.get_latest_restart_file()
                    iced_nc = Dataset(os.path.join(model.prior_restart_path, iced_file))
                    run_start_date = date(
                        iced_nc.getncattr('nyr'),
                        iced_nc.getncattr('month'),
                        iced_nc.getncattr('mday')
                    ) + timedelta(seconds=float(iced_nc.getncattr('sec')))
                    iced_nc.close()

                    # run_start_date must be after initialisation date
                    if run_start_date < init_date:
                        msg = (
                            f"Restart date in {iced_file} must not be "
                            "before initialisation date {INIT_DATE}. "
                        )
                        raise ValueError(msg)

                    # Calculate the total number of seconds between the
                    # initialisation and new run start date,
                    # to use for the runtime0 field.
                    previous_runtime = cal.seconds_between_dates(
                        init_date,
                        run_start_date,
                        caltype
                    )

                else:
                    previous_runtime = 0
                    # TO-DO: user configurable start date
                    # e.g. cpl_group[model.inidate_key] or the start date in `config.yaml`
                    run_start_date = init_date

                # Get new runtime for this run. We get this from either the
                # 'runtime' part of the payu config, or from the namelist
                if self.expt.runtime:
                    run_runtime = cal.runtime_from_date(
                        run_start_date,
                        self.expt.runtime['years'],
                        self.expt.runtime['months'],
                        self.expt.runtime['days'],
                        self.expt.runtime.get('seconds', 0),
                        caltype)
                else:
                    run_runtime = cpl_group[model.runtime_key]

                # Now write out new run start date and total runtime into the
                # work directory namelist.
                cpl_group[model.init_date_key] = cal.date_to_int(init_date)
                cpl_group[model.inidate_key] = cal.date_to_int(run_start_date)
                cpl_group[model.runtime0_key] = previous_runtime
                cpl_group[model.runtime_key] = int(run_runtime)

                # TO-DO : what is this for, should this be getting written to input_ice?
                if self.expt.counter and not self.expt.repeat_run:
                    cpl_group['jobnum'] = (
                        1 + self.expt.counter
                    )
                else:
                    cpl_group['jobnum'] = 1

                # write coupler namelist
                nml_work_path = os.path.join(model.work_path, model.cpl_fname)

                # TODO: Does this need to be split into two steps?
                f90nml.write(cpl_nml, nml_work_path + '~')
                shutil.move(nml_work_path + '~', nml_work_path)

        if run_runtime == 0:
            raise Error()


        # Now change the oasis runtime. This needs to be done after the others.
        for model in self.expt.models:
            if model.model_type == 'oasis':
                namcouple = os.path.join(model.work_path, 'namcouple')

                s = ''
                with open(namcouple, 'r+') as f:
                    s = f.read()
                    m = re.search(r"^[ \t]*\$RUNTIME.*?^[ \t]*(\d+)", s,
                                  re.MULTILINE | re.DOTALL)
                    assert (m is not None)
                    s = s[:m.start(1)] + str(run_runtime) + s[m.end(1):]

                with open(namcouple, 'w') as f:
                    f.write(s)

    def archive(self):
        if not self.top_level_model:
            return

        for model in self.expt.models:
            if model.model_type == 'cice5':

                # Copy supplemental restart files to RESTART path
                for f_name in model.access_restarts:
                    f_src = os.path.join(model.work_path, f_name)
                    f_dst = os.path.join(model.restart_path, f_name)

                    if os.path.exists(f_src):
                        shutil.move(f_src, f_dst)

                # Copy "cice_in.nml" from work path to restart.
                work_ice_nml_path = os.path.join(
                                        model.work_path,
                                        model.ice_nml_fname
                )
                restart_ice_nml_path = os.path.join(
                                        model.restart_path,
                                        model.ice_nml_fname
                )

                if os.path.exists(work_ice_nml_path):
                    shutil.copy2(work_ice_nml_path, restart_ice_nml_path)


    def get_restart_datetime(self, restart_path):
        """Given a restart path, parse the restart files and
        return a cftime datetime (for date-based restart pruning)"""

        # Use mom by default and um if ocean not present
        model_types = ['mom', 'um']

        return self.get_restart_datetime_using_submodel(restart_path,
                                                        model_types)

    def set_model_pathnames(self):
        pass

    def set_local_pathnames(self):
        pass

    def set_input_paths(self):
        pass

    def set_model_output_paths(self):
        pass

    def collate(self):
        pass
