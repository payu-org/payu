"""Run the `payu ghsetup` command.

:copyright: Copyright 2018 Marshall Ward, see AUTHORS for details.
:license: Apache License, Version 2.0, see LICENSE for details.
"""

from payu.experiment import Experiment
from payu.laboratory import Laboratory
from payu.runlog import Runlog
import payu.subcommands.args as args

title = 'ghsetup'
parameters = {'description': 'Create authentication keys for github'}

arguments = [args.model, args.config, args.laboratory]


def runcmd(model_type, config_path, lab_path):
    """Execute the command."""
    lab = Laboratory(model_type, config_path, lab_path)
    expt = Experiment(lab)
    runlog = Runlog(expt)

    runlog.github_setup()


runscript = runcmd
