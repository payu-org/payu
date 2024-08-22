import copy
import os
import shutil
from datetime import datetime

import pytest
from unittest.mock import patch, Mock
from ruamel.yaml import YAML

from payu.metadata import Metadata, MetadataWarning

from test.common import cd
from test.common import tmpdir, ctrldir, labdir, archive_dir
from test.common import config as config_orig
from test.common import write_config

verbose = True

# Global config - Remove set experiment and metadata config
config = copy.deepcopy(config_orig)
config.pop("experiment")
config.pop("metadata")

pytestmark = pytest.mark.filterwarnings(
    "ignore::payu.git_utils.PayuGitWarning")


def setup_module(module):
    """
    Put any test-wide setup code in here, e.g. creating test files
    """
    if verbose:
        print("setup_module      module:%s" % module.__name__)

    try:
        tmpdir.mkdir()
    except Exception as e:
        print(e)


def teardown_module(module):
    """
    Put any test-wide teardown code in here, e.g. removing test outputs
    """
    if verbose:
        print("teardown_module   module:%s" % module.__name__)

    try:
        shutil.rmtree(tmpdir)
        print('removing tmp')
    except Exception as e:
        print(e)


def mocked_get_git_user_info(config_key):
    if config_key == 'name':
        return 'mockUser'
    elif config_key == 'email':
        return 'mock@email.com'
    else:
        return None


@pytest.fixture(autouse=True)
def setup_and_teardown():
    try:
        ctrldir.mkdir()
        labdir.mkdir()
    except Exception as e:
        print(e)

    yield

    try:
        shutil.rmtree(ctrldir)
        shutil.rmtree(labdir)
    except Exception as e:
        print(e)


@patch("payu.metadata.GitRepository")
@pytest.mark.parametrize(
    "uuid, experiment_name, previous_metadata, expected_metadata",
    [
        # Test new metadata file created
        (
            "b1f3ce3d-99da-40e4-849a-c8b352948a31",
            "ctrl-branch-b1f3ce3d",
            None,
            {
                "experiment_uuid": "b1f3ce3d-99da-40e4-849a-c8b352948a31",
                "created": '2000-01-01',
                "name": "ctrl-branch-b1f3ce3d",
                "model": "TEST-MODEL",
                "url": "mockUrl",
                "contact": "mockUser",
                "email": "mock@email.com"
            }
        ),
        # Test metadata file updated when new UUID
        (
            "7b90f37c-4619-44f9-a439-f76fdf6ae2bd",
            "Control-Branch-7b90f37c",
            {
                "experiment_uuid": "b3298c7f-01f6-4f0a-be32-ce5d2cfb9a04",
                "contact": "Add your name here",
                "email": "Add your email address here",
                "description": "Add description here",
            },
            {
                "experiment_uuid": "7b90f37c-4619-44f9-a439-f76fdf6ae2bd",
                "description": "Add description here",
                "created": '2000-01-01',
                "name": "Control-Branch-7b90f37c",
                "model": "TEST-MODEL",
                "url": "mockUrl",
                "contact": "mockUser",
                "email": "mock@email.com"
            }
        ),
        # Test extra fields not added with legacy experiments
        (
            "7b90f37c-4619-44f9-a439-f76fdf6ae2bd",
            "ctrl",
            {
                "experiment_uuid": "0f49f2a0-f45e-4c0b-a3b6-4b0bf21f2b75",
                "name": "UserDefinedExperimentName",
                "contact": "TestUser",
                "email": "Test@email.com"
            },
            {
                "experiment_uuid": "7b90f37c-4619-44f9-a439-f76fdf6ae2bd",
                "name": "UserDefinedExperimentName",
                "contact": "TestUser",
                "email": "Test@email.com"
            }
        ),
    ]
)
def test_update_file(mock_repo, uuid, experiment_name,
                     previous_metadata, expected_metadata):
    # Create pre-existing metadata file
    metadata_path = ctrldir / 'metadata.yaml'
    yaml = YAML()
    if previous_metadata is not None:
        with open(metadata_path, 'w') as file:
            yaml.dump(previous_metadata, file)

    # Add mock git values
    mock_repo.return_value.get_origin_url.return_value = "mockUrl"
    mock_repo.return_value.get_user_info.side_effect = mocked_get_git_user_info

    # Setup config
    test_config = config.copy()
    test_config['model'] = "test-model"
    write_config(test_config)

    # Initialise Metadata
    with cd(ctrldir):
        metadata = Metadata(archive_dir)
    metadata.uuid = uuid
    metadata.experiment_name = experiment_name

    # Mock datetime (for created date)
    with patch('payu.metadata.datetime') as mock_date:
        mock_date.now.return_value = datetime(2000, 1, 1)

        # Function to test
        metadata.update_file()

    assert metadata_path.exists and metadata_path.is_file

    with open(metadata_path, 'r') as file:
        metadata = yaml.load(metadata_path)

    assert metadata == expected_metadata


@pytest.mark.parametrize(
    "uuid_exists, keep_uuid, is_new_experiment, "
    "branch_uuid_archive_exists, legacy_archive_exists, catch_warning,"
    "expected_uuid, expected_name",
    [
        # Keep UUID on new experiment - UUID Exists - no archives exist
        (
            True, True, True, False, False, False,
            "3d18b3b6-dd19-49a9-8d9e-c7fa8582f136", "ctrl-mock_branch-3d18b3b6"
        ),
        # Keep UUID on new experiment - UUID Exists - legacy archive exists
        (
            True, True, True, False, True, False,
            "3d18b3b6-dd19-49a9-8d9e-c7fa8582f136", "ctrl-mock_branch-3d18b3b6"
        ),
        # Keep UUID on not new experiement - UUID Exists -legacy archive exists
        (
            True, True, False, False, True, False,
            "3d18b3b6-dd19-49a9-8d9e-c7fa8582f136", "ctrl"
        ),
        # Keep UUID on not new experiment - No UUID - no archives exist
        (
            False, True, True, False, False, False,
            "cb793e91-6168-4ed2-a70c-f6f9ccf1659b", "ctrl-mock_branch-cb793e91"
        ),
        # Experiment setup - No UUID - legacy archive exists
        (
            False, False, False, False, True, True,
            "cb793e91-6168-4ed2-a70c-f6f9ccf1659b", "ctrl"
        ),
        # Experiment setup - No UUID - no archive exists
        (
            False, False, False, False, False, True,
            "cb793e91-6168-4ed2-a70c-f6f9ccf1659b", "ctrl-mock_branch-cb793e91"
        ),
        # Experiment setup - Existing UUID - legacy archive exists
        (
            True, False, False, False, True, False,
            "3d18b3b6-dd19-49a9-8d9e-c7fa8582f136", "ctrl"
        ),
        # Experiment setup - Existing UUID - new archive exists
        (
            True, False, False, True, True, False,
            "3d18b3b6-dd19-49a9-8d9e-c7fa8582f136", "ctrl-mock_branch-3d18b3b6"
        ),
    ]
)
def test_set_experiment_and_uuid(uuid_exists, keep_uuid, is_new_experiment,
                                 branch_uuid_archive_exists,
                                 legacy_archive_exists, catch_warning,
                                 expected_uuid, expected_name):
    # Setup config and metadata
    write_config(config)
    with cd(ctrldir):
        metadata = Metadata(archive_dir)

    if uuid_exists:
        metadata.uuid = "3d18b3b6-dd19-49a9-8d9e-c7fa8582f136"

    if branch_uuid_archive_exists:
        archive_path = archive_dir / "ctrl-mock_branch-3d18b3b6"
        archive_path.mkdir(parents=True)

    if legacy_archive_exists:
        archive_path = archive_dir / "ctrl"
        archive_path.mkdir(parents=True)

    # Test set UUID and experiment name
    with patch('payu.metadata.GitRepository.get_branch_name') as mock_branch, \
         patch('uuid.uuid4') as mock_uuid:
        mock_branch.return_value = "mock_branch"
        mock_uuid.return_value = "cb793e91-6168-4ed2-a70c-f6f9ccf1659b"

        if catch_warning:
            # Test warning raised
            with pytest.warns(MetadataWarning):
                metadata.setup(is_new_experiment=is_new_experiment,
                               keep_uuid=keep_uuid)
        else:
            metadata.setup(is_new_experiment=is_new_experiment,
                           keep_uuid=keep_uuid)

    assert metadata.experiment_name == expected_name
    assert metadata.uuid == expected_uuid


@pytest.mark.parametrize(
    "archive_metadata_exists, archive_uuid, expected_result",
    [
        # A legacy archive exists, but there's no corresponding metadata
        # in archive
        (
            False, None, True
        ),
        # Archive metadata exists but has no UUID
        (
            True, None, True
        ),
        # Archive metadata exists with same UUID
        (
            True, "3d18b3b6-dd19-49a9-8d9e-c7fa8582f136", True
        ),
        # Archive metadata exists with different UUID
        (
            True, "cb793e91-6168-4ed2-a70c-f6f9ccf1659b", False
        ),
    ]
)
def test_has_archive(archive_metadata_exists, archive_uuid, expected_result):
    # Setup config and metadata
    write_config(config)
    with cd(ctrldir):
        metadata = Metadata(archive_dir)
    metadata.uuid = "3d18b3b6-dd19-49a9-8d9e-c7fa8582f136"

    # Setup archive and it's metadata file
    archive_path = archive_dir / "ctrl"
    archive_path.mkdir(parents=True)

    if archive_metadata_exists:
        archive_metadata = {}

        if archive_uuid is not None:
            archive_metadata["experiment_uuid"] = archive_uuid

        with open(archive_path / 'metadata.yaml', 'w') as file:
            YAML().dump(archive_metadata, file)

    result = metadata.has_archive("ctrl")
    assert result == expected_result


def test_set_configured_experiment_name():
    # Set experiment in config file
    test_config = copy.deepcopy(config)
    test_config['experiment'] = "configuredExperiment"
    write_config(test_config)

    with cd(ctrldir):
        metadata = Metadata(archive_dir)

    # Test configured experiment name is always the set experiment name
    metadata.set_experiment_name()
    assert metadata.experiment_name == "configuredExperiment"

    metadata.set_experiment_name(is_new_experiment=True)
    assert metadata.experiment_name == "configuredExperiment"


@pytest.mark.parametrize(
    "branch, expected_name",
    [(None, "ctrl-cb793e91"),
     ("main", "ctrl-cb793e91"),
     ("master", "ctrl-cb793e91"),
     ("branch", "ctrl-branch-cb793e91")]
)
def test_new_experiment_name(branch, expected_name):
    # Test configured experiment name is the set experiment name
    write_config(config)
    with cd(ctrldir):
        metadata = Metadata(archive_dir)

    metadata.uuid = "cb793e91-6168-4ed2-a70c-f6f9ccf1659b"

    with patch('payu.metadata.GitRepository.get_branch_name') as mock_branch:
        mock_branch.return_value = branch
        experiment = metadata.new_experiment_name()

    assert experiment == expected_name


def test_metadata_enable_false():
    # Set metadata to false in config file
    test_config = copy.deepcopy(config)
    test_config['metadata'] = {
        "enable": False
    }
    write_config(test_config)

    with cd(ctrldir):
        metadata = Metadata(archive_dir)
        metadata.setup()
        metadata.write_metadata()

    # Test UUID kept out of experiment name and metadata file is not written
    assert metadata.experiment_name == "ctrl"
    assert not (ctrldir / "metadata.yaml").exists()


def test_metadata_disable():
    # Set metadata to True in config file
    write_config(config)

    with cd(ctrldir):
        # Pass disabled flag to Metadata initialisation call
        metadata = Metadata(archive_dir, disabled=True)
        metadata.setup()
        metadata.write_metadata()

    # Test UUID kept out of experiment name and metadata file is not written
    assert metadata.experiment_name == "ctrl"
    assert not (ctrldir / "metadata.yaml").exists()


@patch("payu.metadata.GitRepository")
def test_update_file_with_template_metadata_values(mock_repo):
    # Leave out origin URL and git user info
    mock_repo.return_value.get_origin_url.return_value = None
    mock_repo.return_value.get_user_info.return_value = None

    # Setup config
    test_config = config.copy()
    test_config['model'] = "test-model"
    write_config(test_config)

    # Initialise Metadata and UUID and experiment name
    with cd(ctrldir):
        metadata = Metadata(archive_dir)
    metadata.experiment_name = "ctrldir-branch-cb793e91"
    metadata.uuid = "cb793e91-6168-4ed2-a70c-f6f9ccf1659"

    with patch('requests.get') as mock_get:
        # Mock request for json schema
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The name of the experiment (string)"
                },
                "experiment_uuid": {
                    "type": "string",
                    "format": "uuid",
                    "description": "Unique uuid for the experiment (string)"
                },
                "description": {
                    "type": "string",
                    "description": ("Short description of the experiment "
                                    "(string, < 150 char)")
                },
                "long_description": {
                    "type": "string",
                    "description": ("Long description of the experiment "
                                    "(string)")
                },
                "model": {
                    "type": "array",
                    "items": {"type": ["string", "null"]},
                    "description": ("The name(s) of the model(s) used in the"
                                    " experiment (string)")
                },
            },
            "required": [
                "name",
                "experiment_uuid",
                "description",
                "long_description"
            ]
        }
        mock_get.return_value = mock_response

        # Mock datetime (for created date)
        with patch('payu.metadata.datetime') as mock_date:
            mock_date.now.return_value = datetime(2000, 1, 1)

            # Test function
            metadata.update_file(set_template_values=True)

    # Expect commented template values for non-null fields
    expected_metadata = """experiment_uuid: cb793e91-6168-4ed2-a70c-f6f9ccf1659
created: '2000-01-01'
name: ctrldir-branch-cb793e91
model: TEST-MODEL
description:  # Short description of the experiment (string, < 150 char)
long_description: # Long description of the experiment (string)
"""
    assert (ctrldir / 'metadata.yaml').read_text() == expected_metadata
