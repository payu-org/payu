"""Run the `payu uuid` command.

:copyright: Copyright 2018 Marshall Ward, see AUTHORS for details.
:license: Apache License, Version 2.0, see LICENSE for details.
"""

import payu.subcommands.args as args
from payu.metadata import Metadata
from payu.laboratory import Laboratory

title = 'uuid'
parameters = {'description': ('Generates and commits a new experiment uuid, '
                              'update/create and commit experiment metadata')}
arguments = [args.model, args.config, args.laboratory, args.legacy_experiment]


def runcmd(model_type, config_path, lab_path, legacy_experiment):
    """Execute the command."""
    lab = Laboratory(model_type=model_type,
                     config_path=config_path,
                     lab_path=lab_path)
    metadata = Metadata(lab=lab, config_path=config_path)

    metadata.setup_new_experiment(legacy=legacy_experiment)


runscript = runcmd
