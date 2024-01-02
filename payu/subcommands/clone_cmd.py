"""Run the `payu clone` command.

:copyright: Copyright 2018 Marshall Ward, see AUTHORS for details.
:license: Apache License, Version 2.0, see LICENSE for details.
"""

from pathlib import Path

from payu.branch import clone
import payu.subcommands.args as args

title = 'clone'
parameters = {'description': ('A wrapper around git clone. Clones a '
                              'control repository and setup new experiment '
                              'metadata')}

arguments = [args.model, args.config, args.laboratory,
             args.keep_uuid, args.clone_branch,
             args.repository, args.local_directory,
             args.new_branch_name, args.restart_path,
             args.parent_experiment]


def transform_strings_to_path(path_str=None):
    return Path(path_str) if path_str is not None else None


def runcmd(model_type, config_path, lab_path, keep_uuid,
           branch, repository, local_directory, new_branch_name, restart_path,
           parent_experiment):
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
          parent_experiment=parent_experiment)


runscript = runcmd
