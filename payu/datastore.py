"""Experiment post-processing - syncing archive to a remote directory

:copyright: Copyright 2011 Marshall Ward, see AUTHORS for details.
:license: Apache License, Version 2.0, see LICENSE for details.
"""

# Standard
import warnings

# Local
import payu.errors as errors 
from payu.status import collect_expt_paths


class MakeIntakeDatastore():
    """Class used for generating intake datastores"""

    def __init__(self, expt):
        self.expt = expt
        # self.config = self.expt.config.get('datasore', {})

        self.source_paths = []


    def run(self):
        """  
        Generate an intake datastore in the sync location
        """

        try:
            import access_nri_intake.source.builders as builders
            from access_nri_intake.experiment import use_datastore
        except ImportError:
            warnings.warn(
                "ACCESS-NR intake package not found, "
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

        if not self.expt.model_name in builder_map.keys():
            warnings.warn(
                f"No intake datastore builder found for {self.expt.model_name}, "
                " skipping datastore generation"
            )

            return

        expt_paths = collect_expt_paths(self.expt)

        description = (
            f"intake-esm datastore for experiment {expt_paths['experiment_name']} "
            f"({expt_paths['experiment_uuid']})"
        )

        use_datastore(
            experiment_dir=expt_paths["sync_path"],
            description=description, 
            builder=builders[self.expt.model_name]
        )
