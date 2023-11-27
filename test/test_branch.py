import copy
import shutil
from pathlib import Path

import pytest
import git
from ruamel.yaml import YAML
from unittest.mock import patch

import payu
from payu.branch import add_restart_to_config, switch_symlink
from payu.branch import checkout_branch, clone, list_branches
from payu.metadata import MetadataWarning
from payu.fsops import read_config

from test.common import cd
from test.common import tmpdir, ctrldir, labdir
from test.common import ctrldir_basename
from test.common import config as config_orig, write_config
from test.common import config_path, metadata_path
from test.common import make_expt_archive_dir, expt_archive_dir


# Global config
config = copy.deepcopy(config_orig)


@pytest.fixture(autouse=True)
def setup_and_teardown():
    # Create tmp, lab and control directories
    try:
        tmpdir.mkdir()
        labdir.mkdir()
        ctrldir.mkdir()
    except Exception as e:
        print(e)

    yield

    # Remove tmp directory
    try:
        shutil.rmtree(tmpdir)
    except Exception as e:
        print(e)


def setup_control_repository(path=ctrldir, set_config=True):
    """ Return an new control repository"""
    if set_config:
        write_config(config, path=(path / 'config.yaml'))
    else:
        (path / 'newFile').touch()
    # Initialise a control repo
    repo = git.Repo.init(path)
    repo.index.add("*")
    # Commit the changes
    repo.index.commit("First commit - initialising repository")
    return repo


@pytest.mark.parametrize(
    "test_config, expected_config",
    [
        (
            """sync:
  restart: true
# Test comment
restart: old/path/to/restart
anotherField: 1
""",
            """sync:
  restart: true
# Test comment
restart: {0}
anotherField: 1
"""
        ),
        (
            """# Test comment

anotherField: 1""",
            """# Test comment

anotherField: 1
restart: {0}
"""
        ),
    ]
)
def test_add_restart_to_config(test_config, expected_config):
    """Test adding restart: path/to/restart to configuration file"""
    restart_path = labdir / 'archive' / 'tmpRestart'
    restart_path.mkdir(parents=True)

    expected_config = expected_config.format(restart_path)

    with config_path.open('w') as file:
        file.write(test_config)

    # Function to test
    with cd(ctrldir):
        add_restart_to_config(restart_path, config_path)

    with config_path.open('r') as file:
        updated_config = file.read()

    # Test order, comments are preserved
    assert updated_config == expected_config


def test_add_restart_to_config_invalid_restart_path():
    """Test restart path that does not exist raises a warning"""
    restart_path = tmpdir / 'restartDNE'

    config_content = "# Test config content"
    with config_path.open('w') as file:
        file.write(config_content)

    expected_msg = f"Given restart directory {restart_path} does not exist. "
    expected_msg += f"Skipping adding 'restart: {restart_path}' to config file"

    with cd(ctrldir):
        with pytest.warns(UserWarning, match=expected_msg):
            add_restart_to_config(restart_path, config_path)

    # Test config unchanged
    with config_path.open('r') as file:
        assert file.read() == config_content


def test_switch_symlink_when_symlink_and_archive_exists():
    # Pre-existing experiment symlink
    lab_archive = labdir / 'archive'
    previous_archive_dir = lab_archive / 'Experiment0'
    previous_archive_dir.mkdir(parents=True)

    archive_symlink = ctrldir / 'archive'
    archive_symlink.symlink_to(previous_archive_dir)

    # New Experiment - Existing archive
    experiment_name = 'Experiment1'
    archive_dir = lab_archive / experiment_name
    archive_dir.mkdir(parents=True)

    # Test Function
    switch_symlink(lab_archive, ctrldir, experiment_name, 'archive')

    # Assert new symlink is created
    assert archive_symlink.exists() and archive_symlink.is_symlink()
    assert archive_symlink.resolve() == archive_dir


def test_switch_symlink_when_symlink_exists_but_no_archive():
    # Pre-existing experiment symlink
    lab_archive = labdir / 'archive'
    previous_archive_dir = lab_archive / 'Experiment0'
    previous_archive_dir.mkdir(parents=True)

    archive_symlink = ctrldir / 'archive'
    archive_symlink.symlink_to(previous_archive_dir)

    # New Experiment
    experiment_name = 'Experiment1'

    # Test Function
    switch_symlink(lab_archive, ctrldir, experiment_name, 'archive')

    # Assert no symlink is created but previous one is removed
    assert not archive_symlink.exists()
    assert not archive_symlink.is_symlink()


def test_switch_symlink_when_no_symlink_exists_and_no_archive():
    # New Experiment
    experiment_name = 'Experiment1'
    lab_archive = labdir / 'archive'

    archive_symlink = ctrldir / 'archive'

    # Test Function
    switch_symlink(lab_archive, ctrldir, experiment_name, 'archive')

    # Assert no symlink
    assert not archive_symlink.exists()
    assert not archive_symlink.is_symlink()


def check_metadata(expected_uuid,
                   expected_experiment,
                   expected_previous_uuid=None,
                   metadata_file=metadata_path):
    """Helper function to read metadata file and assert changed as expected"""
    assert metadata_file.exists()
    metadata = YAML().load(metadata_file)
    assert metadata.get('uuid', None) == expected_uuid
    assert metadata.get('experiment', None) == expected_experiment
    assert metadata.get('previous_uuid', None) == expected_previous_uuid


def check_branch_metadata(repo,
                          expected_current_branch,
                          expected_uuid,
                          expected_experiment,
                          expected_previous_uuid=None,
                          metadata_file=metadata_path):
    """Helper function for checking expected  branch and metadata"""
    # Check metadata
    check_metadata(expected_uuid,
                   expected_experiment,
                   expected_previous_uuid,
                   metadata_file=metadata_file)

    # Check cuurent branch
    assert str(repo.active_branch) == expected_current_branch

    # Check last commit message
    expected_commit_msg = f"Updated metadata. Experiment uuid: {expected_uuid}"
    assert repo.head.commit.message == expected_commit_msg


@patch('shortuuid.uuid')
def test_checkout_branch(mock_uuid):
    repo = setup_control_repository()

    # Mock uuid1 value
    uuid1 = 'a1234567890'
    mock_uuid.return_value = uuid1

    with cd(ctrldir):
        # Test checkout new branch (with no existing metadata)
        checkout_branch(branch_name="Branch1",
                        is_new_branch=True,
                        lab_path=labdir)

    # Check current branch, new commit was added, and metadata created
    branch1_experiment_name = f'{ctrldir_basename}-Branch1-a1234'
    check_branch_metadata(repo,
                          expected_uuid=uuid1,
                          expected_current_branch='Branch1',
                          expected_experiment=branch1_experiment_name)

    # Save commit hash to check later on
    branch_1_commit_hash = repo.active_branch.object.hexsha

    # Mock uuid2 value
    uuid2 = 'b1234567890'
    mock_uuid.return_value = uuid2

    with cd(ctrldir):
        # Test checkout new branch from branch with existing metadata
        checkout_branch(branch_name="Branch2",
                        is_new_branch=True,
                        lab_path=labdir)

    # Check current branch, new commit was added, and metadata created
    branch2_experiment_name = f'{ctrldir_basename}-Branch2-b1234'
    check_branch_metadata(repo,
                          expected_uuid=uuid2,
                          expected_current_branch='Branch2',
                          expected_experiment=branch2_experiment_name,
                          expected_previous_uuid=uuid1)

    # Mock uuid3 value
    uuid3 = 'c1234567890'
    mock_uuid.return_value = uuid3

    with cd(ctrldir):
        # Test checkout new branch from starting branch with existing metadata
        checkout_branch(branch_name="Branch3",
                        is_new_branch=True,
                        start_point="Branch1",
                        lab_path=labdir)

    # Check current branch, new commit was added, and metadata created
    branch3_experiment_name = f'{ctrldir_basename}-Branch3-c1234'
    check_branch_metadata(repo,
                          expected_uuid=uuid3,
                          expected_current_branch='Branch3',
                          expected_experiment=branch3_experiment_name,
                          expected_previous_uuid=uuid1)

    with cd(ctrldir):
        # Test checkout existing branch with existing metadata
        checkout_branch(branch_name="Branch1",
                        lab_path=labdir)

    # Check metadata and commit has not changed on Branch1
    assert str(repo.active_branch) == "Branch1"
    check_metadata(expected_experiment=branch1_experiment_name,
                   expected_uuid=uuid1)

    # Assert commit hash is the same
    assert repo.active_branch.object.hexsha == branch_1_commit_hash


@patch('shortuuid.uuid')
def test_checkout_existing_branch_with_no_metadata(mock_uuid):
    repo = setup_control_repository()

    # Create new branch
    repo.create_head("Branch1")

    # Mock uuid1 value
    uuid1 = 'a1234567890'
    mock_uuid.return_value = uuid1
    expected_no_uuid_msg = (
        "No experiment uuid found in metadata. Generating a new uuid"
    )

    with cd(ctrldir):
        # Test checkout existing branch with no existing metadata
        with pytest.warns(MetadataWarning, match=expected_no_uuid_msg):
            checkout_branch(branch_name="Branch1",
                            lab_path=labdir)

    # Check metadata was created and commited
    branch1_experiment_name = f'{ctrldir_basename}-Branch1-a1234'
    check_branch_metadata(repo,
                          expected_uuid=uuid1,
                          expected_current_branch='Branch1',
                          expected_experiment=branch1_experiment_name)


@patch('shortuuid.uuid')
def test_checkout_branch_with_no_metadata_and_with_legacy_archive(mock_uuid):
    # Make experiment archive - This function creates legacy experiment archive
    make_expt_archive_dir(type='restart', index=0)

    # Setup repo
    repo = setup_control_repository()

    # Create new branch using git
    repo.create_head("Branch1")

    # Mock uuid1 value
    uuid1 = 'a1234567890'
    mock_uuid.return_value = uuid1
    expected_no_uuid_msg = (
        "No experiment uuid found in metadata. Generating a new uuid"
    )

    archive_warning_msg = (
        f"Pre-existing archive found at: {expt_archive_dir}. "
        f"Experiment name will remain: ctrl"
    )

    with cd(ctrldir):
        # Test checkout existing branch (with no existing metadata)
        # and with pre-existing archive
        with pytest.warns(MetadataWarning) as metadata_warnings:
            checkout_branch(branch_name="Branch1",
                            lab_path=labdir)

    # Check metadata was created and commited - with legacy experiment name
    branch1_experiment_name = ctrldir_basename
    check_branch_metadata(repo,
                          expected_uuid=uuid1,
                          expected_current_branch='Branch1',
                          expected_experiment=branch1_experiment_name)

    # Check warnings were raised
    warnings_msgs = [warning.message.args[0] for warning in metadata_warnings]
    assert warnings_msgs == [expected_no_uuid_msg, archive_warning_msg]


@patch('shortuuid.uuid')
def test_checkout_new_branch_existing_legacy_archive(mock_uuid):
    # Using payu checkout new branch should generate new uuid,
    # and experiment name - even if there's a legacy archive
    repo = setup_control_repository()

    # Add archive under legacy name
    restart_path = Path(make_expt_archive_dir(type='restart'))

    # Mock uuid1 value
    uuid1 = 'a1234567890'
    mock_uuid.return_value = uuid1

    with cd(ctrldir):
        # Test checkout new branch (with no existing metadata)
        checkout_branch(branch_name="Branch1",
                        is_new_branch=True,
                        restart_path=restart_path,
                        config_path=config_path,
                        lab_path=labdir)

    # Check metadata was created and commited - with branch-uuid aware name
    branch1_experiment_name = f'{ctrldir_basename}-Branch1-a1234'
    check_branch_metadata(repo,
                          expected_uuid=uuid1,
                          expected_current_branch='Branch1',
                          expected_experiment=branch1_experiment_name)

    # Check restart path was added to configuration file
    config = read_config(config_path)
    assert config['restart'] == str(restart_path)


def test_checkout_branch_with_no_config():
    # Initialise a control repo with no config
    repo = setup_control_repository(set_config=False)

    repo.create_head("Branch1")

    with cd(ctrldir):
        # Test checkout branch that has no config raise error
        with pytest.raises(FileNotFoundError):
            checkout_branch(branch_name="Branch1",
                            lab_path=labdir)

    assert not metadata_path.exists()


@patch('shortuuid.uuid')
def test_clone(mock_uuid):
    # Create a repo to clone
    source_repo_path = tmpdir / 'sourceRepo'
    source_repo_path.mkdir()
    source_repo = setup_control_repository(path=source_repo_path)
    source_main_branch = str(source_repo.active_branch)

    # Create and checkout branch
    branch1 = source_repo.create_head("Branch1")
    branch1.checkout()

    # Mock uuid1 value
    uuid1 = 'a1234567890'
    mock_uuid.return_value = uuid1

    # Test clone
    cloned_repo_path = tmpdir / 'clonedRepo'
    clone(source_repo_path, cloned_repo_path, lab_path=labdir)

    # Check new commit added and expected metadata
    cloned_repo = git.Repo(cloned_repo_path)
    metadata_file = cloned_repo_path / 'metadata.yaml'
    check_branch_metadata(repo=cloned_repo,
                          expected_current_branch="Branch1",
                          expected_uuid=uuid1,
                          expected_experiment="clonedRepo-Branch1-a1234",
                          metadata_file=metadata_file)

    cloned_repo.git.checkout(source_main_branch)

    # Test clone of a clone - adding a new branch
    uuid2 = 'b1234567890'
    mock_uuid.return_value = uuid2

    # Run clone
    with cd(tmpdir):
        clone(cloned_repo_path, Path('clonedRepo2'),
              lab_path=labdir, new_branch_name='Branch2', branch='Branch1')

    # Check new commit added and expected metadata
    cloned_repo2 = git.Repo(tmpdir / 'clonedRepo2')
    metadata_file = tmpdir / 'clonedRepo2' / 'metadata.yaml'
    check_branch_metadata(repo=cloned_repo2,
                          expected_current_branch="Branch2",
                          expected_uuid=uuid2,
                          expected_experiment="clonedRepo2-Branch2-b1234",
                          expected_previous_uuid=uuid1,
                          metadata_file=metadata_file)

    # Check local branches
    assert [head.name for head in cloned_repo2.heads] == ['Branch1', 'Branch2']


def add_and_commit_metadata(repo, metadata):
    """Helper function to create/update metadata file and commit"""
    metadata_path = ctrldir / 'metadata.yaml'
    YAML().dump(metadata, metadata_path)
    repo.index.add('*')
    repo.index.commit("Updated metadata.yaml")


def test_list_branches(capsys):
    # Create repo and a few branches with and without metadata files
    repo = setup_control_repository(set_config=False)
    # Leave main branch with no metadata file
    main_branch_name = str(repo.active_branch)

    # Branch 1 - has config but no metadata
    branch1 = repo.create_head("Branch1")
    branch1.checkout()
    write_config(config)
    repo.index.add('*')
    repo.index.commit("Added config.yaml")

    # Checkout and add metadata to new branch
    branch2 = repo.create_head("Branch2")
    branch2.checkout()
    write_config(config)
    branch_2_metadata = {
        "uuid": "b12345678",
        "experiment": "testExperimentName2"
    }
    add_and_commit_metadata(repo, branch_2_metadata)

    # New branch with no uuid in metadata
    branch3 = repo.create_head("Branch3")
    branch3.checkout()
    branch_3_metadata = {
        "experiment": "testExperimentName3",
        "contact": "TestUser"
    }
    add_and_commit_metadata(repo, branch_3_metadata)

    # Test list branches
    with cd(ctrldir):
        list_branches()

    expected_printed_output = f"""* Current Branch: Branch3
    No uuid in metadata file
Branch: Branch1
    No metadata file found
Branch: Branch2
    uuid: b12345678
Branch: {main_branch_name}
    No config file found"""
    captured = capsys.readouterr()
    assert captured.out.strip() == expected_printed_output

    # Test list branches with verbose set
    with cd(ctrldir):
        list_branches(verbose=True)

    expected_verbose_output = f"""* Current Branch: Branch3
    experiment: testExperimentName3
    contact: TestUser
Branch: Branch1
    No metadata file found
Branch: Branch2
    uuid: b12345678
    experiment: testExperimentName2
Branch: {main_branch_name}
    No config file found"""
    captured = capsys.readouterr()
    assert captured.out.strip() == expected_verbose_output

    # Test remote branches
    cloned_repo_path = tmpdir / 'cloned_repo'
    repo.clone(cloned_repo_path)

    with cd(cloned_repo_path):
        list_branches(remote=True)
    expected_remote_output = f"""* Current Branch: Branch3
    No uuid in metadata file
Remote Branch: Branch1
    No metadata file found
Remote Branch: Branch2
    uuid: b12345678
Remote Branch: Branch3
    No uuid in metadata file
Remote Branch: HEAD
    No uuid in metadata file
Remote Branch: {main_branch_name}
    No config file found"""
    captured = capsys.readouterr()
    assert captured.out.strip() == expected_remote_output
