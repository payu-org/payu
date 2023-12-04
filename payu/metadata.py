"""Payu experiment UUID and metadata support

Generates and commit a new experiment uuid and updates/creates experiment
metadata

:copyright: Copyright 2011 Marshall Ward, see AUTHORS for details.
:license: Apache License, Version 2.0, see LICENSE for details.
"""

import warnings
import shutil
import uuid
from pathlib import Path
from typing import Optional, List

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

from payu.fsops import read_config, mkdir_p
from payu.git_utils import get_git_branch, get_git_user_info, git_commit

# A truncated uuid is used for branch-uuid aware experiment names
TRUNCATED_UUID_LENGTH = 8

# Metadata file field names
UUID_FIELD = "experiment_uuid"
PARENT_UUID_FIELD = "parent_experiment"
CONTACT_FIELD = "contact"
EMAIL_FIELD = "email"
METADATA_FILENAME = "metadata.yaml"


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
        self.lab_archive_path = laboratory_archive_path
        self.config = read_config(config_path)

        if control_path is None:
            control_path = Path(self.config.get("control_path"))
        self.control_path = control_path
        self.filepath = self.control_path / METADATA_FILENAME

        self.branch = branch
        self.branch_uuid_experiment = True

        # Set uuid if in metadata file
        metadata = self.read_file()
        self.uuid = metadata.get(UUID_FIELD, None)

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

    def setup(self, keep_uuid: bool = False,
              is_new_experiment: bool = False) -> None:
        """Set UUID and experiment name, create/update metadata file,
        commit any changes and copy metadata file to the experiment archive.

        Parameters:
            keep_uuid: bool, default False
                Keep pre-existing UUID, if it exists.
            is_new_experiment: bool, default False
                If not keep_uuid, generate a new_uuid and a branch-uuid aware
                experiment name.
        Return: None

        Note: Experiment name is the name used for the work and archive
        directories in the Laboratory.
        """
        self.set_uuid_and_experiment_name(keep_uuid=keep_uuid,
                                          is_new_experiment=is_new_experiment)
        self.update_file()
        self.commit_file()
        self.copy_to_archive()

    def set_uuid_and_experiment_name(self,
                                     is_new_experiment: bool = False,
                                     keep_uuid: bool = False) -> None:
        """Set experiment name and UUID"""
        if self.uuid is not None and (keep_uuid or not is_new_experiment):
            self.set_experiment_name(keep_uuid=keep_uuid,
                                     is_new_experiment=is_new_experiment)
        else:
            if self.uuid is None and not is_new_experiment:
                warnings.warn("No experiment uuid found in metadata. "
                              "Generating a new uuid", MetadataWarning)
            self.set_new_uuid(is_new_experiment=is_new_experiment)

    def get_branch_uuid_experiment_name(self) -> Path:
        """Return a Branch-UUID aware experiment name"""
        if self.branch is None:
            self.branch = get_git_branch(self.control_path)

        # Add branch and a truncated uuid to control directory name
        truncated_uuid = self.uuid[:TRUNCATED_UUID_LENGTH]
        if self.branch is None or self.branch in ('main', 'master'):
            suffix = f'-{truncated_uuid}'
        else:
            suffix = f'-{self.branch}-{truncated_uuid}'

        return self.control_path.name + suffix

    def set_experiment_name(self,
                            is_new_experiment: bool = False,
                            keep_uuid: bool = False) -> None:
        """Set experiment name - this is used for work and archive
        sub-directories in the Laboratory"""
        if self.config_experiment_name is not None:
            # The configured value over-rides the experiment name
            self.experiment_name = self.config_experiment_name
            self.branch_uuid_experiment = False
            print(f"Experiment name is configured in config.yaml: ",
                  self.experiment_name)
            return

        # Branch-UUID experiment name and archive path
        branch_uuid_experiment_name = self.get_branch_uuid_experiment_name()
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

    def update_file(self) -> None:
        """Write any updates to metadata file"""
        metadata = self.read_file()

        # Update UUID and parent UUID
        parent_uuid = metadata.get(UUID_FIELD, None)
        if parent_uuid is not None and parent_uuid != self.uuid:
            metadata[PARENT_UUID_FIELD] = parent_uuid
        metadata[UUID_FIELD] = self.uuid

        # Update email/contact in metadata
        self.update_user_info(metadata=metadata,
                              metadata_key=CONTACT_FIELD,
                              config_key='name',
                              filler_values=['Your name',
                                             'Add your name here'])

        self.update_user_info(metadata=metadata,
                              metadata_key=EMAIL_FIELD,
                              config_key='email',
                              filler_values=['you@example.com',
                                             'Add your email address here'])

        # Write updated metadata to file
        YAML().dump(metadata, self.filepath)

    def update_user_info(self, metadata: CommentedMap, metadata_key: str,
                         config_key: str, filler_values=List[str]):
        """Add user email/name to metadata - if defined and not already set
        in metadata"""
        example_value = filler_values[0]
        filler_values = {value.casefold() for value in filler_values}
        if (metadata_key not in metadata
                or metadata[metadata_key] is None
                or metadata[metadata_key].casefold() in filler_values):
            # Get config value from git
            value = get_git_user_info(repo_path=self.control_path,
                                      config_key=config_key,
                                      example_value=example_value)
            if value is not None:
                metadata[metadata_key] = value

    def commit_file(self) -> None:
        """Add a git commit for changes to metadata file, if file has changed
        and if control path is a git repository"""
        commit_message = f"Updated metadata. Experiment UUID: {self.uuid}"
        git_commit(repo_path=self.control_path,
                   commit_message=commit_message,
                   paths_to_commit=[self.filepath],
                   initialise_repo=False)

    def copy_to_archive(self) -> None:
        """Copy metadata file to archive"""
        archive_path = self.lab_archive_path / self.experiment_name
        mkdir_p(archive_path)
        shutil.copy(self.filepath, archive_path / METADATA_FILENAME)
        # Note: The existence of archive path is also used for determining
        # experiment names and whether to generate a new UUID


def generate_uuid() -> str:
    """Generate a new uuid"""
    return str(uuid.uuid4())
