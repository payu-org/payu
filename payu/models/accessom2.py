# coding: utf-8
"""
The payu interface for the ACCESSOM2 coupled model
-------------------------------------------------------------------------------
Contact: Marshall Ward <marshall.ward@anu.edu.au>
-------------------------------------------------------------------------------
Distributed as part of Payu, Copyright 2011 Marshall Ward
Licensed under the Apache License, Version 2.0
http://www.apache.org/licenses/LICENSE-2.0
"""
from __future__ import print_function

import os
import shutil

from payu.models.model import Model


class AccessOm2(Model):

    def __init__(self, expt, name, config):
        super(AccessOm2, self).__init__(expt, name, config)

        self.model_type = 'access-om2'
        self.config_files = ['accessom2.nml', 'namcouple']

    def setup(self):
        # HACK: only call setup if this is called as a submodule
        if not self.top_level_model:
            super(AccessOm2, self).setup()

    def set_model_pathnames(self):
        super(AccessOm2, self).set_model_pathnames()

        # HACK: overwrite what super has done with these.
        self.work_path = self.expt.work_path
        self.control_path = self.expt.control_path

        self.work_input_path = self.work_path
        self.work_restart_path = self.work_path
        self.work_output_path = self.work_path
        self.work_init_path = self.work_path

        self.work_input_path = os.path.join(self.work_path, 'INPUT')
        self.work_restart_path = os.path.join(self.work_path, 'RESTART')

    def set_input_paths(self):
        super(AccessOm2, self).set_input_paths()

        # HACK: overwrite what super has done with this.
        input_dirs = self.expt.config.get('input')

    def set_model_output_paths(self):
        super(AccessOm2, self).set_model_output_paths()

        # HACK: overwrite what super has done with these.
        self.output_path = self.expt.output_path
        self.restart_path = self.expt.restart_path

        self.prior_output_path = self.expt.prior_output_path
        self.prior_restart_path = self.expt.prior_restart_path

    def archive(self):

        # HACK: only called when this is a submodule
        if not self.top_level_model:
            shutil.rmtree(self.work_input_path)
            for f in os.listdir(self.work_restart_path):
                shutil.move(os.path.join(self.work_restart_path, f),
                            self.restart_path)
            os.rmdir(self.work_restart_path)
        else:
            cice5 = None
            mom = None
            for model in self.expt.models:
                if model.model_type == 'cice5':
                    cice5 = model
                elif model.model_type == 'mom':
                    mom = model

            # Copy restart from ocean into ice area.
            if cice5 is not None and mom is not None:
                o2i_src = os.path.join(mom.work_path, 'o2i.nc')
                o2i_dst = os.path.join(cice5.restart_path, 'o2i.nc')
                shutil.copy2(o2i_src, o2i_dst)

    def collate(self):
        pass
