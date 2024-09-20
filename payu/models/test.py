"""Test driver interface

:copyright: Copyright 2019 Marshall Ward, see AUTHORS for details
:license: Apache License, Version 2.0, see LICENSE for details
"""
import os
import shlex
import shutil
import subprocess

from payu.models.model import Model

config_files = [
            'data',
            'diag',
            'input.nml'
        ]
optional_config_files = ['opt_data']


class Test(Model):

    def __init__(self, expt, name, config):

        # payu initialisation
        super(Test, self).__init__(expt, name, config)

        # Model-specific configuration
        self.model_type = 'test'
        self.default_exec = 'test.exe'

        self.config_files = config_files
        self.optional_config_files = optional_config_files
