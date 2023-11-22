"""Run the `payu checkout` command.

:copyright: Copyright 2018 Marshall Ward, see AUTHORS for details.
:license: Apache License, Version 2.0, see LICENSE for details.
"""

from payu.branch import list_branches
import payu.subcommands.args as args

title = 'branch'
parameters = {'description': ('List git branches and corresponding metadata')}

arguments = [args.config, args.verbose]


def runcmd(config_path, verbose):
    """Execute the command."""
    list_branches(config_path, verbose)

runscript = runcmd