"""Roms driver interface

:copyright: Copyright 2019 Marshall Ward, see AUTHORS for details
:license: Apache License, Version 2.0, see LICENSE for details
"""
import os
import shlex
import shutil
import subprocess

from payu.models.model import Model

config_files = [
            'roms.in',
            'varinfo_seacofs.yaml'
        ]
optional_config_files = []


class Roms(Model):

    def __init__(self, expt, name, config):

        # payu initialisation
        super(Roms, self).__init__(expt, name, config)

        # Model-specific configuration
        self.model_type = 'roms'

        self.config_files = config_files
        self.optional_config_files = optional_config_files
