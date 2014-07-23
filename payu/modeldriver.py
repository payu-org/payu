# coding: utf-8
"""payu.modeldriver
   ================

   Generic driver to be inherited by other models

   :copyright: Copyright 2011-2014 Marshall Ward
   :license: Apache License, Version 2.0, see LICENSE for details
"""

# Standard Library
import errno
import os
import shutil
import shlex
import sys
import subprocess as sp

# Local
from payu.fsops import make_symlink, mkdir_p

class Model(object):
    """Abstract model class"""

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
        self.exec_name = None
        self.codebase_path = None
        self.build_exec_path = None
        self.build_path = None

        # Control flags
        self.copy_restarts = False
        self.copy_inputs = False

        # Codebase details
        self.repo_url = None
        self.repo_tag = None
        self.build_command = None


    #---
    def set_model_pathnames(self):

        self.control_path = self.expt.control_path
        self.input_basepath = self.expt.lab.input_basepath
        self.work_path = self.expt.work_path
        self.codebase_path = self.expt.lab.codebase_path

        if len(self.expt.models) > 1:

            self.control_path = os.path.join(self.control_path, self.name)
            self.work_path = os.path.join(self.work_path, self.name)
            self.codebase_path = os.path.join(self.codebase_path, self.name)

        # NOTE: Individual models may override the work subdirectories
        self.work_input_path = self.work_path
        self.work_restart_path = self.work_path
        self.work_output_path = self.work_path
        self.work_init_path = self.work_path

        self.exec_name = self.config.get('exe', self.default_exec)
        if self.exec_name:
            self.exec_path = os.path.join(self.expt.lab.bin_path,
                                          self.exec_name)
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
        for f_name in self.config_files:
            f_path = os.path.join(self.control_path, f_name)
            shutil.copy(f_path, self.work_path)

        for f_name in self.optional_config_files:
            f_path = os.path.join(self.control_path, f_name)
            try:
                shutil.copy(f_path, self.work_path)
            except IOError as exc:
                if exc.errno == errno.ENOENT:
                    pass
                else:
                    raise

        # Link restart files from prior run
        if self.prior_restart_path and not self.expt.repeat_run:
            restart_files = self.get_prior_restart_files()
            for f_name in restart_files:
                f_restart = os.path.join(self.prior_restart_path, f_name)
                f_input = os.path.join(self.work_init_path, f_name)
                if self.copy_restarts:
                    shutil.copy(f_restart, f_input)
                else:
                    make_symlink(f_restart, f_input)

        # Link input data
        for input_path in self.input_paths:
            input_files = os.listdir(input_path)
            for f_name in input_files:
                f_input = os.path.join(input_path, f_name)
                f_work_input = os.path.join(self.work_input_path, f_name)
                # Do not use input file if it is in RESTART
                if not os.path.exists(f_work_input):
                    if self.copy_inputs:
                        shutil.copy(f_input, f_work_input)
                    else:
                        make_symlink(f_input, f_work_input)


    #---
    def archive(self):
        raise NotImplementedError


    #---
    def collate(self):
        raise NotImplementedError


    #---
    def build_model(self):

        if not self.repo_url:
            return

        # Check to see if executable already exists.
        if self.exec_path and os.path.exists(self.exec_path):
            print('payu: warning: {} will be overwritten.'
                  ''.format(self.exec_path))

        # First step is always to go to the codebase.
        curdir = os.getcwd()

        # Do the build. First check whether there is a build command in the
        # config. If not check for the model default, otherwise just run make.

        try:
            build_path = self.config['build']['path_to_build_command']
        except KeyError:
            if self.build_path:
                build_path = self.build_path
            else:
                build_path = './'

        os.chdir(os.path.join(self.codebase_path, build_path))

        try:
            cmd = self.config['build']['command']
        except KeyError:
            if self.build_command:
                cmd = self.build_command
            else:
                cmd = 'make'

        print('Running command {}'.format(cmd))
        sp.check_call(shlex.split(cmd))

        try:
            build_exec_path = os.path.join(self.codebase_path,
                                           self.config['build']['exec_path'])
        except KeyError:
            if self.build_exec_path:
                build_exec_path = self.build_exec_path
            else:
                build_exec_path = self.codebase_path

        # Copy newly build executable to bin dir.
        if self.exec_path:
            build_exec_path = os.path.join(build_exec_path, self.exec_name)
            shutil.copy(build_exec_path, self.exec_path)

        os.chdir(curdir)


    #---
    def get_codebase(self):

        if not self.repo_url:
            return

        assert self.repo_tag
        assert self.codebase_path

        try:
            self.repo_url = self.config['build']['repository']
        except KeyError:
            # Use default.
            pass

        try:
            self.repo_tag = self.config['build']['tag']
        except KeyError:
            if not self.repo_tag:
                self.repo_tag = 'master'

        if not os.path.exists(self.codebase_path):
            cmd = 'git clone {} {}'.format(self.repo_url, self.codebase_path)
            rc = sp.call(shlex.split(cmd))
            assert rc == 0

        curdir = os.getcwd()
        os.chdir(self.codebase_path)
        rc = sp.call(shlex.split('git checkout {}'.format(self.repo_tag)))
        assert rc == 0
        rc = sp.call(shlex.split('git pull'))
        assert rc == 0
        os.chdir(curdir)
