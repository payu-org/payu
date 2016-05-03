"""payu.models.nemo
   ================

   Driver interface to NEMO

   :copyright: Copyright 2016 Marshall Ward, see AUTHORS for details
   :license: Apache License, Version 2.0, see LICENSE for details
"""

import os
import shutil

from payu.fsops import mkdir_p
from payu.models.model import Model


class Nemo(Model):

    def __init__(self, expt, name, config):
        super(Nemo, self).__init__(expt, name, config)

        self.model_type = 'nemo'
        self.default_exec = 'opa'

        self.config_files = [
            'namelist',
            'namelist_ice',
        ]

    def archive(self, **kwargs):

        # Remove symbolic links
        for f in os.listdir(self.work_input_path):
            f_path = os.path.join(self.work_input_path, f)
            if os.path.islink(f_path):
                os.remove(f_path)

        # Archive the restart files
        print("restart path", self.restart_path)
        mkdir_p(self.restart_path)

        restart_files = [f for f in os.listdir(self.work_path)
                         if f.endswith('.dimg')]

        for f in restart_files:
            f_src = os.path.join(self.work_path, f)
            shutil.move(f_src, self.restart_path)

    def collate(self):
        pass
