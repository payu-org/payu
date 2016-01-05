"""payu.models.ww3
   ================

   Driver interface to WaveWatch3

   :copyright: Copyright 2015 Marshall Ward, see AUTHORS for details
   :license: Apache License, Version 2.0, see LICENSE for details
"""

from payu.models.model import Model


class WW3(Model):
    
    def __init__(self, expt, name, config):
        super(WW3, self).__init__(expt, name, config)

        self.model_type = 'ww3'
        self.default_exec = 'ww3_shel'

        self.config_files = [
            'ww3_grid.inp',
            'ww3_shel.inp',
            'ww3_ounf.inp'
        ]

    def collate(self):
        pass
