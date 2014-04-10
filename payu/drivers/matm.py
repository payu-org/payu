#!/usr/bin/env python
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
import sys
import shlex
import shutil
import subprocess as sp

# Local
from ..modeldriver import Model
from ..fsops import mkdir_p

class Matm(Model):

    #---
    def __init__(self, expt, name, config):
        super(Matm, self).__init__(expt, name, config)

        self.model_type = 'matm'
        self.default_exec = 'matm'

        self.modules = ['pbs',
                        'openmpi']

        self.config_files = ['input_atm.nml',
                             'data_4_matm.table']


    def set_model_pathnames(self):
        super(Matm, self).set_model_pathnames()

        self.work_input_path = os.path.join(self.work_path, 'INPUT')


    def archive(self):

        # Create an empty restart directory
        mkdir_p(self.restart_path)
