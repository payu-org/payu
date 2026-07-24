import copy
from pathlib import Path
import shutil
from datetime import datetime

import pytest
from unittest.mock import patch, Mock
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
import jsonschema

from payu.metadata import Metadata, SCHEMA_FIELD, SCHEMA_VERSION, placeholder_text, no_archive_msg
import payu.errors as errors
from payu.metadata import DO_NOT_EDIT_COMMENT, CAN_EDIT_COMMENT, PLEASE_UPDATE_COMMENT, BRANCH_OFF_TIME_FIELD
from payu.metadata import arrange_metadata, add_template_metadata_values

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

@pytest.fixture
def mock_git_repo():
    with patch("payu.metadata.GitRepository") as mock_repo:
        # Leave out origin URL and git user info
        mock_repo.return_value.get_origin_url.return_value = None
        mock_repo.return_value.get_user_info.return_value = None

        with patch("requests.get") as mock_get:
            # Mock request for json schema
            mock_response = Mock()
            mock_response.status_code = 200
            mock_shema = YAML().load(Path(__file__).parent / "resources" / "mock_schema.yaml")
            mock_response.json.return_value = mock_shema
            mock_get.return_value = mock_response

            # Mock datetime (for created date)
            with patch('payu.metadata.datetime') as mock_date:
                mock_date.now.return_value = datetime(2000, 1, 1)

                yield mock_repo, mock_get, mock_date, mock_response


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
    "branch_uuid_archive_exists, legacy_archive_exists,"
    "expected_uuid, expected_name",
    [
        # Keep UUID on new experiment - UUID Exists - no archives exist
        (
            True, True, True, False, False,
            "3d18b3b6-dd19-49a9-8d9e-c7fa8582f136", "ctrl-mock_branch-3d18b3b6"
        ),
        # Keep UUID on new experiment - UUID Exists - legacy archive exists
        (
            True, True, True, False, True,
            "3d18b3b6-dd19-49a9-8d9e-c7fa8582f136", "ctrl-mock_branch-3d18b3b6"
        ),
        # Keep UUID on not new experiment - UUID Exists -legacy archive exists
        (
            True, True, False, False, True,
            "3d18b3b6-dd19-49a9-8d9e-c7fa8582f136", "ctrl"
        ),
        # Keep UUID on not new experiment - No UUID - no archives exist
        (
            False, True, True, False, False, 
            "cb793e91-6168-4ed2-a70c-f6f9ccf1659b", "ctrl-mock_branch-cb793e91"
        ),
        # Experiment setup - No UUID - legacy archive exists
        (
            False, False, False, False, True, 
            "cb793e91-6168-4ed2-a70c-f6f9ccf1659b", "ctrl"
        ),
        # Experiment setup - Existing UUID - legacy archive exists
        (
            True, False, False, False, True,
            "3d18b3b6-dd19-49a9-8d9e-c7fa8582f136", "ctrl"
        ),
        # Experiment setup - Existing UUID - new archive exists
        (
            True, False, False, True, True, 
            "3d18b3b6-dd19-49a9-8d9e-c7fa8582f136", "ctrl-mock_branch-3d18b3b6"
        ),
    ]
)
def test_set_experiment_and_uuid(uuid_exists, keep_uuid, is_new_experiment,
                                 branch_uuid_archive_exists,
                                 legacy_archive_exists, expected_uuid, expected_name):
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
    metadata.expt_name_prefix = None

    with patch('payu.metadata.GitRepository.get_branch_name') as mock_branch:
        mock_branch.return_value = branch
        experiment = metadata.new_experiment_name()

    assert experiment == expected_name


@pytest.mark.parametrize(
    "expt_name_prefix, branch, expected_name",
    [
        (None, "branch", "ctrl-branch-cb793e91"),
        (" ", "branch", "ctrl-branch-cb793e91"),
        ("imprefix", None, "imprefix-cb793e91"),
        ("hiprefix", "branch", "hiprefix-branch-cb793e91"),
        ("ohprefix", "master", "ohprefix-cb793e91"),
    ]
)
def test_new_experiment_name_with_prefix(expt_name_prefix, branch, expected_name):
    """ Test experiment name is prefix with branch and UUID suffix"""
    # Setup config
    test_config = config.copy()
    test_config['experiment_prefix'] = expt_name_prefix
    write_config(test_config)
    with cd(ctrldir):
        metadata = Metadata(archive_dir)

    metadata.uuid = "cb793e91-6168-4ed2-a70c-f6f9ccf1659b"

    with patch('payu.metadata.GitRepository.get_branch_name') as mock_branch:
        mock_branch.return_value = branch
        metadata.expt_name_prefix = metadata.config.get("experiment_prefix", None)
        experiment = metadata.new_experiment_name()

    assert experiment == expected_name


def test_experiment_name_with_prefix_and_experiment():
    """Test when both experiment name and prefix are set, a warning is raised and
    new_experiment_name() is not called, experiment name is used directly."""
    # Setup config
    test_config = config.copy()
    test_config['experiment_prefix'] = "IAMprefix"
    test_config['experiment'] = "IAMexpt"
    write_config(test_config)
    with cd(ctrldir):
        metadata = Metadata(archive_dir)

    with patch.object(metadata, 'new_experiment_name') as mock_new_experiment_name:
        with pytest.warns(UserWarning, match="Both experiment name and prefix are configured in config.yaml.\n"):
            metadata.set_experiment_name()

        mock_new_experiment_name.assert_not_called()


def test_set_experiment_name_archive_not_found():
    """Test that when no archive found, the user is prompted to confirm before generating a new UUID."""
    # Setup config
    write_config(config)
    with cd(ctrldir):
        metadata = Metadata(archive_dir)
        
    with patch.object(metadata, 'has_archive') as mock_has_archive, \
        patch.object(metadata, 'new_experiment_name') as mock_new_experiment_name:

        # Simulate no archive found
        mock_has_archive.return_value = False  

        # Simulate new experiment name generation
        mock_new_experiment_name.return_value = "mock_experiment_name"

        # Assert error raised when user did not specify to generate a new UUID
        with pytest.raises(errors.PayuRuntimeError, match=f"{no_archive_msg}"):
            metadata.set_experiment_name(is_new_experiment=False)



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


def test_update_file_with_template_metadata_values(mock_git_repo):
    """ Test metadata is updated with set_template_values = True
        and test if metadata is valid against the schema"""
    mock_repo, mock_get, mock_date, mock_response = mock_git_repo
    
    # Setup config
    test_config = config.copy()
    test_config['model'] = "test-model"
    write_config(test_config)

    # Initialise Metadata and UUID and experiment name
    with cd(ctrldir):
        metadata = Metadata(archive_dir)
    metadata.experiment_name = "ctrldir-branch-cb793e91"
    metadata.uuid = "cb793e91-6168-4ed2-a70c-f6f9ccf1659"

    # Test function
    metadata.update_file(set_template_values=True)

    # Expect commented template values for non-null fields
    expected_metadata = f"""
# {DO_NOT_EDIT_COMMENT}
experiment_uuid: cb793e91-6168-4ed2-a70c-f6f9ccf1659

# {CAN_EDIT_COMMENT}
name: ctrldir-branch-cb793e91
created: '2000-01-01'
model: TEST-MODEL
{SCHEMA_FIELD}: {SCHEMA_VERSION}

# {PLEASE_UPDATE_COMMENT}
description: {placeholder_text}  # Short description of the experiment (string, < 150 char)
long_description: {placeholder_text} # Long description of the experiment (string)
# realm: The realm(s) included in the experiment (array of strings)
"""
    assert (ctrldir / 'metadata.yaml').read_text() == expected_metadata

    # Test metadata is valid against the schema
    metadata = YAML().load((ctrldir / 'metadata.yaml'))
    jsonschema.validate(instance=metadata, schema=mock_response.json.return_value)


@pytest.mark.parametrize(
    "metadata, expected_metadata, manual_fields",
    [
        (   
            # Test fields arranged in correct order: auto don't edit fields + auto may edit fields
            CommentedMap([
                ("name", "Control-Branch-UUID"),
                ("experiment_uuid", "test-uuid"),
                ("email", "test@domain.com"),
                ("created", "2026-01-01"),
                ("url", "test-url"),
                ("model", "test-model"),
            ]),
            CommentedMap([
                ("experiment_uuid", "test-uuid"),
                ("name", "Control-Branch-UUID"),
                ("email", "test@domain.com"),
                ("created", "2026-01-01"),
                ("url", "test-url"),
                ("model", "test-model"),
            ]),
            False,
        ),
        # Test fields with None values are left at the end, and manual fields have a header
        (
            CommentedMap([
                ("email", "test@domain.com"),
                ("description", None),
                ("created", "2026-01-01"),
                ("url", None),
                ("model", "test-model"),
                ("experiment_uuid", "test-uuid"),
                ("name", "Control-Branch-UUID"),
            ]),
            CommentedMap([
                ("experiment_uuid", "test-uuid"),
                ("name", "Control-Branch-UUID"),
                ("email", "test@domain.com"),
                ("created", "2026-01-01"),
                ("model", "test-model"),
                ("description", None),
                ("url", None),
            ]),
            True,
        ),
    ]
)
def test_arrange_metadata(metadata, expected_metadata, manual_fields):
    """Test that arrange_metadata correctly arranges fields and adds headers"""

    result = arrange_metadata(metadata)
    assert expected_metadata == result

    # Test headers added for auto-generated fields
    assert "\n" == result.ca.items["experiment_uuid"][1][0].value
    assert f"# {DO_NOT_EDIT_COMMENT}\n" == result.ca.items["experiment_uuid"][1][1].value
    assert f"# {CAN_EDIT_COMMENT}\n" == result.ca.items["name"][1][1].value

    # Test header added if there are manual fields
    if manual_fields:
        assert f"# {PLEASE_UPDATE_COMMENT}\n" == result.ca.items["description"][1][1].value


@pytest.mark.parametrize("metadata_input, metadata_expected, set_template_values", 
    [
        ("metadata_example.yaml", "metadata_example_arranged.yaml", True),
        ("metadata_unchange.yaml", "metadata_unchange.yaml", False)
    ]
)
def test_update_file_given_metadata_file(tmp_path, metadata_input, metadata_expected, set_template_values, mock_git_repo):
    """Test that add_template_metadata_values + arrange_metadata 
        oragnise metadata and preserves description comments"""

    metadata = YAML().load(Path(__file__).parent / "resources" / metadata_input)
    if set_template_values:
        metadata = add_template_metadata_values(metadata)
    result = arrange_metadata(metadata)
    
    # write result to file
    result_path = tmp_path / "metadata_result.yaml"
    YAML().dump(result, result_path)

    expected_metadata_path = Path(__file__).parent / "resources" / metadata_expected
    assert result_path.read_text() == expected_metadata_path.read_text()


@pytest.mark.parametrize(
    "restart_path, branch_off_time, expected",
    [   
        # restart_path and branch_off_time provided - BRANCH_OFF_TIME_FIELD should be updated
        (Path("/path/to/restart000/"), "2026-07-24T12:00:00", "2026-07-24T12:00:00"),

        # restart_path provided, but no branch_off_time - should not have BRANCH_OFF_TIME_FIELD
        (Path("/path/to/restart000/"), None, None),
        
        # branch_off_time alone, without a restart_path, should not have BRANCH_OFF_TIME_FIELD
        (None, "2026-07-24T12:00:00", None),

        # No restart_path and no branch_off_time, should not have BRANCH_OFF_TIME_FIELD
        (None, None, None),
    ]
)
def test_update_file_restart_branch_off_time(restart_path, branch_off_time, expected):
    """ Test that branch_off_time is added to metadata when restart path is provided"""
    # Setup config
    test_config = config.copy()
    test_config['model'] = "test-model"
    write_config(test_config)

    # Initialise Metadata
    with cd(ctrldir):
        metadata = Metadata(archive_dir)
    metadata.uuid = "cb793e91-6168-4ed2-a70c-f6f9ccf1659"
    metadata.experiment_name = "ctrl-mock_branch-cb793e91"

    # Write an initial branch off time
    orig_metadata = metadata.read_file()
    orig_metadata[BRANCH_OFF_TIME_FIELD] = "Original branch off time"
    with open(ctrldir / 'metadata.yaml', 'w') as file:
        YAML().dump(orig_metadata, file)

    # Mock datetime (for created date)
    with patch('payu.metadata.datetime') as mock_date:
        mock_date.now.return_value = datetime(2026, 7, 24)

        # Call update_file
        metadata.update_file(restart_path=restart_path, branch_off_time=branch_off_time)

    # Read the metadata file
    with open(ctrldir / 'metadata.yaml', 'r') as file:
        metadata_content = YAML().load(file)

    if expected is None:
        # Should not have BRANCH_OFF_TIME_FIELD field
        assert BRANCH_OFF_TIME_FIELD not in metadata_content
    else:
        # Should be the same as the provided branch_off_time
        assert metadata_content[BRANCH_OFF_TIME_FIELD] == expected