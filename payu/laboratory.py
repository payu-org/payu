"""payu.laboratory
   ===============

   Interface to the numerical model laboratory

   :copyright: Copyright 2011-2014 Marshall Ward, see AUTHORS for details.
   :license: Apache License, Version 2.0, see LICENSE for details.
"""

# Python3 preparation
from __future__ import print_function

# Standard Library
import os
import pwd

# Local
from payu.fsops import mkdir_p, read_config


#---
class Laboratory(object):
    """Interface to the numerical model's laboratory."""

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

        self.lab_path = None
        self.archive_path = None
        self.bin_path = None
        self.input_basepath = None
        self.codebase_path = None


    #---
    def set_lab_pathnames(self):
        """Determine laboratory directory pathnames."""

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
        """Get laboratory pathnames and create subdirectories."""

        self.set_lab_pathnames()

        mkdir_p(self.archive_path)
        mkdir_p(self.bin_path)
        mkdir_p(self.codebase_path)
        mkdir_p(self.input_basepath)
