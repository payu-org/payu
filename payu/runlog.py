"""payu.runlog
   ===========

   Experiment run logging manager

   :copyright: Copyright 2011-2014 Marshall Ward, see AUTHORS for details.
   :license: Apache License, Version 2.0, see LICENSE for details.
"""

# Standard Library
import datetime
import os
import shlex
import subprocess

# Local
from payu import envmod
from payu.fsops import DEFAULT_CONFIG_FNAME


class Runlog(object):

    def __init__(self, expt):

        self.expt = expt

        self.manifest = []
        self.create_manifest()


    def create_manifest(self):

        config_path = os.path.join(self.expt.control_path,
                                   DEFAULT_CONFIG_FNAME)

        if os.path.isfile(config_path):
            self.manifest.append(config_path)

        for model in self.expt.models:
            self.manifest.extend(os.path.join(model.control_path, f)
                                 for f in model.config_files)


    def commit(self):

        # TODO: We currently need git v1.9.x, but this may be too strict
        envmod.module('load', 'git')

        # TODO: Remove this
        cmd = 'git --version'
        rc = subprocess.call(shlex.split(cmd))

        # Check if a repository exists
        cmd = 'git -C {} rev-parse'.format(self.expt.control_path)
        print(cmd)
        rc = subprocess.call(shlex.split(cmd))
        if rc:
            cmd = 'git init {}'.format(self.expt.control_path)
            print(cmd)
            subprocess.check_call(shlex.split(cmd))

        # Add configuration files
        for fname in self.manifest:
            cmd = 'git -C {} add {}'.format(self.expt.control_path, fname)
            print(cmd)
            subprocess.check_call(shlex.split(cmd))

        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        commit_msg = '{}: Run {}'.format(timestamp, self.expt.counter)

        cmd = 'git -C {} commit -am "{}"'.format(self.expt.control_path,
                                                 commit_msg)
        print(cmd)
        try:
            subprocess.check_call(shlex.split(cmd))
        except subprocess.CalledProcessError:
            print('TODO: Check if commit is unchanged')
