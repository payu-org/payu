"""payu.models.qgcm
   ================

   Driver interface to qgcm

   :copyright: Copyright 2016 Marshall Ward, see AUTHORS for details
   :license: Apache License, Version 2.0, see LICENSE for details
"""

import os
import shutil

from payu.fsops import mkdir_p
from payu.models.model import Model


class Qgcm(Model):

    def __init__(self, expt, name, config):
        super(Qgcm, self).__init__(expt, name, config)

        self.model_type = 'qgcm'
        self.default_exec = 'q-gcm'

        self.config_files = [
            'input.params',
            'areas.limits',
            'outdata.dat',
        ]

        self.mpthreads = config.get('mpthreads')

    def set_model_pathnames(self):

        super(Qgcm, self).set_model_pathnames()

        # Define local directories
        self.work_input_path = os.path.join(self.work_path, 'INPUT')
        self.work_init_path = self.work_input_path

    def setup(self):
        super(Qgcm, self).setup()

        os.environ.update({"OMP_NUM_THREADS" : str(self.mpthreads)} )

        print("OMP_NUM_THREADS = {}".format(os.environ["OMP_NUM_THREADS"]))

    def archive(self, **kwargs):

        # Remove symbolic links
        for f in os.listdir(self.work_input_path):
            f_path = os.path.join(self.work_input_path, f)
            if os.path.islink(f_path):
                os.remove(f_path)

        # Archive the restart files
        mkdir_p(self.restart_path)

        restart_files = [f for f in os.listdir(self.work_path)
                         if f.endswith('lastday.nc')]

        for f in restart_files:
            f_src = os.path.join(self.work_path, f)
            shutil.move(f_src, self.restart_path)

    def collate(self):
        pass
