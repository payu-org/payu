"""Run the `payu checkout` command.

:copyright: Copyright 2018 Marshall Ward, see AUTHORS for details.
:license: Apache License, Version 2.0, see LICENSE for details.
"""
from argparse import RawDescriptionHelpFormatter
from pathlib import Path

from payu.branch import checkout_branch
import payu.subcommands.args as args

title = 'checkout'
parameters = {
    "description": (
        "A wrapper around git checkout. Create a new branch (if specified), "
        "checkout branch, setup experiment metadata and "
        "create/switch archive/work symlinks"
    ),
    "epilog": (
        "Example usage:\n"
        "\n  To checkout an existing git branch:\n"
        "    payu checkout <branch_name>\n"
        "\n  To create a new branch from an existing branch:\n"
        "    payu checkout -b <new_branch_name> <existing_branch_name>\n"
        "\n  To create a new branch from an existing commit or tag:\n"
        "    payu checkout -b <new_branch_name> <commit_or_tag>\n"
        "\n  To checkout a new branch, and specify a restart path to start from:\n"
        "    payu checkout -r <path_to_restart_dir> -b <new_branch_name>"
    ),
    "formatter_class": RawDescriptionHelpFormatter,
}

arguments = [args.model, args.config, args.laboratory, args.new_branch,
             args.branch_name, args.start_point, args.restart_path,
             args.keep_uuid, args.parent_experiment]


def transform_strings_to_path(path_str=None):
    return Path(path_str) if path_str is not None else None


def runcmd(model_type, config_path, lab_path, new_branch,
           branch_name, start_point,
           restart_path, keep_uuid, parent_experiment):
    """Execute the command."""
    config_path = transform_strings_to_path(config_path)
    lab_path = transform_strings_to_path(lab_path)
    restart_path = transform_strings_to_path(restart_path)

    checkout_branch(is_new_branch=new_branch,
                    branch_name=branch_name,
                    start_point=start_point,
                    restart_path=restart_path,
                    config_path=config_path,
                    lab_path=lab_path,
                    model_type=model_type,
                    keep_uuid=keep_uuid,
                    parent_experiment=parent_experiment)


runscript = runcmd
