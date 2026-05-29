"""Run the `payu branch` command.

:copyright: Copyright 2018 Marshall Ward, see AUTHORS for details.
:license: Apache License, Version 2.0, see LICENSE for details.
"""

from pathlib import Path

from payu import cli
from payu.branch import list_branches
import payu.subcommands.args as args

title = 'branch'
parameters = {'description': ('List git branches and corresponding metadata')}

arguments = [args.config, args.verbose, args.remote, args.stacktrace]


def runcmd(config_path, verbose, remote, stacktrace=None):
    """Execute the command."""
    # Configure stacktrace settings based on arguments
    cli.set_stacktrace_runscript(stacktrace)
    
    config_path = Path(config_path) if config_path is not None else None
    list_branches(config_path, verbose, remote)


runscript = runcmd
