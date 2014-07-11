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

# Standard Library
import datetime
import errno
import os
import shutil
import re

# Extensions
import f90nml

# Local
from payu.fsops import make_symlink
from payu.modeldriver import Model
import payu.calendar as cal

class Access(Model):

    #---
    def __init__(self, expt, name, config):
        super(Access, self).__init__(expt, name, config)

        self.model_type = 'access'

        self.modules = ['pbs',
                        'openmpi']

        for model in self.expt.models:
            if model.model_type == 'cice':
                model.config_files = ['cice_in.nml',
                                      'input_ice.nml',
                                      'input_ice_gfdl.nml',
                                      'input_ice_monin.nml']

                model.ice_nml_fname = 'cice_in.nml'

                model.access_restarts = ['u_star.nc', 'sicemass.nc', 'mice.nc']

    #---
    def setup(self):

        cpl_keys = {'cice': ('input_ice.nml', 'coupling_nml', 'runtime0'),
                    'matm': ('input_atm.nml', 'coupling', 'truntime0')}

        # Keep track of this in order to set the oasis runtime. 
        run_runtime = 0

        for model in self.expt.models:

            if model.model_type == 'cice':

                # Stage the supplemental input files
                if model.prior_restart_path:
                    for f_name in model.access_restarts:
                        f_src = os.path.join(model.prior_restart_path, f_name)
                        f_dst = os.path.join(model.work_input_path, f_name)

                        if os.path.isfile(f_src):
                            make_symlink(f_src, f_dst)

            if model.model_type in ('cice', 'matm'):

                # Update the supplemental OASIS namelists
                cpl_fname, cpl_group, runtime0_key = cpl_keys[model.model_type]

                cpl_fpath = os.path.join(model.work_path, cpl_fname)
                cpl_nml = f90nml.read(cpl_fpath)

                # Which calendar are we using, noleap or Gregorian.
                caltype = cpl_nml[cpl_group]['caltype']
                init_date = cal.int_to_date(cpl_nml[cpl_group]['init_date'])

                # Get time info about the beginning of this run. We're interested
                # in: 1) start date of run, 2) total runtime of all previous runs.
                if model.prior_output_path:

                    prior_cpl_fpath = os.path.join(model.prior_output_path,
                                                   cpl_fname)
                    prior_cpl_nml = f90nml.read(prior_cpl_fpath)
                    cpl_nml_grp = prior_cpl_nml[cpl_group]

                    # The total time in seconds since the beginning of
                    # the experiment.
                    total_runtime = int(cpl_nml_grp[runtime0_key] +
                                          cpl_nml_grp['runtime'])
                    run_start_date = cal.date_plus_seconds(init_date, total_runtime,
                                                           caltype)

                else:
                    total_runtime = 0
                    run_start_date = init_date

                # Get new runtime for this run. We get this from either the
                # 'runtime' part of the payu config, or from the namelist
                if self.expt.runtime:
                    run_runtime = cal.runtime_from_date(run_start_date, 
                                                        self.expt.runtime['years'],
                                                        self.expt.runtime['months'],
                                                        self.expt.runtime['days'], 
                                                        caltype)
                else:
                    run_runtime = cpl_nml[cpl_group]['runtime']

                # Now write out new run start date and total runtime.
                cpl_nml[cpl_group]['inidate'] = cal.date_to_int(run_start_date)
                cpl_nml[cpl_group][runtime0_key] = total_runtime
                cpl_nml[cpl_group]['runtime'] = int(run_runtime)

                if model.model_type == 'cice':
                    cpl_nml[cpl_group]['jobnum'] = 1 + self.expt.counter

                nml_work_path = os.path.join(model.work_path, cpl_fname)
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
                    assert(m is not None)
                    s = s[:m.start(1)] + str(run_runtime) + s[m.end(1):]

                with open(namcouple, 'w') as f:
                    f.write(s)

    #---
    def archive(self):

        for model in self.expt.models:
            if model.model_type == 'cice':

                # Move supplemental restart files to RESTART path
                for f_name in model.access_restarts:
                    f_src = os.path.join(model.work_path, f_name)
                    f_dst = os.path.join(model.restart_path, f_name)

                    if os.path.exists(f_src):
                        shutil.move(f_src, f_dst)

    #---
    def collate(self):
        raise NotImplementedError

