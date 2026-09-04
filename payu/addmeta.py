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
    submodel_options = set('metafiles', 'fnregex')

    def __init__(self, options, submodel_options=None):
        self.options = SimpleNamespace(**options)
        self.submodels = {}
        if submodel_options:
            for submodel, options in submodel_options.items():
                self.submodels[submodel] = SimpleNamespace(**options)

    @classmethod
    def from_config(cls, config):
        """Create an AddMeta instance from a configuration dictionary"""
        options = cls.default_options.copy()
        options.update(config)

        submodel_options = {}
        for submodel, submodel_config in config.get('submodel', {}).items():
            if submodel_config.get('enable', True):
                for key in cls.submodel_options:
                    if key in submodel_config:
                        submodel_options[key] = submodel_config[key]

        return cls(options, submodel_options)

    def run(self, submodel):
        """Run the addmeta tool with the specified configuration"""

        if submodel in self.submodels:
            for submodel in self.submodels:
                submodel_options = self.submodels[submodel]
                options = vars(self.options) | vars(submodel_options)

                addmeta.find_and_add_meta(
                    files=self.options.files,
                    metafiles=self.options.metafiles,
                    data=self.options.data,
                    fnregex=self.options.fnregex,
                    sort_attrs=self.options.sort,
                    history=self.options.history,
                    verbose=self.options.verbose,
                )
            
        else if self.options.files:
            addmeta.find_and_add_meta(
                files=self.options.files,
                metafiles=self.options.metafiles,
                data=self.options.data,
                fnregex=self.options.fnregex,
                sort_attrs=self.options.sort,
                history=self.options.history,
                verbose=self.options.verbose,
            )
        

def add_meta_data(expt, config):
    """Add metadata to model output directories using the addmeta tool"""

    for submodel, submodel_config in config.get('submodel', {}).items():
        if submodel_config.get('enable', True):
            addmeta_instance = AddMeta.from_config(submodel_config)
            addmeta_instance.run()  
    addmeta_instance = AddMeta.from_config(config)
    addmeta_instance.run()