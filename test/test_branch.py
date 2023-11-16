import copy
import shutil
from pathlib import Path

import pytest
import git
from unittest.mock import patch

import payu
from payu.branch import add_restart_to_config, switch_symlink
from payu.branch import checkout_branch, clone
from payu.metadata import Metadata
from payu.fsops import read_config

from test.common import cd
from test.common import tmpdir, ctrldir, labdir
from test.common import ctrldir_basename
from test.common import config as config_orig, write_config
from test.common import config_path
from test.common import make_all_files, make_expt_archive_dir


# Global config
config = copy.deepcopy(config_orig)


@pytest.fixture(autouse=True)
def setup_and_teardown():
    # Create tmp, lab and control directories
    try:
        tmpdir.mkdir()
        labdir.mkdir()
        ctrldir.mkdir()
        make_all_files()
    except Exception as e:
        print(e)

    yield

    # Remove tmp directory
    try:
        shutil.rmtree(tmpdir)
    except Exception as e:
        print(e)


def setup_control_repository(path: Path = ctrldir) -> git.Repo:
    """ Return an new control repository"""
    write_config(config, path=(path / 'config.yaml'))
    # Initialise a control repo
    repo = git.Repo.init(path)
    repo.index.add("*")
    # Commit the changes
    repo.index.commit("First commit - initialising repository")
    return repo


@pytest.mark.parametrize(
    "config_lines, expected_lines",
    [
        (
                (
                        'sync:',
                        '  restart: true',
                        '# Test comment',
                        'restart: old/path/to/restart',
                        'anotherField: 1\n'
                ),
                (
                        'sync:',
                        '  restart: true',
                        '# Test comment',
                        'restart: {0}',
                        'anotherField: 1\n'
                )
        ),
        (
                (
                        '# Test comment',
                        '',
                        'anotherField: 1',
                ),
                (
                        '# Test comment',
                        '',
                        'anotherField: 1',
                        'restart: {0}\n',
                )
        ),
    ]
)
def test_add_restart_to_config(config_lines, expected_lines):
    """Test adding restart: path/to/restart to configuration file"""
    restart_path = labdir / 'archive' / 'tmpRestart'
    restart_path.mkdir()

    test_config = '\n'.join(config_lines)
    expected_config = '\n'.join(expected_lines).format(restart_path)

    with config_path.open('w') as file:
        file.write(test_config)

    # Function to test
    with cd(ctrldir):
        add_restart_to_config(restart_path)

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
            add_restart_to_config(restart_path)

    # Test config unchanged
    with config_path.open('r') as file:
        assert file.read() == config_content


def test_add_restart_to_config_invalid_config_path():
    """Test restart path that does not exist raises a warning"""
    config_path = tmpdir / "configDNE"

    restart_path = labdir / 'archive' / 'tmpRestart'
    restart_path.mkdir(exist_ok=True)

    expected_msg = f"Given configuration file {config_path} does not exist. "
    expected_msg += f"Skipping adding 'restart: {restart_path}' to config file"

    with pytest.warns(UserWarning, match=expected_msg):
        add_restart_to_config(restart_path, config_path)


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


@patch('shortuuid.uuid')
def test_checkout_branch(mock_uuid):
    repo = setup_control_repository()

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=labdir)

    # Mock uuid1 value
    uuid1 = 'a1234567890'
    mock_uuid.return_value = uuid1

    with cd(ctrldir):
        # Test checkout new branch (with no existing metadata)
        checkout_branch(lab=lab,
                        branch_name="Branch1",
                        is_new_branch=True)
        metadata = Metadata(lab)

    # Check metadata was created and commited
    assert str(repo.active_branch) == "Branch1"
    assert metadata.experiment_name == f'{ctrldir_basename}-Branch1-a123456'
    assert metadata.uuid == uuid1

    expected_commit_msg = f"Updated metadata. Experiment uuid: {uuid1}"
    assert repo.head.commit.message == expected_commit_msg
    branch_1_commit_hash = repo.active_branch.object.hexsha

    # Mock uuid2 value
    uuid2 = 'b1234567890'
    mock_uuid.return_value = uuid2

    with cd(ctrldir):
        # Test checkout new branch from branch with existing metadata
        checkout_branch(lab=lab,
                        branch_name="Branch2",
                        is_new_branch=True,
                        start_point="Branch1")
        metadata = Metadata(lab)

    # Check metadata has been updated and commited
    assert str(repo.active_branch) == "Branch2"
    assert metadata.experiment_name == f'{ctrldir_basename}-Branch2-b123456'
    assert metadata.uuid == uuid2

    expected_commit_msg = f"Updated metadata. Experiment uuid: {uuid2}"
    assert repo.head.commit.message == expected_commit_msg

    with cd(ctrldir):
        # Test checkout existing branch with existing metadata
        checkout_branch(lab=lab,
                        branch_name="Branch1")
        metadata = Metadata(lab)

    # Check metadata and commit has not changed on Branch1
    assert str(repo.active_branch) == "Branch1"
    assert metadata.experiment_name == f'{ctrldir_basename}-Branch1-a123456'
    assert metadata.uuid == uuid1

    # Assert commit hash is the same
    assert repo.active_branch.object.hexsha == branch_1_commit_hash


@patch('shortuuid.uuid')
def test_checkout_existing_branches_with_no_metadata(mock_uuid):
    repo = setup_control_repository()
    main_commit = repo.active_branch.object.hexsha

    # Create new branch
    repo.create_head("Branch1")

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=labdir)

    # Mock uuid1 value
    uuid1 = 'a1234567890'
    mock_uuid.return_value = uuid1

    with cd(ctrldir):
        # Test checkout existing branch with no existing metadata
        checkout_branch(lab=lab,
                        branch_name="Branch1")
        metadata = Metadata(lab)

    # Check metadata was created and commited
    assert str(repo.active_branch) == "Branch1"
    assert metadata.experiment_name == f'{ctrldir_basename}-Branch1-a123456'
    assert metadata.uuid == uuid1

    expected_commit_msg = f"Updated metadata. Experiment uuid: {uuid1}"
    assert repo.head.commit.message == expected_commit_msg

    # Create new branch - from main commit
    repo.create_head("Branch2", commit=main_commit)
    # Make experiment archive - This function creates legacy experiment archive
    make_expt_archive_dir(type='restart')

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=labdir)

    # Mock uuid1 value
    uuid2 = 'b1234567890'
    mock_uuid.return_value = uuid2

    with cd(ctrldir):
        # Test checkout existing branch (with no existing metadata)
        # But crucially with archive
        checkout_branch(lab=lab,
                        branch_name="Branch2")
        metadata = Metadata(lab)

    # Check metadata was created and commited
    assert str(repo.active_branch) == "Branch2"

    # Check for legacy experiment name
    assert metadata.experiment_name == f'{ctrldir_basename}'
    assert metadata.uuid == uuid2

    expected_commit_msg = f"Updated metadata. Experiment uuid: {uuid2}"
    assert repo.head.commit.message == expected_commit_msg

    # Note: new experiments branches created with payu checkout
    # can work with existing repo's but using git branch to create branch
    # will result in branch using the same archive (as it worked before branch
    # support)


@patch('shortuuid.uuid')
def test_checkout_new_branch_existing_legacy_archive(mock_uuid):
    # Using payu checkout new branch should generate new uuid,
    # and experiment name - even if there's a legacy archive
    repo = setup_control_repository()

    # Add archive under legacy name
    restart_path = Path(make_expt_archive_dir(type='restart'))

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=labdir)

    # Mock uuid1 value
    uuid1 = 'a1234567890'
    mock_uuid.return_value = uuid1

    with cd(ctrldir):
        # Test checkout new branch (with no existing metadata)
        checkout_branch(lab=lab,
                        branch_name="Branch1",
                        is_new_branch=True,
                        restart_path=restart_path,
                        config_path=config_path)
        metadata = Metadata(lab)

    # Check metadata was created and commited - with branch-uuid aware name
    assert str(repo.active_branch) == "Branch1"
    assert metadata.experiment_name == f'{ctrldir_basename}-Branch1-a123456'
    assert metadata.uuid == uuid1

    expected_commit_msg = f"Updated metadata. Experiment uuid: {uuid1}"
    assert repo.head.commit.message == expected_commit_msg

    # Check restart path was added to configuration file
    config = read_config(config_path)
    assert config['restart'] == str(restart_path)


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

    # Check new commit added
    cloned_repo = git.Repo(cloned_repo_path)
    expected_commit_msg = f"Updated metadata. Experiment uuid: {uuid1}"
    assert cloned_repo.head.commit.message == expected_commit_msg
    assert str(cloned_repo.active_branch) == 'Branch1'

    # Check metadata
    with cd(cloned_repo_path):
        lab = payu.laboratory.Laboratory(lab_path=labdir)
        metadata = Metadata(lab)

    assert metadata.uuid == uuid1
    assert metadata.experiment_name == 'clonedRepo-Branch1-a123456'

    cloned_repo.git.checkout(source_main_branch)

    # Test clone of a clone - adding a new branch
    uuid2 = 'b1234567890'
    mock_uuid.return_value = uuid2

    # Run clone
    with cd(tmpdir):
        clone(cloned_repo_path, Path('clonedRepo2'),
              lab_path=labdir, new_branch_name='Branch2', branch='Branch1')

    # Check new commit added
    cloned_repo2 = git.Repo(tmpdir / 'clonedRepo2')
    expected_commit_msg = f"Updated metadata. Experiment uuid: {uuid2}"
    assert cloned_repo2.head.commit.message == expected_commit_msg
    assert [head.name for head in cloned_repo2.heads] == ['Branch1', 'Branch2']
