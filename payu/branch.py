"""Experiment branch support for payu's branch, clone and checkout commands

This may generate new experiment ID, updates, sets any
specified configuration in config.yaml and updates work/archive symlinks

:copyright: Copyright 2011 Marshall Ward, see AUTHORS for details.
:license: Apache License, Version 2.0, see LICENSE for details.
"""

import os
import warnings
from pathlib import Path
from typing import Optional

from ruamel.yaml import YAML
import git

from payu.fsops import read_config, DEFAULT_CONFIG_FNAME
from payu.laboratory import Laboratory
from payu.metadata import Metadata
from payu.git_utils import git_checkout_branch, git_clone, get_git_branch
from payu.git_utils import get_git_repository
from payu.git_utils import remote_branches_dict, local_branches_dict

NO_CONFIG_FOUND_MESSAGE = """No configuration file found on this branch.
Skipping adding new metadata file and creating archive/work symlinks.

To find a branch that has config file, you can:
    - Display local branches by running:
        payu branch
    - Or display remote branches by running:
        payu branch --remote

To checkout an existing branch, run:
    payu checkout BRANCH_NAME
Where BRANCH_NAME is the name of the branch"""


def add_restart_to_config(restart_path: Path,
                          config_path: Path) -> None:
    """Takes restart path and config path, and add 'restart' flag to the
    config file - which is used to start a run if there isn't a pre-existing
    restart in archive"""

    # Check for valid paths
    if not restart_path.exists() or not restart_path.is_dir():
        warnings.warn((f"Given restart directory {restart_path} does not "
                       f"exist. Skipping adding 'restart: {restart_path}' "
                       "to config file"))
        return

    # Default ruamel yaml preserves comments and multiline strings
    yaml = YAML()
    config = yaml.load(config_path)

    # Add in restart path
    config['restart'] = str(restart_path)

    # Write modified lines back to config
    yaml.dump(config, config_path)
    print(f"Added 'restart: {restart_path}' to configuration file:",
          config_path.name)


def get_control_path(config_path: Path) -> Path:
    """Given the config path, return the control path"""
    # Note: Control path is set in read_config
    config = read_config(config_path)
    return Path(config.get('control_path'))


def check_config_path(config_path: Optional[Path] = None) -> Optional[Path]:
    """Checks if configuration file exists"""
    if config_path is None:
        config_path = Path(DEFAULT_CONFIG_FNAME)
        config_path.resolve()

    if not config_path.exists() or not config_path.is_file:
        print(NO_CONFIG_FOUND_MESSAGE)
        raise FileNotFoundError(f"Configuration file {config_path} not found")

    return config_path


def checkout_branch(branch_name: str,
                    is_new_branch: bool = False,
                    is_new_experiment: bool = False,
                    start_point: Optional[str] = None,
                    restart_path: Optional[Path] = None,
                    config_path: Optional[Path] = None,
                    control_path: Optional[Path] = None,
                    model_type: Optional[str] = None,
                    lab_path: Optional[Path] = None,) -> None:
    """Checkout branch"""
    if control_path is None:
        control_path = get_control_path(config_path)

    # Checkout branch
    git_checkout_branch(control_path, branch_name, is_new_branch, start_point)

    # Check config file exists on checked out branch
    config_path = check_config_path(config_path)

    # Initialise Lab and Metadata
    lab = Laboratory(model_type, config_path, lab_path)
    metadata = Metadata(lab, branch=branch_name, config_path=config_path)

    if is_new_branch or is_new_experiment:
        # Create new uuid, experiment name, update and commit metadata file
        metadata.setup_new_experiment()
    else:
        # Create/update metadata if no uuid, otherwise run checks on existing
        # metadata and commit any changes
        metadata.setup()
        metadata.commit_file()

    # Add restart option to config
    if restart_path:
        add_restart_to_config(restart_path, config_path=config_path)

    # Switch/Remove/Add archive and work symlinks
    experiment = metadata.experiment_name
    switch_symlink(Path(lab.archive_path), control_path, experiment, 'archive')
    switch_symlink(Path(lab.work_path), control_path, experiment, 'work')


def switch_symlink(lab_dir_path: Path, control_path: Path,
                   experiment_name: str, sym_dir: str) -> None:
    """Helper function for removing and switching work and archive
    symlinks in control directory"""
    dir_path = lab_dir_path / experiment_name
    sym_path = control_path / sym_dir

    # Remove symlink if it already exists
    if sym_path.exists() and sym_path.is_symlink:
        previous_path = sym_path.resolve()
        sym_path.unlink()
        print(f"Removed {sym_dir} symlink to {previous_path}")

    # Create symlink, if experiment directory exists in laboratory
    if dir_path.exists():
        sym_path.symlink_to(dir_path)
        print(f"Added {sym_dir} symlink to {dir_path}")


def clone(repository: str,
          directory: Path,
          branch: Optional[Path] = None,
          new_branch_name: Optional[str] = None,
          keep_uuid: bool = False,
          model_type: Optional[str] = None,
          config_path: Optional[Path] = None,
          lab_path: Optional[Path] = None,
          restart_path: Optional[Path] = None) -> None:
    """Clone an experiment control repo"""
    # git clone the repository
    git_clone(repository, directory, branch)

    # Resolve directory to an absolute path
    control_path = directory.resolve()

    owd = os.getcwd()
    try:
        # cd into cloned directory
        os.chdir(control_path)

        # Use checkout wrapper
        if new_branch_name is not None:
            # Create and checkout new branch
            checkout_branch(is_new_branch=True,
                            branch_name=new_branch_name,
                            restart_path=restart_path,
                            config_path=config_path,
                            control_path=control_path,
                            model_type=model_type,
                            lab_path=lab_path)
        else:
            # Checkout branch
            if branch is None:
                branch = get_git_branch(control_path)

            checkout_branch(branch_name=branch,
                            config_path=config_path,
                            is_new_experiment=not keep_uuid,
                            restart_path=restart_path,
                            control_path=control_path,
                            model_type=model_type,
                            lab_path=lab_path)
            # Note: is_new_experiment ensures new uuid and metadata is created
            # Otherwise uuid is generated only if there's no pre-existing uuid
    finally:
        # Change back to original working directory
        os.chdir(owd)

    print(f"To change directory to control directory run:\n  cd {directory}")


def print_branch_metadata(branch: git.Head, verbose: bool = False):
    """Print uuid for each branch. If verbose is true, it will print all lines
    of the metadata file"""
    contains_config = False
    metadata_content = None
    # Note: Blobs are files in the commit tree
    for blob in branch.commit.tree.blobs:
        if blob.name == 'config.yaml':
            contains_config = True
        if blob.name == 'metadata.yaml':
            # Read file contents
            metadata_content = blob.data_stream.read().decode('utf-8')

    # Print branch info
    if not contains_config:
        print(f"    No config file found")
    elif metadata_content is None:
        print("    No metadata file found")
    else:
        if verbose:
            # Print all metadata
            for line in metadata_content.splitlines():
                print(f'    {line}')
        else:
            # Print uuid
            metadata = YAML().load(metadata_content)
            uuid = metadata.get('uuid', None)
            if uuid is not None:
                print(f"    uuid: {uuid}")
            else:
                print(f"    No uuid in metadata file")


def list_branches(config_path: Optional[Path] = None,
                  verbose: bool = False,
                  remote: bool = False):
    """Print uuid, or metadata if verbose, for each branch in control repo"""
    control_path = get_control_path(config_path)
    repo = get_git_repository(control_path)

    current_branch = repo.active_branch
    print(f"* Current Branch: {current_branch.name}")
    print_branch_metadata(current_branch, verbose)

    if remote:
        branches = remote_branches_dict(repo)
        label = "Remote Branch"
    else:
        branches = local_branches_dict(repo)
        label = "Branch"

    for branch_name, branch in branches.items():
        if branch != current_branch:
            print(f"{label}: {branch_name}")
            print_branch_metadata(branch, verbose)
