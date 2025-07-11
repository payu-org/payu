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
import sys

# Extensions
import f90nml
from datetime import date, timedelta, datetime

# Local
from payu.fsops import make_symlink
from payu.models.model import Model
import payu.calendar as cal

INIT_DATE = 10101 #aka 0001/01/01
# this is the reference date for time calculations in CICE5, 
# see https://github.com/ACCESS-NRI/cice5/issues/25

class AccessEsm1p6(Model):

    def __init__(self, expt, name, config):
        super(AccessEsm1p6, self).__init__(expt, name, config)

        self.model_type = 'access-esm1.6'

        for model in self.expt.models:
            if model.model_type == 'cice' or model.model_type == 'cice5':
                model.config_files = ['cice_in.nml',
                                      'input_ice.nml']

                model.ice_nml_fname = 'cice_in.nml'

                model.access_restarts = ['mice.nc']
                model.copy_restarts = True

                model.set_timestep = model.set_access_timestep

                # Structure of model coupling namelist
                model.cpl_fname = 'input_ice.nml'
                model.cpl_group = 'coupling'
                # Experiment initialisation date
                model.init_date_key = "init_date"
                # Start date for new run
                model.inidate_key = "inidate"
                # Total time in seconds since initialisation date
                model.runtime0_key = 'runtime0'
                # Simulation length in seconds for new run
                model.runtime_key = "runtime"

            if model.model_type == 'cice':
                # The ACCESS build of CICE4 assumes that restart_dir is 'RESTART'
                model.get_ptr_restart_dir = lambda : '.'
                # We also rely on having an extra 'restart_date.nml' file
                model.start_date_nml_name = "restart_date.nml"

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

            if model.model_type == 'cice' or model.model_type == 'cice5':

                # Horrible hack to make a link to o2i.nc in the
                # work/ice/RESTART directory
                f_name = 'o2i.nc'
                f_src = os.path.join(model.work_path, f_name)
                f_dst = os.path.join(model.work_restart_path, f_name)

                if os.path.isfile(f_src):
                    make_symlink(f_src, f_dst)

                # Update the supplemental OASIS namelists
                # cpl_nml is the coupling namelist copied from the control to
                # work directory.
                cpl_fpath = os.path.join(model.work_path, model.cpl_fname)
                cpl_nml = f90nml.read(cpl_fpath)
                cpl_group = cpl_nml[model.cpl_group]

            if model.model_type == 'cice5':

                # Stage the supplemental input files
                if model.prior_restart_path:
                    for f_name in model.access_restarts:
                        f_src = os.path.join(model.prior_restart_path, f_name)
                        f_dst = os.path.join(model.work_input_path, f_name)

                        if os.path.isfile(f_src):
                            make_symlink(f_src, f_dst)

            # find calendar, cice5 is determined in cice5 driver
            if model.model_type == 'cice':
                model.caltype = cpl_nml[model.cpl_group]['caltype']

            if model.model_type == 'cice' or model.model_type == 'cice5':

                # Experiment initialisation date
                init_date = cal.int_to_date(INIT_DATE)

                # Get timing information for the new run.
                if model.prior_restart_path:

                    if model.model_type == 'cice':
                        # Read the start date from the restart date namelist.
                        start_date_fpath = os.path.join(
                            model.prior_restart_path,
                            model.start_date_nml_name
                        )

                        try:
                            start_date_nml = f90nml.read(start_date_fpath)[
                                model.cpl_group]
                        except FileNotFoundError:
                            print(
                                "Missing restart date file for model "
                                f"{model.model_type}",
                                file=sys.stderr
                            )
                            raise

                        # Experiment initialisation date
                        init_date = cal.int_to_date(
                            start_date_nml[model.init_date_key]
                        )

                        # Start date of new run
                        run_start_date = cal.int_to_date(
                            start_date_nml[model.inidate_key]
                        )

                    elif model.model_type == 'cice5':
                        # get_restart_datetime returns cftime objects, 
                        # convert to datetime
                        run_start_date = datetime.fromisoformat(
                            model.get_restart_datetime(model.prior_restart_path).isoformat()
                        ).date()

                    # run_start_date must be after initialisation date
                    if run_start_date < init_date:
                        msg = (
                            f"Restart date ({run_start_date}) in "
                            f"cice restart ('iced') must not be "
                            f"before initialisation date ({INIT_DATE}). "
                        )
                        raise ValueError(msg)

                    # Calculate the total number of seconds between the
                    # initialisation and new run start date,
                    # to use for the runtime0 field.
                    previous_runtime = cal.seconds_between_dates(
                        init_date,
                        run_start_date,
                        model.caltype
                    )

                    cpl_group['jobnum'] = cpl_group['jobnum'] + 1

                else:
                    previous_runtime = 0
                    cpl_group['jobnum'] = 1
                    run_start_date = init_date

                # Set runtime for this run. 
                if self.expt.runtime:
                    run_runtime = cal.runtime_from_date(
                        run_start_date,
                        self.expt.runtime['years'],
                        self.expt.runtime['months'],
                        self.expt.runtime['days'],
                        0, #secs
                        model.caltype)
                    if run_runtime <=0 :
                        raise RuntimeError("invalid runtime specified in config.yaml")
                else:
                    raise RuntimeError("runtime missing from config.yaml")

                # Namelist dates only required for CICE4
                if model.model_type == "cice":
                    # Now write out new run start date and total runtime into the
                    # work directory namelist.
                    cpl_group[model.init_date_key] = cal.date_to_int(init_date)
                    cpl_group[model.inidate_key] = cal.date_to_int(run_start_date)
                    cpl_group[model.runtime0_key] = previous_runtime

                cpl_group[model.runtime_key] = int(run_runtime)

                # write coupler namelist
                nml_work_path = os.path.join(model.work_path, model.cpl_fname)

                # TODO: Does this need to be split into two steps?
                f90nml.write(cpl_nml, nml_work_path + '~')
                shutil.move(nml_work_path + '~', nml_work_path)

                if  model.prior_restart_path and model.model_type == 'cice' :
                    # Set up and check the cice restart files.
                    model.overwrite_restart_ptr(run_start_date,
                                                previous_runtime,
                                                start_date_fpath)

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
            if model.model_type == 'cice5' or model.model_type == 'cice':

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

            if model.model_type == 'cice':
                # Write the simulation end date to the restart date
                # namelist.

                # Calculate the end date using information from the work
                # directory coupling namelist.
                work_cpl_fpath = os.path.join(model.work_path, model.cpl_fname)
                work_cpl_nml = f90nml.read(work_cpl_fpath)
                work_cpl_grp = work_cpl_nml[model.cpl_group]

                # Timing information on the completed run.
                exp_init_date_int = work_cpl_grp[model.init_date_key]
                run_start_date_int = work_cpl_grp[model.inidate_key]
                run_runtime = work_cpl_grp[model.runtime_key]
                run_caltype = work_cpl_grp["caltype"]

                # Calculate end date of completed run
                run_end_date = cal.date_plus_seconds(
                    cal.int_to_date(run_start_date_int),
                    run_runtime,
                    run_caltype
                )

                end_date_dict = {
                    model.cpl_group: {
                        model.init_date_key: exp_init_date_int,
                        model.inidate_key: cal.date_to_int(run_end_date)
                    }
                }

                # Write restart date to the restart directory
                end_date_path = os.path.join(model.restart_path,
                                             model.start_date_nml_name)
                f90nml.write(end_date_dict, end_date_path, force=True)


    def get_restart_datetime(self, restart_path):
        """Given a restart path, parse the restart files and
        return a cftime datetime (for date-based restart pruning)"""

        # Use mom by default and um if ocean not present
        model_types = ['mom', 'um', 'cice5']

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
