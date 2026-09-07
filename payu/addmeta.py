"""Tooling to add metata to model output directories using the
addmeta tool

:copyright: Copyright 2011 Marshall Ward, see AUTHORS for details.
:license: Apache License, Version 2.0, see LICENSE for details.
"""
from types import SimpleNamespace

import addmeta

class AddMeta:
    """Add metadata to model output directories using the addmeta tool"""

    default_options = {
        'enable': True,
        'verbose': False,
        'update-history': False,
        'data': {},
        'metafiles': [],
        'datafiles': [],
        'fnregex': '',
    }

    def __init__(self, options):
        self.options = SimpleNamespace(**options)

    @classmethod
    def from_config(cls, config):
        """Create an AddMeta instance from a configuration dictionary"""
        return cls(cls.default_options | config)

    def update(self, namespace):
        """Update the AddMeta instance from a namespace. This is useful for 
           updating the instance with model specific arguments."""

        # Default to overwriting the options with the new values from the 
        # namespace except for metafiles and data, which should be combined 
        # with the existing values.
        for key, value in vars(namespace).items():
            if key == 'metafiles':
                value = self.options.metafiles + value
            if key == 'data':
                value = self.options.data | value
        setattr(self.options, key, value)

    def run(self):
        """Run the addmeta tool with the specified configuration"""

        addmeta.main(self.options.files)