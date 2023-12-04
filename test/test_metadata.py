import copy
import shutil

import pytest
from unittest.mock import patch

from payu.metadata import Metadata, MetadataWarning

from test.common import cd
from test.common import tmpdir, ctrldir, labdir, archive_dir
from test.common import config as config_orig
from test.common import write_config
from test.common import make_all_files

verbose = True

# Global config
config = copy.deepcopy(config_orig)
config.pop("experiment")


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


def mocked_get_git_user_info(repo_path, config_key, example_value):
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


@pytest.mark.parametrize(
    "uuid, previous_metadata, expected_metadata",
    [
        (
            "0f49f2a0-f45e-4c0b-a3b6-4b0bf21f2b75",
            """contact: TestUser
email: Test@email.com
description: |-
  Test description etc
  More description
keywords:
- test
- testKeyword
# Test Comment
experiment_uuid: 0f49f2a0-f45e-4c0b-a3b6-4b0bf21f2b75
parent_experiment: b3298c7f-01f6-4f0a-be32-ce5d2cfb9a04
""",
            """contact: TestUser
email: Test@email.com
description: |-
  Test description etc
  More description
keywords:
- test
- testKeyword
# Test Comment
experiment_uuid: 0f49f2a0-f45e-4c0b-a3b6-4b0bf21f2b75
parent_experiment: b3298c7f-01f6-4f0a-be32-ce5d2cfb9a04
"""
        ),
        (
            "b1f3ce3d-99da-40e4-849a-c8b352948a31",
            None,
            """experiment_uuid: b1f3ce3d-99da-40e4-849a-c8b352948a31
contact: mockUser
email: mock@email.com
"""
        ),
        (
            "7b90f37c-4619-44f9-a439-f76fdf6ae2bd",
            """experiment_uuid: b3298c7f-01f6-4f0a-be32-ce5d2cfb9a04
contact: Add your name here
email: Add your email address here
""",
            """experiment_uuid: 7b90f37c-4619-44f9-a439-f76fdf6ae2bd
contact: mockUser
email: mock@email.com
parent_experiment: b3298c7f-01f6-4f0a-be32-ce5d2cfb9a04
"""
        ),
        (
            "3d18b3b6-dd19-49a9-8d9e-c7fa8582f136",
            """
contact: AdD Your nAme hEre
email: #
""",
            """contact: mockUser
email: mock@email.com #
experiment_uuid: 3d18b3b6-dd19-49a9-8d9e-c7fa8582f136
"""
        )
    ]
)
def test_update_file(uuid, previous_metadata, expected_metadata):
    # Create pre-existing metadata file
    metadata_path = ctrldir / 'metadata.yaml'
    if previous_metadata is not None:
        metadata_path.write_text(previous_metadata)

    write_config(config)
    with cd(ctrldir):
        metadata = Metadata(archive_dir)

    metadata.uuid = uuid

    # Function to test
    with patch('payu.metadata.get_git_user_info',
               side_effect=mocked_get_git_user_info):
        metadata.update_file()

    assert metadata_path.exists and metadata_path.is_file
    assert metadata_path.read_text() == expected_metadata

    # Remove metadata file
    metadata_path.unlink()


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
    with patch('payu.metadata.get_git_branch') as mock_branch, \
         patch('uuid.uuid4') as mock_uuid:
        mock_branch.return_value = "mock_branch"
        mock_uuid.return_value = "cb793e91-6168-4ed2-a70c-f6f9ccf1659b"

        if catch_warning:
            with pytest.warns(MetadataWarning):
                metadata.set_uuid_and_experiment_name(
                    is_new_experiment=is_new_experiment,
                    keep_uuid=keep_uuid
                )
        else:
            metadata.set_uuid_and_experiment_name(
                is_new_experiment=is_new_experiment,
                keep_uuid=keep_uuid
            )

    assert metadata.experiment_name == expected_name
    assert metadata.uuid == expected_uuid


def test_set_configured_experiment_name():
    # Test configured experiment name is the set experiment name
    test_config = copy.deepcopy(config)
    test_config['experiment'] = "configuredExperiment"
    write_config(test_config)
    with cd(ctrldir):
        metadata = Metadata(archive_dir)

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
def test_get_branch_uuid_aware_experiment_name(branch, expected_name):
    # Test configured experiment name is the set experiment name
    with cd(ctrldir):
        metadata = Metadata(archive_dir)

    metadata.uuid = "cb793e91-6168-4ed2-a70c-f6f9ccf1659b"

    with patch('payu.metadata.get_git_branch') as mock_branch:
        mock_branch.return_value = branch
        experiment = metadata.get_branch_uuid_experiment_name()

    assert experiment == expected_name
