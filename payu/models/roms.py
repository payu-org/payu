"""Roms driver interface

:copyright: Copyright 2019 Marshall Ward, see AUTHORS for details
:license: Apache License, Version 2.0, see LICENSE for details
"""
import os
import shlex
import shutil
import subprocess
from pathlib import Path

from payu.models.model import Model
from payu.fsops import mkdir_p

config_files = ['varinfo_seacofs.yaml']
optional_config_files = []

class Roms(Model):

    def __init__(self, expt, name, config):

        # payu initialisation
        super(Roms, self).__init__(expt, name, config)

        # Model-specific configuration
        self.model_type = 'roms'

        self.config_files = config_files
        self.optional_config_files = optional_config_files

    def setup(self):
        # Add the model config file to the list of config files
        if 'model_config' not in self.config:
            raise ValueError(
                "'model_config' field must be specified in config.yaml for "
                "the ROMS model configuration filename, e.g. 'roms.in'"
            )

        model_config = self.config['model_config']

        if not (Path(self.control_path) / model_config).is_file():
            raise FileNotFoundError(
                f"Model configuration file '{model_config}' not found in the "
                f"control directory: {self.control_path}"
            )

        self.config_files.append(model_config)

        super(Roms, self).setup()

        # Set the model config file to be added after the executable
        # in the model run command
        self.exec_postfix = model_config

    def archive(self, **kwargs):

        # Remove symbolic links
        for f in os.listdir(self.work_input_path):
            f_path = os.path.join(self.work_input_path, f)
            if os.path.islink(f_path):
                os.remove(f_path)

        # Archive the restart files
        mkdir_p(self.restart_path)
        restart_files = [frst for frst in os.listdir(self.work_path) if 'rst' in frst]
        for frst in restart_files:
            f_src = os.path.join(self.work_path, frst)
            shutil.move(f_src, self.restart_path)

    def collate(self):
        pass