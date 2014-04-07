# coding: utf-8

# Standard Library
import errno
import os
import shutil
import sys

# Local
from fsops import mkdir_p

class Model(object):

    def __init__(self, expt, model_name, model_config):

        # Inherit experiment configuration
        self.expt = expt
        self.name = model_name
        self.config = model_config

        #---

        # Model details
        self.model_type = None
        self.default_exec = None
        self.input_basepath = None
        self.modules = []
        self.config_files = []
        self.optional_config_files = []

        # Path names
        self.work_input_path = None
        self.work_restart_path = None
        self.work_init_path = None
        self.exec_path = None

        # Control flags
        self.copy_restarts = False
        self.copy_inputs = False


    #---
    def set_model_pathnames(self):

        self.control_path = self.expt.control_path
        self.input_basepath = self.expt.input_basepath
        self.work_path = self.expt.work_path

        if len(self.expt.models) > 1:

            self.control_path = os.path.join(self.control_path, self.name)
            self.work_path = os.path.join(self.work_path, self.name)

        # NOTE: Individual models may override the work subdirectories
        self.work_input_path = self.work_path
        self.work_restart_path = self.work_path
        self.work_output_path = self.work_path
        self.work_init_path = self.work_path

        exec_name = self.config.get('exe', self.default_exec)
        if exec_name:
            self.exec_path = os.path.join(self.expt.bin_path, exec_name)
        else:
            self.exec_path = None


    #---
    def set_input_paths(self):

        if len(self.expt.models) == 1:
            input_dirs = self.expt.config.get('input')
        else:
            input_dirs = self.config.get('input')

        if input_dirs is None:
            input_dirs = []
        elif type(input_dirs) == str:
            input_dirs = [input_dirs]

        self.input_paths = []
        for input_dir in input_dirs:

            # First test for absolute path
            if os.path.exists(input_dir):
                self.input_paths.append(input_dir)
            else:
                # Test for path relative to /${lab_path}/input/${model_name}
                assert self.input_basepath
                rel_path = os.path.join(self.input_basepath, input_dir)
                if os.path.exists(rel_path):
                    self.input_paths.append(rel_path)
                else:
                    sys.exit('payu: error: Input directory {} not found; '
                             'aborting.'.format(rel_path))


    #---
    def set_model_output_paths(self):

        self.output_path = self.expt.output_path
        self.restart_path = self.expt.restart_path

        self.prior_output_path = self.expt.prior_output_path
        self.prior_restart_path = self.expt.prior_restart_path

        if len(self.expt.models) > 1:

            self.output_path = os.path.join(self.output_path, self.name)
            self.restart_path = os.path.join(self.restart_path, self.name)

            if self.prior_output_path:
                self.prior_output_path = os.path.join(self.prior_output_path,
                                                      self.name)

            if self.prior_restart_path:
                self.prior_restart_path = os.path.join(self.prior_restart_path,
                                                       self.name)


    #---
    def get_prior_restart_files(self):
        return os.listdir(self.prior_restart_path)


    #---
    def setup(self):

        # Create experiment directory structure
        mkdir_p(self.work_input_path)
        mkdir_p(self.work_restart_path)
        mkdir_p(self.work_output_path)

        # Copy configuration files from control path
        for f in self.config_files:
            f_path = os.path.join(self.control_path, f)
            shutil.copy(f_path, self.work_path)

        for f in self.optional_config_files:
            f_path = os.path.join(self.control_path, f)
            try:
                shutil.copy(f_path, self.work_path)
            except IOError as ec:
                if ec.errno == errno.ENOENT:
                    pass
                else:
                    raise

        # Link restart files from prior run
        if self.prior_restart_path and not self.expt.repeat_run:
            restart_files = self.get_prior_restart_files()
            for f in restart_files:
                f_restart = os.path.join(self.prior_restart_path, f)
                f_input = os.path.join(self.work_init_path, f)
                if self.copy_restarts:
                    shutil.copy(f_restart, f_input)
                else:
                    os.symlink(f_restart, f_input)

        # Link input data
        for input_path in self.input_paths:
            input_files = os.listdir(input_path)
            for f in input_files:
                f_input = os.path.join(input_path, f)
                f_work_input = os.path.join(self.work_input_path, f)
                # Do not use input file if it is in RESTART
                if not os.path.exists(f_work_input):
                    if self.copy_inputs:
                        shutil.copy(f_input, f_work_input)
                    else:
                        os.symlink(f_input, f_work_input)


    #---
    def archive(self):
        raise NotImplementedError


    #---
    def collate(self):
        raise NotImplementedError
