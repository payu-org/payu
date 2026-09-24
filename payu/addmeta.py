"""Tooling to add metata to model output directories using the
addmeta tool

:copyright: Copyright 2011 Marshall Ward, see AUTHORS for details.
:license: Apache License, Version 2.0, see LICENSE for details.
"""
from types import SimpleNamespace
from pathlib import Path

from addmeta import cli as addmeta_cli
from addmeta.cli import resolve_relative_paths


class AddMeta:
    """Add metadata to model output directories using the addmeta tool"""

    default_options = {
        'enable': True,
        'verbose': False,
        'update_history': False,
        'data': {},
        'metafiles': [],
        'datafiles': [],
        'fnregex': '',
        'datavar': {},
        'metalist': '',
        'sort': True,
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
        # namespace except for metafiles and datavar, which should be combined 
        # with the existing values.
        for key, value in vars(namespace).items():
            if key == 'metafiles':
                value = self.options.metafiles + value
            if key == 'datavar':
                value = self.options.datavar | value
            self.options.__setattr__(key, value)


    def run(self, meta_dict=None, output_path=None):
        """Run the addmeta tool with the specified configuration. Pass through
          any additional metadata to be added to the output files via the 
          meta_dict argument."""

        if output_path is None:
            output_path = Path.cwd()

        # Expand globs in the files option
        self.options.files = resolve_relative_paths(self.options.files, output_path)

        addmeta_cli.main(self.options, meta_dict)