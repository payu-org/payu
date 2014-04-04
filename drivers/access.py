#!/usr/bin/env python
# coding: utf-8
"""
The payu interface for the CICE model
-------------------------------------------------------------------------------
Contact: Marshall Ward <marshall.ward@anu.edu.au>
-------------------------------------------------------------------------------
Distributed as part of Payu, Copyright 2011-2012 Marshall Ward
Licensed under the Apache License, Version 2.0
http://www.apache.org/licenses/LICENSE-2.0
"""

# Standard Library
import datetime
import os
import sys
import shlex
import shutil
import subprocess as sp

# Extensions
import f90nml

# Local
from ..modeldriver import Model

class Access(Model):

    #---
    def __init__(self, expt, name, config):
        super(Access, self).__init__(expt, name, config)

        self.model_type = 'access'

        self.modules = ['pbs',
                        'openmpi']

        # TODO: set up model dict?
        for model in self.expt.models:
            if model.model_type == 'cice':
                model.config_files = ['cice_in.nml',
                                      'input_ice.nml',
                                      'input_ice_gfdl.nml',
                                      'input_ice_monin.nml']

                model.ice_nml_fname = 'cice_in.nml'


    #---
    def setup(self):

        cpl_keys = {'cice': ('input_ice.nml', 'coupling_nml', 'runtime0'),
                    'matm': ('input_atm.nml', 'coupling', 'truntime0')}

        for model in self.expt.models:
            if model.model_type in ('cice', 'matm'):

                cpl_fname, cpl_group, runtime0_key = cpl_keys[model.model_type]

                cpl_fpath = os.path.join(model.work_path, cpl_fname)
                cpl_nml = f90nml.read(cpl_fpath)

                if model.prior_output_path:
                    prior_cpl_fpath = os.path.join(model.prior_output_path,
                                                   cpl_fname)
                    prior_cpl_nml = f90nml.read(prior_cpl_fpath)

                    # Calculate initial runtime (runtime0, in seconds)
                    cpl_nml_grp = prior_cpl_nml[cpl_group]
                    runtime0 = cpl_nml_grp[runtime0_key] + cpl_nml_grp['runtime']

                    prior_idate = prior_cpl_nml[cpl_group]['init_date']
                    init_date = datetime.date(int(prior_idate[0:4]),
                                              int(prior_idate[4:6]),
                                              int(prior_idate[6:8]))

                    dt_run = datetime.timedelta(seconds=runtime0)

                    # TODO: Leap year correction

                    t_new = init_date + dt_run
                    inidate = '{:04}{:02}{:02}'.format(t_new.year, t_new.month,
                                                       t_new.day)
                else:
                    inidate = cpl_nml[cpl_group]['init_date']
                    runtime0 = 0

                cpl_nml[cpl_group]['inidate'] = inidate
                cpl_nml[cpl_group][runtime0_key] = runtime0

                nml_work_path = os.path.join(model.work_path, cpl_fname)
                f90nml.write(cpl_nml, nml_work_path + '~')
                shutil.move(nml_work_path + '~', nml_work_path)


    #---
    def archive(self):

        for model in self.expt.models:
            model.archive()
