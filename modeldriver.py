# coding: utf-8

import os
import shutil

# TODO: Redesign the various models to subclass Model
# TODO: Move relevant parts of Experiment into Model
class Model(object):

    def __init__(self, expt):

        # Inherit experiment configuration
        self.expt = expt

        #---
        # Null stuff, mostly to remind me what needs configuring in the drivers

        # Model details
        self.model_name = None
        self.default_exec = None

        # Path names
        self.work_input_path = None
        self.work_restart_path = None
        self.exec_path = None


    def set_model_pathnames(self):

        # Individual models may override the work subdirectories
        self.work_input_path = self.expt.work_path
        self.work_restart_path = self.expt.work_path

        assert self.default_exec
        exec_name = self.expt.config.get('exe', self.default_exec)

        assert self.expt.bin_path
        self.exec_path = os.path.join(self.expt.bin_path, exec_name)


    def setup(self):

        # Copy configuration files from control path
        for f in self.config_files:
            f_path = os.path.join(self.expt.control_path, f)
            shutil.copy(f_path, self.expt.work_path)
