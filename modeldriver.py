# coding: utf-8

import os

# TODO: Redesign the various models to subclass Model
# TODO: Move relevant parts of Experiment into Model
class Model(object):

    def __init__(self, expt):

        # Inherit experiment configuration
        self.expt = expt
        self.config = self.expt.config

        # Null stuff, mostly to remind me what needs configuring in the drivers

        # Model details
        self.model_name = None
        self.default_exec = None

        # Path names
        self.control_path = None
        self.run_input_path = None
        self.run_restart_path = None
        self.exec_path = None


    def set_model_pathnames(self):

        assert self.default_exec
        exec_name = self.config.get('exe', self.default_exec)

        assert self.expt.bin_path
        self.exec_path = os.path.join(self.expt.bin_path, exec_name)


    def setup(self):

        # Copy configuration files from control path
        for f in model.config_files:
            f_path = os.path.join(self.control_path, f)
            sh.copy(f_path, self.work_path)
