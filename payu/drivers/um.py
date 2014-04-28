# coding: utf-8
"""
The payu interface for the UM atmosphere model
-------------------------------------------------------------------------------
Contact: Marshall Ward <marshall.ward@anu.edu.au>
-------------------------------------------------------------------------------
Distributed as part of Payu, Copyright 2011 Marshall Ward
Licensed under the Apache License, Version 2.0
http://www.apache.org/licenses/LICENSE-2.0
"""

from payu.modeldriver import Model
import os
import imp
import fileinput

class UnifiedModel(Model):

    #---
    def __init__(self, expt, name, config):
        super(UnifiedModel, self).__init__(expt, name, config)

        self.model_type = 'um'
        self.default_exec = 'um'

        self.modules = ['pbs',
                        'openmpi']

        self.config_files = ['CNTLALL', 'prefix.CNTLATM', 'prefix.CNTLGEN',
                             'prefix.CONTCNTL', 'errflag', 'exstat',
                             'ftxx', 'ftxx.new', 'ftxx.vars',
                             'hnlist', 'ihist', 'INITHIS',
                             'namelists', 'PPCNTL', 'prefix.PRESM_A',
                             'SIZES', 'STASHC', 'UAFILES_A', 'UAFLDS_A',
                             'parexe', 'cable.nml']

    def set_model_pathnames(self):
        super(UnifiedModel, self).set_model_pathnames()

        self.work_input_path = os.path.join(self.work_path, 'INPUT')

    #---
    def archive(self):
        raise NotImplementedError

    #---
    def collate(self):
        raise NotImplementedError

    #---
    def setup(self):
        super(UnifiedModel, self).setup()

        # Set up environment variables needed to run UM. 
        # Look for a python file in the config directory.
        um_env = imp.load_source('um_env',
                os.path.join(self.control_path, 'um_env.py'))
        vars = um_env.vars

        assert len(self.input_paths) == 1

        # Set some paths
        for k in vars.keys():
            vars[k] = vars[k].format(input_path=self.input_paths[0],
                                     work_path=self.work_path)

        # Paths need to be set in parexe also.
        parexe = os.path.join(self.work_path, 'parexe')
        for line in fileinput.input(parexe, inplace=True):
            line = line.format(input_path=self.input_paths[0],
                               work_path=self.work_path)
            print(line)

        # Put all in the current environment. 
        os.environ.update(vars)
