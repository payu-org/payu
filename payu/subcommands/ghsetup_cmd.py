"""Run the `payu ghsetup` command.

:copyright: Copyright 2018 Marshall Ward, see AUTHORS for details.
:license: Apache License, Version 2.0, see LICENSE for details.
"""

from payu.experiment import Experiment
from payu.laboratory import Laboratory
import payu.subcommands.args as args

title = 'ghsetup'
parameters = {'description': 'Create authentication keys for GitHub'}

arguments = [args.model, args.config, args.laboratory]


def runcmd(model_type, config_path, lab_path):
    """Execute the command."""
    lab = Laboratory(model_type, config_path, lab_path)
    expt = Experiment(lab)

    if expt.runlog.enabled:
        expt.runlog.github_setup()
    else:
        print('payu: Runlog must be enabled to configure GitHub sync.')


runscript = runcmd
