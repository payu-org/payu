"""Experiment post-processing - creating an intake-esm datastore

:copyright: Copyright 2011 Marshall Ward, see AUTHORS for details.
:license: Apache License, Version 2.0, see LICENSE for details.
"""

# Standard
from pathlib import Path
import warnings

# Local
from payu.status import collect_expt_paths
from payu.sync import DATASTORE_NAME


class MakeIntakeDatastore():
    """Class used for generating intake-esm datastores"""

    def __init__(self, expt):
        self.expt = expt

    def run(self):
        """
        Generate an intake-esm datastore for the experiment output.

        The datastore is built in the sync destination if syncing is
        enabled, otherwise it is built in the archive directory.
        """

        try:
            import access_nri_intake.source.builders as builders
            from access_nri_intake.experiment import use_datastore
        except ImportError:
            warnings.warn(
                "access-nri-intake-catalog not found, "
                "skipping datastore generation"
            )
            return

        builder_map = {
            'access': builders.AccessEsm15Builder,
            'access-esm1.6': builders.AccessEsm16Builder,
            'access-om2': builders.AccessOm2Builder,
            'access-om3': builders.AccessOm3Builder,
            'mom': builders.Mom6Builder
        }

        builder = builder_map.get(self.expt.model_name)
        if builder is None:
            warnings.warn(
                f"No intake datastore builder found for "
                f"{self.expt.model_name}, skipping datastore generation"
            )
            return

        expt_paths = collect_expt_paths(self.expt)

        sync_config = self.expt.config.get('sync', {})
        if sync_config.get('enable', False):
            datastore_path = expt_paths['sync_path']
            # Remove any datastore left behind in the archive directory
            # (e.g. built before syncing was enabled) 
            remove_datastore(expt_paths['archive_path'])
        else:
            datastore_path = expt_paths['archive_path']

        description = (
            f"intake-esm datastore for experiment "
            f"{expt_paths['experiment_name']} "
            f"({expt_paths['experiment_uuid']})"
        )

        builder_kwargs = {}
        if issubclass(builder, builders.AccessEsm15Builder):
            # AccessEsm15Builder/AccessEsm16Builder require an explicit
            # `ensemble` argument
            builder_kwargs['ensemble'] = False

        use_datastore(
            experiment_dir=datastore_path,
            description=description,
            builder=builder,
            builder_kwargs=builder_kwargs
        )


def remove_datastore(directory):
    """Remove any existing datastore files (json, csv and hash) from
    `directory`, if present."""
    directory = Path(directory)
    # Also matches the "<name>_invalid_assets_<timestamp>.csv" file
    # use_datastore() writes if some assets fail to parse.
    patterns = [f"{DATASTORE_NAME}*", f".{DATASTORE_NAME}*"]
    for pattern in patterns:
        for path in directory.glob(pattern):
            path.unlink()
