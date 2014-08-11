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

    def __init__(self, model_type=None, config_path=None, lab_path=None):

        # Attach inputs
        config = read_config(config_path)

        # Set the file permission mask
        perms = config.get('umask', 0o0027)
        os.umask(perms)

        # Set model type
        if not model_type:
            model_type = config.get('model')

        if not model_type:
            raise ValueError('Cannot determine model type.')

        self.model_type = model_type

        # Set top-level lab path if provided
        if lab_path:
            self.basepath = lab_path
        elif 'PAYU_LAB_PATH' in os.environ:
            self.basepath = os.environ.get('PAYU_LAB_PATH')
        else:
            self.basepath = config.get('laboratory')

        # If no lab path is set, generate a default path
        if not self.basepath:
            self.basepath = self.get_default_lab_path(config)

        # Set subdirectory paths
        self.archive_path = os.path.join(self.basepath, 'archive')
        self.bin_path = os.path.join(self.basepath, 'bin')
        self.codebase_path = os.path.join(self.basepath, 'codebase')
        self.input_basepath = os.path.join(self.basepath, 'input')
        self.work_path = os.path.join(self.basepath, 'work')


    #---
    def get_default_lab_path(self, config):
        """Generate a default laboratory path based on user environment."""

        # Default path settings
        default_short_path = os.path.join('/short', os.environ.get('PROJECT'))
        default_user = pwd.getpwuid(os.getuid()).pw_name

        short_path = config.get('shortpath', default_short_path)
        lab_name = config.get('laboratory', self.model_type)

        if os.path.isabs(lab_name):
            lab_path = lab_name
        else:
            user_name = config.get('user', default_user)
            lab_path = os.path.join(short_path, user_name, lab_name)

        return lab_path


    #---
    def initialize(self):
        """Create the laboratory directories."""

        # Create laboratory directories
        mkdir_p(self.archive_path)
        mkdir_p(self.bin_path)
        mkdir_p(self.codebase_path)
        mkdir_p(self.input_basepath)
