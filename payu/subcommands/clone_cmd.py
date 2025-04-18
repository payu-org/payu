"""Run the `payu clone` command.

:copyright: Copyright 2018 Marshall Ward, see AUTHORS for details.
:license: Apache License, Version 2.0, see LICENSE for details.
"""

from argparse import RawDescriptionHelpFormatter
from pathlib import Path

from payu.branch import clone
import payu.subcommands.args as args

title = 'clone'
parameters = {
    'description': (
        'A wrapper around git clone. Clones a control repository and setup '
        'new experiment metadata'
    ),
    'epilog': (
        'Example usage:\n'
        '\n  To clone repository and checkout an existing git branch:\n'
        '    payu clone -B <branch_name> <repository> <local_directory>\n'
        '\n  To clone and create a new branch from an existing branch:\n'
        '    payu clone -B <branch_name> -b <new_branch_name> <repository> <local_directory>\n'
        '\n  To clone and create a new branch from an existing commit or tag:\n'
        '    payu clone -s <commit_or_tag> -b <new_branch_name> <repository> <local_directory>\n'
        '\n  To clone and checkout a new branch, and specify a restart path to start from:\n'
        '    payu clone -b <new_branch_name> -r <path_to_restart_dir> <repository> <local_directory>\n'
    ),
    'formatter_class': RawDescriptionHelpFormatter,
}

arguments = [args.model, args.config, args.laboratory,
             args.keep_uuid, args.clone_branch,
             args.repository, args.local_directory,
             args.new_branch_name, args.restart_path,
             args.parent_experiment, args.clone_start_point]


def transform_strings_to_path(path_str=None):
    return Path(path_str) if path_str is not None else None


def runcmd(model_type, config_path, lab_path, keep_uuid,
           branch, repository, local_directory, new_branch_name, restart_path,
           parent_experiment, start_point):
    """Execute the command."""
    config_path = transform_strings_to_path(config_path)
    restart_path = transform_strings_to_path(restart_path)
    lab_path = transform_strings_to_path(lab_path)
    directory = transform_strings_to_path(local_directory)

    clone(repository=repository,
          directory=directory,
          branch=branch,
          keep_uuid=keep_uuid,
          model_type=model_type,
          config_path=config_path,
          lab_path=lab_path,
          new_branch_name=new_branch_name,
          restart_path=restart_path,
          parent_experiment=parent_experiment,
          start_point=start_point)


runscript = runcmd
