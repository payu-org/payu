# coding: utf-8
"""payu.models.yatm
   ================

   Driver interface to the YATM model.

   :copyright: Copyright 2011 Marshall Ward, see AUTHORS for details
   :license: Apache License, Version 2.0, see LICENSE for details
"""

# Standard Library
import os
import shutil

# Local
from payu.models.model import Model
from payu.fsops import mkdir_p


class Yatm(Model):

    def __init__(self, expt, name, config):
        super(Yatm, self).__init__(expt, name, config)

        self.model_type = 'yatm'
        self.config_files = ['atm.nml', 'forcing.json']

    def setup(self):
        super(Yatm, self).setup()

        # Make log dir
        mkdir_p(os.path.join(self.work_path, 'log'))

    def set_model_pathnames(self):
        super(Yatm, self).set_model_pathnames()

        self.work_input_path = os.path.join(self.work_path, 'INPUT')

    def archive(self):

        # Create an empty restart directory
        mkdir_p(self.restart_path)

        shutil.rmtree(self.work_input_path)

    def collate(self):
        pass
