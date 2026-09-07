"""Tooling to add metata to model output directories using the
addmeta tool

:copyright: Copyright 2011 Marshall Ward, see AUTHORS for details.
:license: Apache License, Version 2.0, see LICENSE for details.
"""
"""
do
    addmeta \
        -v -s \
        -d metadata.yaml \
        -d $PAYU_CURRENT_OUTPUT_DIR/env.yaml \
        -m scripts/post-processing/addmeta/dataspec.yaml \
        -m scripts/post-processing/addmeta/${submodel}.yaml \
        --fnregex='access-esm1p6\.\w+(?:\.\dd)?\.(?P<var>\w+)\.(?P<freq>\w{2,4})(?:\.\w+)?(?:\.\d{4})?\.nc' \
        $PAYU_CURRENT_OUTPUT_DIR/${submodel}/*.nc
"""

"""
addmeta:
    enable: true                               # default
    verbose: true                              # default
    update-history: false                      # default
    data:
        id: "{{ metadata.experiment_id }}"     # default
        run_id: "{{ env.PAYU_RUN_ID }}"        # default
    metafiles:
        - metadata.yaml                        # default
        - PATH_TO_OUTPUT_DIR/env.yaml          # default
        - addmeta/dataspec.yaml
    datafiles:
        - more_metadata.yaml
    fnregex: 'access-esm1p6\.\w+(?:\.\dd)?\.(?P<var>\w+)\.(?P<freq>\w{2,4})(?:\.\w+)?(?:\.\d{4})?\.nc'
    submodel:
        ocean:
            metafiles:
                - addmeta/ocean.yaml
            fnregex: 'access-esm1p6\.\w+(?:\.\dd)?\.(?P<var>\w+)\.(?P<freq>\w{2,4})(?:\.\w+)?(?:\.\d{4})?\.nc'
        ice:
            metafiles:
                - addmeta/ice.yaml
        atmosphere:
            metafiles:
                - addmeta/atmosphere.yaml
"""

"""
    # Call signature function to add metadata to model output directories
    find_and_add_meta(
        args.files,
        combine_meta(metafiles),
        kwdata,
        args.fnregex,
        sort_attrs=args.sort,
        history=history,
        verbose=verbose,
    )
"""


from collections import defaultdict
from types import SimpleNamespace

from addmeta import addmeta

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