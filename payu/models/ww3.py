"""payu.models.ww3
   ================

   Driver interface to WAVEWATCH3

   :copyright: Copyright 2015 Marshall Ward, see AUTHORS for details
   :license: Apache License, Version 2.0, see LICENSE for details
"""

import os

from payu.models.model import Model


class WW3(Model):

    def __init__(self, expt, name, config):
        super(WW3, self).__init__(expt, name, config)

        self.model_type = 'ww3'
        self.default_exec = 'ww3_shel'

        self.config_files = [
            'ww3_shel.inp',
        ]

    def setup(self):
        super(WW3, self).setup()

        # TODO: Construct grid files
        pass

    def archive(self, **kwargs):
        for f in os.listdir(self.work_input_path):
            f_path = os.path.join(self.work_input_path, f)
            if os.path.islink(f_path):
                os.remove(f_path)

    def collate(self):
        pass
