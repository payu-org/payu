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
import shutil

from ruamel.yaml import YAML, CommentedMap, constructor
import git

from payu.fsops import read_config, DEFAULT_CONFIG_FNAME, list_archive_dirs
from payu.laboratory import Laboratory
from payu.metadata import Metadata, UUID_FIELD, METADATA_FILENAME
from payu.git_utils import GitRepository, git_clone, PayuBranchError


NO_CONFIG_FOUND_MESSAGE = """No configuration file found on this branch.
Skipping adding new metadata file and creating archive/work symlinks.

To find a branch that has a config file, you can:
    - Display local branches by running:
        payu branch
    - Or display remote branches by running:
        payu branch --remote

To checkout an existing branch, run:
    payu checkout BRANCH_NAME
Where BRANCH_NAME is the name of the branch"""


def check_restart(restart_path: Optional[Path],
                  archive_path: Path) -> Optional[Path]:
    """Checks for valid prior restart path. Returns resolved restart path
    if valid, otherwise returns None"""

    # Check for valid path
    if not restart_path.exists():
        warnings.warn((f"Given restart path {restart_path} does not "
                       f"exist. Skipping setting 'restart' in config file"))
        return

    # Resolve to absolute path
    restart_path = restart_path.resolve()

    # Check for pre-existing restarts in archive
    if archive_path.exists():
        if len(list_archive_dirs(archive_path, dir_type="restart")) > 0:
            warnings.warn((
                f"Pre-existing restarts found in archive: {archive_path}."
                f"Skipping adding 'restart: {restart_path}' to config file"))
            return

    return restart_path


def add_restart_to_config(restart_path: Path, config_path: Path) -> None:
    """Takes restart path and config path, and add 'restart' flag to the
    config file - which is used to start a run if there isn't a pre-existing
    restart in archive"""

    # Default ruamel yaml preserves comments and multiline strings
    try:
        yaml = YAML()
        config = yaml.load(config_path)
    except constructor.DuplicateKeyError as e:
        # PyYaml which is used to read config allows duplicate keys
        # These will get removed when the configuration file is modified
        warnings.warn(
            "Removing any subsequent duplicate keys from config.yaml"
        )
        yaml = YAML()
        yaml.allow_duplicate_keys = True
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
                    keep_uuid: bool = False,
                    start_point: Optional[str] = None,
                    restart_path: Optional[Path] = None,
                    config_path: Optional[Path] = None,
                    control_path: Optional[Path] = None,
                    model_type: Optional[str] = None,
                    lab_path: Optional[Path] = None,
                    parent_experiment: Optional[str] = None) -> None:
    """Checkout branch, setup metadata and add symlinks

    Parameters
    ----------
    branch_name : str
        Name of branch to checkout/create
    is_new_branch: bool, default False
        Create new branch and mark as new experiment
    is_new_experiment: bool, default False
        Create new uuid for this experiment
    keep_uuid: bool, default False
        Keep UUID unchanged, if it exists - this overrides is_new_experiment
        if there is a pre-existing UUID
    start_point: Optional[str]
        Branch name or commit hash to start new branch from
    restart_path: Optional[Path]
        Absolute restart path to start experiment from
    config_path: Optional[Path]
        Path to configuration file - config.yaml
    control_path: Optional[Path]
        Path to control directory - defaults to current working directory
    model_type: Optional[str]
        Type of model - used for creating a Laboratory
    lab_path: Optional[Path]
        Path to laboratory directory
    parent_experiment: Optional[str]
        Parent experiment UUID to add to generated metadata
    """
    if control_path is None:
        control_path = get_control_path(config_path)

    # Checkout branch
    repo = GitRepository(control_path)
    repo.checkout_branch(branch_name, is_new_branch, start_point)

    # Check config file exists on checked out branch
    config_path = check_config_path(config_path)

    # Initialise Lab and Metadata
    lab = Laboratory(model_type, config_path, lab_path)
    metadata = Metadata(Path(lab.archive_path),
                        branch=branch_name,
                        config_path=config_path)

    # Setup Metadata
    is_new_experiment = is_new_experiment or is_new_branch
    metadata.setup(keep_uuid=keep_uuid,
                   is_new_experiment=is_new_experiment)

    # Gets valid prior restart path
    prior_restart_path = None
    if restart_path:
        prior_restart_path = check_restart(restart_path=restart_path,
                                           archive_path=metadata.archive_path)

    # Create/update and commit metadata file
    metadata.write_metadata(set_template_values=True,
                            restart_path=prior_restart_path,
                            parent_experiment=parent_experiment)

    # Add restart option to config
    if prior_restart_path:
        add_restart_to_config(prior_restart_path, config_path=config_path)

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
          branch: Optional[str] = None,
          new_branch_name: Optional[str] = None,
          keep_uuid: bool = False,
          model_type: Optional[str] = None,
          config_path: Optional[Path] = None,
          lab_path: Optional[Path] = None,
          restart_path: Optional[Path] = None,
          parent_experiment: Optional[str] = None) -> None:
    """Clone an experiment control repository.

    Parameters:
        repository: str
            Git URL or path to Git repository to clone
        directory: Path
            The control directory where the repository will be cloned
        branch: Optional[str]
            Name of branch to clone and checkout
        new_branch_name: Optional[str]
            Name of new branch to create and checkout.
            If branch is also defined, the new branch will start from the
            latest commit of the branch.
        keep_uuid: bool, default False
            Keep UUID unchanged, if it exists
        config_path: Optional[Path]
            Path to configuration file - config.yaml
        control_path: Optional[Path]
            Path to control directory - defaults to current working directory
        model_type: Optional[str]
            Type of model - used for creating a Laboratory
        lab_path: Optional[Path]
            Path to laboratory directory
        restart_path: Optional[Path]
            Absolute restart path to start experiment from
        parent_experiment: Optional[str]
            Parent experiment UUID to add to generated metadata

    Returns: None
    """
    # Resolve directory to an absolute path
    control_path = directory.resolve()

    if control_path.exists():
        raise PayuBranchError(
            f"Directory path `{control_path}` already exists. "
            "Clone to a different path, or cd into the existing directory " +
            "and use `payu checkout` if it is the same git repository"
        )

    # git clone the repository
    repo = git_clone(repository, control_path, branch)

    owd = os.getcwd()
    try:
        # cd into cloned directory
        os.chdir(control_path)

        # Use checkout wrapper
        if new_branch_name is not None:
            # Create and checkout new branch
            checkout_branch(is_new_branch=True,
                            keep_uuid=keep_uuid,
                            branch_name=new_branch_name,
                            restart_path=restart_path,
                            config_path=config_path,
                            control_path=control_path,
                            model_type=model_type,
                            lab_path=lab_path,
                            parent_experiment=parent_experiment)
        else:
            # Checkout branch
            if branch is None:
                branch = repo.get_branch_name()

            checkout_branch(branch_name=branch,
                            config_path=config_path,
                            keep_uuid=keep_uuid,
                            restart_path=restart_path,
                            control_path=control_path,
                            model_type=model_type,
                            lab_path=lab_path,
                            is_new_experiment=True,
                            parent_experiment=parent_experiment)
    except PayuBranchError as e:
        # Remove directory if incomplete checkout
        shutil.rmtree(control_path)
        msg = (
            "Incomplete checkout. To run payu clone again, modify/remove " +
            "the checkout new branch flag: --new-branch/-b, or " +
            "checkout existing branch flag: --branch/-B " +
            f"\n  Checkout error: {e}"
        )
        raise PayuBranchError(msg)
    finally:
        # Change back to original working directory
        os.chdir(owd)

    print(f"To change directory to control directory run:\n  cd {directory}")


def get_branch_metadata(branch: git.Head) -> Optional[CommentedMap]:
    """Return dictionary of branch metadata if it exists, None otherwise"""
    for blob in branch.commit.tree.blobs:
        if blob.name == METADATA_FILENAME:
            # Read file contents
            metadata_content = blob.data_stream.read().decode('utf-8')
            return YAML().load(metadata_content)


def contains_config(branch: git.Head) -> bool:
    """Checks if config file in defined in given branch"""
    contains_config = False
    for blob in branch.commit.tree.blobs:
        if blob.name == DEFAULT_CONFIG_FNAME:
            contains_config = True
    return contains_config


def print_branch_metadata(branch: git.Head, verbose: bool = False):
    """Display given Git branch UUID, or if config.yaml or metadata.yaml does
    not exist.

    Parameters:
        branch: git.Head
            Branch object to parse commit tree.
        verbose: bool, default False
            Display entire metadata files
        remote: bool, default False
            Display remote Git branches

    Returns: None
    """
    # Print branch info
    if not contains_config(branch):
        print(f"    No config file found")
        return

    metadata = get_branch_metadata(branch)

    if metadata is None:
        print("    No metadata file found")
        return

    if verbose:
        # Print all non-null metadata values
        for key, value in metadata.items():
            if value:
                print(f'    {key}: {value}')
    else:
        # Print uuid
        uuid = metadata.get(UUID_FIELD, None)
        if uuid is not None:
            print(f"    {UUID_FIELD}: {uuid}")
        else:
            print(f"    No UUID in metadata file")


def list_branches(config_path: Optional[Path] = None,
                  verbose: bool = False,
                  remote: bool = False):
    """Display local Git branches UUIDs.

    Parameters:
        verbose: bool, default False
            Display entire metadata files
        remote: bool, default False
            Display remote Git branches

    Returns: None"""
    control_path = get_control_path(config_path)
    git_repo = GitRepository(control_path)

    current_branch = git_repo.repo.active_branch
    print(f"* Current Branch: {current_branch.name}")
    print_branch_metadata(current_branch, verbose)

    if remote:
        branches = git_repo.remote_branches_dict()
        label = "Remote Branch"
    else:
        branches = git_repo.local_branches_dict()
        label = "Branch"

    for branch_name, branch in branches.items():
        if branch != current_branch:
            print(f"{label}: {branch_name}")
            print_branch_metadata(branch, verbose)
