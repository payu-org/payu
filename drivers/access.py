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

        cpl_nml_fname = {'cice': 'input_ice.nml',
                         'matm': 'input_atm.nml'}

        cpl_namelist = {'cice': 'coupling_nml',
                        'matm': 'coupling'}

        cpl_runtime0_key = {'cice': 'runtime0',
                            'matm': 'truntime0'}

        # TODO: set up model dict?
        for model in self.expt.models:
            if model.model_type in ('cice', 'matm'):

                nml_fname = cpl_nml_fname[model.model_type]
                cpl_name = cpl_namelist[model.model_type]
                runtime0_key = cpl_runtime0_key[model.model_type]

                nml_path = os.path.join(model.work_path, nml_fname)
                cpl_nml = f90nml.read(nml_path)

                # TODO: Calculate inidate, runtime0
                inidate = 'i dont know'
                cpl_nml[cpl_name]['inidate'] = inidate

                prior_nml_path = os.path.join(model.prior_output_path,
                                              nml_fname)
                prior_cpl_nml = f90nml.read(prior_nml_path)

                # Calculate truntime0
                coupling_nml = prior_cpl_nml[cpl_name]
                runtime0 = coupling_nml[runtime0_key] + coupling_nml['runtime']

                cpl_nml[cpl_name][runtime0_key] = runtime0

                nml_path = os.path.join(model.work_path, nml_fname)
                f90nml.write(cpl_nml, nml_path + '~')
                shutil.move(nml_path + '~', nml_path)


    #---
    def archive(self):

        for model in self.expt.models:
            model.archive()
