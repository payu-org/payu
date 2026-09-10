"""Tooling to add metata to model output directories using the
addmeta tool

:copyright: Copyright 2011 Marshall Ward, see AUTHORS for details.
:license: Apache License, Version 2.0, see LICENSE for details.
"""
from types import SimpleNamespace

from addmeta import cli as addmeta_cli
from addmeta import combine_meta, dict_merge, load_data_files, find_and_add_meta

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
        'datavar': [],
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

    def run(self):
        """Run the addmeta tool with the specified configuration"""

        # addmeta_cli.main(self.options)

        # Below is a copy of the main routine above to inject default metadata
        # until the addmeta tool is updated to support default metadata. 
        metafiles = []
        verbose = self.options.verbose
        kwdata = {}

        if (self.options.datafiles is not None):
            if verbose: print("datafiles: "," ".join([str(f) for f in self.options.datafiles]))
            kwdata = load_data_files(self.options.datafiles)

        # Process keyword --datavar command line arguments
        if self.options.datavar:
            if verbose: print("datavar: "," ".join([str(v) for v in self.options.datavar]))
            try:
                datavar_dict = addmeta.cli.parse_key_value_pairs(self.options.datavar)
                # Add to kwdata under 'datavar' namespace
                kwdata['__argdata__'] = datavar_dict
            except ValueError as e:
                if verbose: print(f"Error parsing datavar: {e}")
                raise

        if (self.options.metalist is not None):
            for line in self.options.metalist:
                metafiles.extend(list_from_file(line))

        if (self.options.metafiles is not None):
            metafiles.extend(self.options.metafiles)

        if verbose: print("metafiles: "," ".join([str(f) for f in metafiles]))
        
        if getattr(self.options, 'update-history', False):
            history = build_history(self.options.files)
        else:
            history = None

        # Default to always inject the experiment_uuid and run_id metadata into 
        # the output files
        metafile_default = {
            'global': {
                'experiment_uuid': "{{ metadata.experiment_uuid }}",
                'run_id': "{{ env.PAYU_RUN_ID}}",
            },
        }

        meta_dict = dict_merge(metafile_default, combine_meta(metafiles))

        find_and_add_meta(
            self.options.files,
            meta_dict,
            kwdata,
            self.options.fnregex,
            sort_attrs=self.options.sort,
            history=history,
            verbose=verbose,
        )