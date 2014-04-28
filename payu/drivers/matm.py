# coding: utf-8
"""
The payu interface for the MATM model
-------------------------------------------------------------------------------
Contact: Marshall Ward <marshall.ward@anu.edu.au>
-------------------------------------------------------------------------------
Distributed as part of Payu, Copyright 2011 Marshall Ward
Licensed under the Apache License, Version 2.0
http://www.apache.org/licenses/LICENSE-2.0
"""

# Standard Library
import os

# Local
from payu.modeldriver import Model
from payu.fsops import mkdir_p

class Matm(Model):

    #---
    def __init__(self, expt, name, config):
        super(Matm, self).__init__(expt, name, config)

        self.model_type = 'matm'
        self.default_exec = 'matm'

        # Default repo details
        self.repo_url = 'https://github.com/nicholash/matm.git'
        self.repo_tag = 'master'

        self.modules = ['pbs',
                        'openmpi']

        self.config_files = ['input_atm.nml',
                             'data_4_matm.table']


    #---
    def set_model_pathnames(self):
        super(Matm, self).set_model_pathnames()

        self.build_exec_path = os.path.join(self.codebase_path, 'build_nt62')
        self.work_input_path = os.path.join(self.work_path, 'INPUT')


    #---
    def archive(self):

        # Create an empty restart directory
        mkdir_p(self.restart_path)


    #---
    def collate(self):
        pass
