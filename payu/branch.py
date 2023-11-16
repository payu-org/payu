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

from payu.fsops import read_config, DEFAULT_CONFIG_FNAME
from payu.laboratory import Laboratory
from payu.metadata import Metadata
from payu.git_utils import git_checkout_branch, git_clone, get_git_branch


def add_restart_to_config(restart_path: Path,
                          config_path: Optional[Path] = None) -> None:
    """Takes restart path and config path, and add 'restart' flag to the
    config file - which is used to start a run if there isn't a pre-existing
    restart in archive"""
    if config_path is None:
        config_path = Path(DEFAULT_CONFIG_FNAME)
        config_path.resolve()

    # Check for valid paths
    skip_msg = f"Skipping adding 'restart: {restart_path}' to config file"
    if not config_path.exists() or not config_path.is_file:
        warnings.warn(f"Given configuration file {config_path} does not "
                      "exist. " + skip_msg)
        return
    if not restart_path.exists() or not restart_path.is_dir():
        warnings.warn((f"Given restart directory {restart_path} does not "
                       "exist. " + skip_msg))
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


def checkout_branch(lab: Laboratory,
                    branch_name: str,
                    is_new_branch: bool = False,
                    is_new_experiment: bool = False,
                    start_point: Optional[str] = None,
                    restart_path: Optional[Path] = None,
                    config_path: Optional[Path] = None) -> None:
    """Checkout branch"""
    # Note: Control path is set in read_config
    config = read_config(config_path)
    control_path = Path(config.get('control_path'))

    # Checkout branch
    git_checkout_branch(control_path, branch_name, is_new_branch, start_point)

    metadata = Metadata(lab, branch=branch_name, config_path=config_path)
    if is_new_branch or is_new_experiment:
        # Creates new uuid, experiment name, updates and commit metadata file
        metadata.setup_new_experiment()
    else:
        # Setup metadata if there is no uuid, otherwise check existing metadata
        # and commit any changes
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

    # Create symlink, if directory exists in laboratory
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

    # Resolve directory to an absolute path and cd into cloned directory
    previous_directory = os.getcwd()
    dir_path = directory.resolve()
    os.chdir(directory)

    # Initial lab and metadata
    lab = Laboratory(model_type, config_path, lab_path)

    # Use checkout wrapper
    if new_branch_name is not None:
        # Create and checkout new branch
        checkout_branch(lab=lab,
                        is_new_branch=True,
                        branch_name=new_branch_name,
                        restart_path=restart_path,
                        config_path=config_path)
    else:
        # Checkout branch
        if branch is None:
            branch = get_git_branch(dir_path)

        checkout_branch(lab=lab,
                        branch_name=branch,
                        config_path=config_path,
                        is_new_experiment=not keep_uuid,
                        restart_path=restart_path)
        # Note: is_new_experiment ensures new uuid and metadata is created
        # Otherwise uuid is generated only if there's no pre-existing uuid

    # Change back to previous directory
    os.chdir(previous_directory)
