#!/usr/bin/env python
# coding: utf-8
"""
The payu implementation of GOLD
-------------------------------------------------------------------------------
Contact: Marshall Ward <marshall.ward@anu.edu.au>
-------------------------------------------------------------------------------
Distributed as part of Payu, Copyright 2011 Marshall Ward
Licensed under the Apache License, Version 2.0
http://www.apache.org/licenses/LICENSE-2.0
"""

# Standard library
import os
import shutil as sh

# Local
from fms import Fms

class Gold(Fms):

    #---
    def __init__(self, expt, name, config):

        # FMS initalisation
        super(Gold, self).__init__(expt, name, config)

        self.model_type = 'gold'
        self.default_exec = 'GOLD'

        self.modules = ['pbs',
                        'openmpi']

        self.config_files = ['GOLD_input',
                             'GOLD_override',
                             'diag_table',
                             'fre_input.nml',
                             'input.nml']


    #---
    def setup(self):
        # FMS initialisation
        super(Gold, self).setup()

        # GOLD-specific initialisation
        if self.expt.counter == 0:
            self.init_config()


    #---
    def init_config(self):
        input_filepath = os.path.join(self.work_path, 'input.nml')
        temp_filepath  = ''.join([input_filepath, '~'])

        input_file = open(input_filepath)
        temp_file  = open(temp_filepath, 'w')

        for line in input_file:
            temp_file.write(line.replace("input_filename = 'r'",
                                         "input_filename = 'n'"))

        input_file.close()
        temp_file.close()
        sh.move(temp_filepath, input_filepath)
