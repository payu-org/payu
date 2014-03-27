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

# Local
from ..fsops import mkdir_p
from ..modeldriver import Model

class Oasis(Model):

    #---
    def __init__(self, expt, name, config):
        super(Oasis, self).__init__(expt, name, config)

        self.model_type = 'oasis'
        self.default_exec = 'oasis'

        # NOTE: OASIS3 uses an executable, but OASIS4 does not
        # TODO: Detect version?
        # if oasis_version == 3: self.default_exec = 'oasis'

        self.modules = ['pbs',
                        'openmpi']

        self.config_files = ['namcouple']
        self.optional_config_files = ['cf_name_table.txt']


    def setup(self):
        super(Oasis, self).setup()

        # Copy OASIS data to the other submodels
        input_filepaths = []
        for input_path in self.input_paths:
            for f in os.listdir(input_path):
                input_filepaths.append(os.path.join(input_path, f))

        for model in self.expt.models:

            # Skip the oasis model
            if model == self:
                continue

            mkdir_p(model.work_path)

            f_src = os.path.join(self.control_path, 'namcouple')
            f_dest = os.path.join(model.work_path, 'namcouple')
            os.symlink(f_src, f_dest)

            for f_path in input_filepaths:
                f_name = os.path.basename(f_path)
                f_work_path = os.path.join(model.work_path, f_name)
                os.symlink(f_path, f_work_path)
