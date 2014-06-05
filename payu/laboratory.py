# coding: utf-8
"""payu.laboratory
   ===============

"""

# Python3 preparation
from __future__ import print_function

# Standard Library
import os
import pwd

# Local
from fsops import mkdir_p, read_config
from payu.modelindex import index as model_index


#---
class Laboratory(object):
    def __init__(self, model_type=None, config_path=None):

        # Disable group write access and all public access
        perms = 0o0027
        os.umask(perms)

        # Attach inputs
        self.config = read_config(config_path)

        if not model_type:
            model_type = self.config.get('model')

        # If no model type then abort
        if not model_type:
            raise ValueError('Cannot determine model type.')

        self.model_type = model_type

        # Laboratory paths to be configured
        self.set_lab_pathnames()


    #---
    def set_lab_pathnames(self):

        # Default path settings
        default_short_path = os.path.join('/short', os.environ.get('PROJECT'))
        default_user = pwd.getpwuid(os.getuid()).pw_name
        default_lab_name = self.model_type

        # Build laboratory paths
        short_path = self.config.get('shortpath', default_short_path)

        lab_name = self.config.get('laboratory', default_lab_name)

        if os.path.isabs(lab_name):
            self.lab_path = lab_name
        else:
            user_name = self.config.get('user', default_user)
            self.lab_path = os.path.join(short_path, user_name, lab_name)

        self.archive_path = os.path.join(self.lab_path, 'archive')
        self.bin_path = os.path.join(self.lab_path, 'bin')
        self.input_basepath = os.path.join(self.lab_path, 'input')
        self.codebase_path = os.path.join(self.lab_path, 'codebase')


    def init(self):

        mkdir_p(self.archive_path)
        mkdir_p(self.bin_path)
        mkdir_p(self.codebase_path)
        mkdir_p(self.input_basepath)
