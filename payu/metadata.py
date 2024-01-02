"""Payu experiment UUID and metadata support

Generates and commit a new experiment uuid and updates/creates experiment
metadata

:copyright: Copyright 2011 Marshall Ward, see AUTHORS for details.
:license: Apache License, Version 2.0, see LICENSE for details.
"""

import requests
import shutil
import uuid
import warnings
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

from payu.fsops import read_config, mkdir_p
from payu.git_utils import GitRepository

# A truncated uuid is used for branch-uuid aware experiment names
TRUNCATED_UUID_LENGTH = 8

# Metadata file field names
UUID_FIELD = "experiment_uuid"
PARENT_UUID_FIELD = "parent_experiment"
CONTACT_FIELD = "contact"
EMAIL_FIELD = "email"
NAME_FIELD = "name"
GIT_URL_FIELD = "url"
CREATED_FIELD = "created"
MODEL_FIELD = "model"
METADATA_FILENAME = "metadata.yaml"

# Metadata Schema
SCHEMA_URL = "https://raw.githubusercontent.com/ACCESS-NRI/schema/main/experiment_asset.json"


class MetadataWarning(Warning):
    pass


class Metadata:
    """
    Class to store/update/create metadata such as experiment uuid and name

    Parameters:
        laboratory_archive_path : Path
            The archive sub-directory in Laboratory
        branch : Optional[str]
            The git branch on which the experiment is run
        control_path : Optional[Path]
            Path to where the experiment is configured and run. The default
            is set to the current working directory. This default is set in
            in fsops.read_config
        config_path : Optional[Path]
            Configuration Path. The default is config.yaml in the current
            working directory. This is also set in fsop.read_config
    """

    def __init__(self,
                 laboratory_archive_path: Path,
                 config_path: Optional[Path] = None,
                 branch: Optional[str] = None,
                 control_path: Optional[Path] = None) -> None:
        self.config = read_config(config_path)
        self.metadata_config = self.config.get('metadata', {})

        if control_path is None:
            control_path = Path(self.config.get("control_path"))
        self.control_path = control_path
        self.filepath = self.control_path / METADATA_FILENAME
        self.lab_archive_path = laboratory_archive_path

        # Config flag to disable creating metadata files and UUIDs
        self.enabled = self.metadata_config.get('enable', True)

        if self.enabled:
            self.repo = GitRepository(self.control_path, catch_error=True)

        self.branch = branch
        self.branch_uuid_experiment = True

        # Set uuid if in metadata file
        metadata = self.read_file()
        self.uuid = metadata.get(UUID_FIELD, None)
        self.uuid_updated = False

        # Experiment name configuration - this overrides experiment name
        self.config_experiment_name = self.config.get("experiment", None)

    def read_file(self) -> CommentedMap:
        """Read metadata file - preserving orginal format if it exists"""
        metadata = CommentedMap()
        if self.filepath.exists():
            # Use default ruamel YAML to preserve comments and multi-line
            # strings
            metadata = YAML().load(self.filepath)
        return metadata

    def setup(self,
              is_new_experiment: bool = False,
              keep_uuid: bool = False) -> None:
        """Set UUID and experiment name.

        Parameters:
            keep_uuid: bool, default False
                Keep pre-existing UUID, if it exists.
            is_new_experiment: bool, default False
                If not keep_uuid, generate a new UUID and a branch-uuid aware
                experiment name. This is set in payu.branch.checkout_branch.
        Return: None

        Note: Experiment name is the name used for the work and archive
        directories in the Laboratory.
        """
        if not self.enabled:
            # Set experiment name only - either configured or includes branch
            self.set_experiment_name(ignore_uuid=True)

        elif self.uuid is not None and (keep_uuid or not is_new_experiment):
            self.set_experiment_name(keep_uuid=keep_uuid,
                                     is_new_experiment=is_new_experiment)
        else:
            # Generate new UUID
            if self.uuid is None and not is_new_experiment:
                warnings.warn("No experiment uuid found in metadata. "
                              "Generating a new uuid", MetadataWarning)
            self.set_new_uuid(is_new_experiment=is_new_experiment)

        self.archive_path = self.lab_archive_path / self.experiment_name

    def new_experiment_name(self, ignore_uuid: bool = False) -> str:
        """Generate a new experiment name"""
        if self.branch is None:
            self.branch = self.repo.get_branch_name()

        # Add branch and a truncated uuid to control directory name
        adding_branch = self.branch not in (None, 'main', 'master')
        suffix = f'-{self.branch}' if adding_branch else ''

        if not ignore_uuid:
            truncated_uuid = self.uuid[:TRUNCATED_UUID_LENGTH]
            suffix += f'-{truncated_uuid}'

        return self.control_path.name + suffix

    def set_experiment_name(self,
                            is_new_experiment: bool = False,
                            keep_uuid: bool = False,
                            ignore_uuid: bool = False) -> None:
        """Set experiment name - this is used for work and archive
        sub-directories in the Laboratory"""
        if self.config_experiment_name is not None:
            # The configured value over-rides the experiment name
            self.experiment_name = self.config_experiment_name
            self.branch_uuid_experiment = False
            print(f"Experiment name is configured in config.yaml: ",
                  self.experiment_name)
            return

        if ignore_uuid:
            # Leave experiment UUID out of experiment name
            self.experiment_name = self.new_experiment_name(ignore_uuid=True)
            return

        # Branch-UUID experiment name and archive path
        branch_uuid_experiment_name = self.new_experiment_name()
        archive_path = self.lab_archive_path / branch_uuid_experiment_name

        # Legacy experiment name and archive path
        legacy_name = self.control_path.name
        legacy_archive_path = self.lab_archive_path / legacy_name

        if is_new_experiment or archive_path.exists():
            # Use branch-UUID aware experiment name
            self.experiment_name = branch_uuid_experiment_name
        elif legacy_archive_path.exists():
            # Use legacy CONTROL-DIR experiment name
            self.experiment_name = legacy_name
            print(f"Pre-existing archive found at: {legacy_archive_path}. "
                  f"Experiment name will remain: {legacy_name}")
            self.branch_uuid_experiment = False
        elif keep_uuid:
            # Use same experiment UUID and use branch-UUID name for archive
            self.experiment_name = branch_uuid_experiment_name
        else:
            # No archive exists - Detecting new experiment
            warnings.warn(
                "No pre-existing archive found. Generating a new uuid",
                MetadataWarning
            )
            self.set_new_uuid(is_new_experiment=True)

    def set_new_uuid(self, is_new_experiment: bool = False) -> None:
        """Generate a new uuid and set experiment name"""
        self.uuid_updated = True
        self.uuid = generate_uuid()
        self.set_experiment_name(is_new_experiment=is_new_experiment)

        # If experiment name does not include UUID, leave it unchanged
        if not self.branch_uuid_experiment:
            return

        # Check experiment name is unique in local archive
        lab_archive_path = self.lab_archive_path
        if lab_archive_path.exists():
            local_experiments = [item for item in lab_archive_path.iterdir()
                                 if item.is_dir()]
            while self.experiment_name in local_experiments:
                # Generate a new id and experiment name
                self.uuid = generate_uuid()
                self.set_experiment_name(is_new_experiment=is_new_experiment)

    def write_metadata(self,
                       restart_path: Optional[Union[Path, str]] = None,
                       set_template_values: bool = False,
                       parent_experiment: Optional[str] = None) -> None:
        """Create/update metadata file, commit any changes and
        copy metadata file to the experiment archive.

        Parameters:
            restart_path: Optional[Path]
                Prior restart path - used for finding parent metadata
            set_template_values: bool, default False
                Read schema and set metadata template values for new
                experiments
            parent_experiment: Optional[str]
                Parent experiment UUID to add to generated metadata

        Return: None

        Note: This assumes setup() has been run to set UUID and experiment name
        """
        if not self.enabled:
            # Skip creating/updating/commiting metadata
            return

        if self.uuid_updated:
            # Update metadata if UUID has changed
            restart_path = Path(restart_path) if restart_path else None
            self.update_file(restart_path=restart_path,
                             set_template_values=set_template_values,
                             parent_experiment=parent_experiment)
            self.commit_file()

        self.copy_to_archive()

    def update_file(self,
                    restart_path: Optional[Path] = None,
                    set_template_values: bool = False,
                    parent_experiment: Optional[str] = None) -> None:
        """Write any updates to metadata file"""
        metadata = self.read_file()

        # Add UUID field
        metadata[UUID_FIELD] = self.uuid

        # Update parent UUID field
        if parent_experiment is None:
            parent_experiment = self.get_parent_experiment(restart_path)
        if parent_experiment and parent_experiment != self.uuid:
            metadata[PARENT_UUID_FIELD] = parent_experiment

        # Add extra fields if new branch-uuid experiment
        # so to not over-write fields if it's a pre-existing legacy experiment
        if self.branch_uuid_experiment:
            metadata[CREATED_FIELD] = datetime.now().strftime('%Y-%m-%d')
            metadata[NAME_FIELD] = self.experiment_name
            metadata[MODEL_FIELD] = self.get_model_name()

            # Add origin git URL, if defined
            url = self.repo.get_origin_url()
            if url:
                metadata[GIT_URL_FIELD] = url

            # Add email + contact if defined in git config
            contact = self.repo.get_user_info(config_key='name')
            if contact:
                metadata[CONTACT_FIELD] = contact

            email = self.repo.get_user_info(config_key="email")
            if email:
                metadata[EMAIL_FIELD] = email

        if set_template_values:
            # Note that retrieving schema requires internet access
            add_template_metadata_values(metadata)

        # Write updated metadata to file
        YAML().dump(metadata, self.filepath)

    def get_model_name(self) -> str:
        """Get model name from config file"""
        # Use capitilised model name unless a specific model name is defined
        default_model_name = self.config.get('model').upper()
        model_name = self.metadata_config.get('model', default_model_name)
        return model_name

    def get_parent_experiment(self, prior_restart_path: Path) -> None:
        """Searches UUID in the metadata in the parent directory that
        contains the restart"""
        if prior_restart_path is None:
            return

        # Resolve to absolute path
        prior_restart_path = prior_restart_path.resolve()

        # Check for pre-existing metadata file
        base_output_directory = Path(prior_restart_path).parent
        metadata_filepath = base_output_directory / METADATA_FILENAME
        if not metadata_filepath.exists():
            return

        # Read metadata file
        parent_metadata = YAML().load(metadata_filepath)
        return parent_metadata.get(UUID_FIELD, None)

    def commit_file(self) -> None:
        """Add a git commit for changes to metadata file, if file has changed
        and if control path is a git repository"""
        commit_message = f"Updated metadata. Experiment UUID: {self.uuid}"
        self.repo.commit(commit_message=commit_message,
                         paths_to_commit=[self.filepath])

    def copy_to_archive(self) -> None:
        """Copy metadata file to archive"""
        mkdir_p(self.archive_path)
        shutil.copy(self.filepath, self.archive_path / METADATA_FILENAME)
        # Note: The existence of an archive is used for determining
        # experiment names and whether to generate a new UUID


def get_schema_from_github():
    """Retrieve metadata schema from github"""
    response = requests.get(SCHEMA_URL)

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch schema from {SCHEMA_URL}")
    return response.json() if response.status_code == 200 else {}


def add_template_metadata_values(metadata: CommentedMap) -> None:
    """Add in templates for un-set metadata values"""
    schema = get_schema_from_github()

    for key, value in schema.get('properties', {}).items():
        if key not in metadata:
            # Add field with commented description of value
            description = value.get('description', None)
            if description is not None:
                metadata[key] = None
                metadata.yaml_add_eol_comment(description, key)


def generate_uuid() -> str:
    """Generate a new uuid"""
    return str(uuid.uuid4())
