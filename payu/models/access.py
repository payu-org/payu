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
import errno
import os
import re
import shutil
import sys

# Extensions
import f90nml

# Local
from payu.fsops import make_symlink
from payu.models.model import Model
from payu.models.mom import get_restart_datetime_using_mom_submodel
import payu.calendar as cal


class Access(Model):

    def __init__(self, expt, name, config):
        super(Access, self).__init__(expt, name, config)

        self.model_type = 'access'

        for model in self.expt.models:
            if model.model_type == 'cice' or model.model_type == 'cice5':
                model.config_files = ['cice_in.nml',
                                      'input_ice.nml']
                model.optional_config_files = ['input_ice_gfdl.nml',
                                               'input_ice_monin.nml']

                model.ice_nml_fname = 'cice_in.nml'

                model.access_restarts = ['mice.nc']
                model.copy_restarts = True

                model.set_timestep = model.set_access_timestep
                model.get_ptr_restart_dir = model.get_access_ptr_restart_dir

            if model.model_type == 'cice5':
                model.access_restarts.append(['u_star.nc', 'sicemass.nc'])

            if model.model_type == 'cice':
                # Structure of model coupling namelist
                model.cpl_fname = 'input_ice.nml'
                model.cpl_group = 'coupling'
                model.start_date_nml_name = "restart_date.nml"
                # Experiment initialisation date
                model.init_date_key = "init_date"
                # Start date for new run
                model.inidate_key = "inidate"
                # Total time in seconds since initialisation date
                model.runtime0_key = 'runtime0'
                # Simulation length in seconds for new run
                model.runtime_key = "runtime"

            if model.model_type == 'matm':
                # Structure of model coupling namelist
                model.cpl_fname = 'input_atm.nml'
                model.cpl_group = 'coupling'
                model.start_date_nml_name = "restart_date.nml"
                # Experiment initialisation date
                model.init_date_key = "init_date"
                # Start date for new run
                model.inidate_key = "inidate"
                # Total time in seconds since initialisation date
                model.runtime0_key = 'truntime0'
                # Simulation length in seconds for new run
                model.runtime_key = "runtime"


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

            if model.model_type == 'cice5':

                # Stage the supplemental input files
                if model.prior_restart_path:
                    for f_name in model.access_restarts:
                        f_src = os.path.join(model.prior_restart_path, f_name)
                        f_dst = os.path.join(model.work_input_path, f_name)

                        if os.path.isfile(f_src):
                            make_symlink(f_src, f_dst)

            if model.model_type in ('cice', 'matm'):

                # Update the supplemental OASIS namelists

                # cpl_nml is the coupling namelist copied from the control to
                # work directory.
                cpl_fpath = os.path.join(model.work_path, model.cpl_fname)
                cpl_nml = f90nml.read(cpl_fpath)
                cpl_group = cpl_nml[model.cpl_group]

                # Which calendar are we using, noleap or Gregorian.
                caltype = cpl_group['caltype']

                # Get timing information for the new run.
                if model.prior_restart_path and not self.expt.repeat_run:
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

                    # run_start_date must be after initialisation date
                    if run_start_date < init_date:
                        msg = (
                            "Restart date 'inidate` in "
                            f"{model.start_date_nml_name} must not be "
                            "before initialisation date `init_date. "
                            "Values provided: \n"
                            f"inidate={start_date_nml[model.inidate_key]}\n"
                            f"init_date={start_date_nml[model.init_date_key]}"
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
                    init_date = cal.int_to_date(
                        cpl_group[model.init_date_key]
                    )
                    previous_runtime = 0
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

                if model.model_type == 'cice':
                    if self.expt.counter and not self.expt.repeat_run:
                        cpl_group['jobnum'] = (
                            1 + self.expt.counter
                        )
                    else:
                        cpl_group['jobnum'] = 1

                nml_work_path = os.path.join(model.work_path, model.cpl_fname)

                # TODO: Does this need to be split into two steps?
                f90nml.write(cpl_nml, nml_work_path + '~')
                shutil.move(nml_work_path + '~', nml_work_path)

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

        cice5 = None
        mom = None

        for model in self.expt.models:
            if model.model_type == 'cice':

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

            if model.model_type in ('cice', 'matm'):
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

            if model.model_type == 'cice5':
                cice5 = model
            elif model.model_type == 'mom':
                mom = model

        # Copy restart from ocean into ice area.
        if cice5 is not None and mom is not None:
            o2i_src = os.path.join(mom.work_path, 'o2i.nc')
            o2i_dst = os.path.join(cice5.restart_path, 'o2i.nc')
            shutil.copy2(o2i_src, o2i_dst)

    def get_restart_datetime(self, restart_path):
        """Given a restart path, parse the restart files and
        return a cftime datetime (for date-based restart pruning)"""
        return get_restart_datetime_using_mom_submodel(
            model=self, 
            restart_path=restart_path
        )

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
