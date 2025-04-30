import copy
import shutil
from pathlib import Path

import pytest
import git
from ruamel.yaml import YAML
from unittest.mock import patch

from payu.branch import add_restart_to_config, check_restart, switch_symlink
from payu.branch import checkout_branch, clone, list_branches, PayuBranchError
from payu.metadata import MetadataWarning
from payu.fsops import read_config

from test.common import cd
from test.common import tmpdir, ctrldir, labdir, archive_dir
from test.common import ctrldir_basename
from test.common import config as config_orig, write_config
from test.common import config_path, metadata_path
from test.common import make_expt_archive_dir


# Global config - Remove set experiment and metadata config
config = copy.deepcopy(config_orig)
config.pop("experiment")
config.pop("metadata")


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
    """Return an new control repository"""
    if set_config:
        write_config(config, path=(path / "config.yaml"))
    else:
        (path / "newFile").touch()
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
    restart_path = tmpdir / "archive" / "tmpRestart"
    restart_path.mkdir(parents=True)

    expected_config = expected_config.format(restart_path)

    with config_path.open("w") as file:
        file.write(test_config)

    # Function to test
    with cd(ctrldir):
        add_restart_to_config(restart_path, config_path)

    with config_path.open("r") as file:
        updated_config = file.read()

    # Test order, comments are preserved
    assert updated_config == expected_config


def test_check_restart_relative_path():
    """Test an relative restart path is resolved to an absolute path"""
    restart_path = tmpdir / "archive" / "tmpRestart"
    restart_path.mkdir(parents=True)

    with cd(tmpdir):
        relative_restart_path = Path("archive") / "tmpRestart"
        assert not relative_restart_path.is_absolute()

        resolved_path = check_restart(relative_restart_path)
        assert resolved_path.is_absolute()


def test_check_restart_with_non_existent_restart():
    """Test restart path that does not exist raises a warning"""
    restart_path = tmpdir / "restartDNE"

    expected_msg = (f"Given restart path {restart_path} does not exist. "
                    f"Skipping setting 'restart' in config file")

    with cd(ctrldir):
        with pytest.warns(UserWarning, match=expected_msg):
            restart_path = check_restart(restart_path, labdir / "archive")

    assert restart_path is None


def test_check_restart_with_pre_existing_restarts_in_archive():
    """Test pre-existing restarts in archive raises a warning"""
    # Create pre-existing restart in archive
    archive_path = labdir / "archive"
    (archive_path / "restart000").mkdir(parents=True)

    # Create restart path in different archive
    restart_path = labdir / "different_archive" / "restart000"
    restart_path.mkdir(parents=True)

    expected_msg = (
        f"Pre-existing restarts found in archive: {archive_path}."
        f"Skipping adding 'restart: {restart_path}' to config file"
    )

    with cd(ctrldir):
        with pytest.warns(UserWarning, match=expected_msg):
            restart_path = check_restart(restart_path, archive_path)

    assert restart_path is None


def test_switch_symlink_when_symlink_and_archive_exists():
    # Pre-existing experiment symlink
    lab_archive = labdir / "archive"
    previous_archive_dir = lab_archive / "Experiment0"
    previous_archive_dir.mkdir(parents=True)

    archive_symlink = ctrldir / "archive"
    archive_symlink.symlink_to(previous_archive_dir)

    # New Experiment - Existing archive
    experiment_name = "Experiment1"
    archive_dir = lab_archive / experiment_name
    archive_dir.mkdir(parents=True)

    # Test Function
    switch_symlink(lab_archive, ctrldir, experiment_name, "archive")

    # Assert new symlink is created
    assert archive_symlink.exists() and archive_symlink.is_symlink()
    assert archive_symlink.resolve() == archive_dir


def test_switch_symlink_when_symlink_exists_but_no_archive():
    # Pre-existing experiment symlink
    lab_archive = labdir / "archive"
    previous_archive_dir = lab_archive / "Experiment0"
    previous_archive_dir.mkdir(parents=True)

    archive_symlink = ctrldir / "archive"
    archive_symlink.symlink_to(previous_archive_dir)

    # New Experiment
    experiment_name = "Experiment1"

    # Test Function
    switch_symlink(lab_archive, ctrldir, experiment_name, "archive")

    # Assert no symlink is created but previous one is removed
    assert not archive_symlink.exists()
    assert not archive_symlink.is_symlink()


def test_switch_symlink_when_no_symlink_exists_and_no_archive():
    # New Experiment
    experiment_name = "Experiment1"
    lab_archive = labdir / "archive"

    archive_symlink = ctrldir / "archive"

    # Test Function
    switch_symlink(lab_archive, ctrldir, experiment_name, "archive")

    # Assert no symlink
    assert not archive_symlink.exists()
    assert not archive_symlink.is_symlink()


def test_switch_symkink_when_previous_symlink_dne():
    # Point archive symlink to a directory that does not exist anymore
    lab_archive = labdir / "archive"
    previous_archive_dir = lab_archive / "ExperimentDNE"

    archive_symlink = ctrldir / "archive"
    archive_symlink.symlink_to(previous_archive_dir)

    # New Experiment
    experiment_name = "Experiment1"
    archive_dir = lab_archive / experiment_name
    archive_dir.mkdir(parents=True)

    # Test Function
    switch_symlink(lab_archive, ctrldir, experiment_name, "archive")

    # Assert new symlink is created
    assert archive_symlink.exists() and archive_symlink.is_symlink()
    assert archive_symlink.resolve() == archive_dir


def check_metadata(expected_uuid,
                   expected_experiment,
                   expected_parent_uuid=None,
                   metadata_file=metadata_path):
    """Helper function to read metadata file and assert changed as expected"""
    assert metadata_file.exists()
    metadata = YAML().load(metadata_file)
    assert metadata.get("experiment_uuid", None) == expected_uuid
    assert metadata.get("parent_experiment", None) == expected_parent_uuid

    # Assert archive exists for experiment name
    assert (archive_dir / expected_experiment / "metadata.yaml").exists()
    copied_metadata = YAML().load(metadata_file)
    assert copied_metadata == metadata


def check_branch_metadata(repo,
                          expected_current_branch,
                          expected_uuid,
                          expected_experiment,
                          expected_parent_uuid=None,
                          metadata_file=metadata_path):
    """Helper function for checking expected  branch and metadata"""
    # Check metadata
    check_metadata(expected_uuid,
                   expected_experiment,
                   expected_parent_uuid,
                   metadata_file=metadata_file)

    # Check cuurent branch
    assert str(repo.active_branch) == expected_current_branch

    # Check last commit message
    expected_commit_msg = f"Updated metadata. Experiment UUID: {expected_uuid}"
    assert repo.head.commit.message == expected_commit_msg


@patch("uuid.uuid4")
def test_checkout_branch(mock_uuid):
    repo = setup_control_repository()

    # Mock uuid1 value
    uuid1 = "8ddc1985-b7d0-4d4d-884f-061ecd90d478"
    mock_uuid.return_value = uuid1

    with cd(ctrldir):
        # Test checkout new branch (with no existing metadata)
        checkout_branch(branch_name="Branch1",
                        is_new_branch=True,
                        lab_path=labdir)

    # Check current branch, new commit was added, and metadata created
    branch1_experiment_name = f"{ctrldir_basename}-Branch1-8ddc1985"
    check_branch_metadata(repo,
                          expected_uuid=uuid1,
                          expected_current_branch="Branch1",
                          expected_experiment=branch1_experiment_name)

    # Save commit hash to check later on
    branch_1_commit_hash = repo.active_branch.object.hexsha

    # Mock uuid2 value
    uuid2 = "2de5b001-df08-4c0b-ab15-f47f8ad72929"
    mock_uuid.return_value = uuid2

    with cd(ctrldir):
        # Test checkout new branch from branch with existing metadata
        checkout_branch(branch_name="Branch2",
                        is_new_branch=True,
                        lab_path=labdir)

    # Check current branch, new commit was added, and metadata created
    branch2_experiment_name = f"{ctrldir_basename}-Branch2-2de5b001"
    check_branch_metadata(repo,
                          expected_uuid=uuid2,
                          expected_current_branch="Branch2",
                          expected_experiment=branch2_experiment_name)

    # Mock uuid3 value
    uuid3 = "98c99f06-260e-42cc-a23f-f113fae825e5"
    mock_uuid.return_value = uuid3

    with cd(ctrldir):
        # Test checkout new branch from starting branch with existing metadata
        checkout_branch(branch_name="Branch3",
                        is_new_branch=True,
                        start_point="Branch1",
                        lab_path=labdir)

    # Check current branch, new commit was added, and metadata created
    branch3_experiment_name = f"{ctrldir_basename}-Branch3-98c99f06"
    check_branch_metadata(repo,
                          expected_uuid=uuid3,
                          expected_current_branch="Branch3",
                          expected_experiment=branch3_experiment_name)

    # Check second to last commit was last commit on branch 1
    second_latest_commit = list(repo.iter_commits(max_count=2))[1]
    assert second_latest_commit.hexsha == branch_1_commit_hash

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


@patch("uuid.uuid4")
def test_checkout_existing_branch_with_no_metadata(mock_uuid):
    repo = setup_control_repository()

    # Create new branch
    repo.create_head("Branch1")

    # Mock uuid1 value
    uuid1 = "574ea2c9-2379-4484-86b4-1d1a0f820773"
    mock_uuid.return_value = uuid1
    expected_no_uuid_msg = (
        "No experiment uuid found in metadata. Generating a new uuid"
    )
    expected_no_archive_msg = (
        "No pre-existing archive found. Generating a new uuid"
    )

    with cd(ctrldir):
        # Test checkout existing branch with no existing metadata
        with pytest.warns(MetadataWarning, match=expected_no_uuid_msg):
            with pytest.warns(MetadataWarning, match=expected_no_archive_msg):
                checkout_branch(branch_name="Branch1",
                                lab_path=labdir)

    # Check metadata was created and commited
    branch1_experiment_name = f"{ctrldir_basename}-Branch1-574ea2c9"
    check_branch_metadata(repo,
                          expected_uuid=uuid1,
                          expected_current_branch="Branch1",
                          expected_experiment=branch1_experiment_name)


@patch("uuid.uuid4")
def test_checkout_branch_with_no_metadata_and_with_legacy_archive(mock_uuid):
    # Make experiment archive - This function creates legacy experiment archive
    make_expt_archive_dir(type="restart", index=0)

    # Setup repo
    repo = setup_control_repository()

    # Create new branch using git
    repo.create_head("Branch1")

    # Mock uuid1 value
    uuid1 = "df050eaf-c8bb-4b10-9998-e0202a1eabd2"
    mock_uuid.return_value = uuid1
    expected_no_uuid_msg = (
        "No experiment uuid found in metadata. Generating a new uuid"
    )

    with cd(ctrldir):
        # Test checkout existing branch (with no existing metadata)
        # and with pre-existing archive
        with pytest.warns(MetadataWarning, match=expected_no_uuid_msg):
            checkout_branch(branch_name="Branch1",
                            lab_path=labdir)

    # Check metadata was created and commited - with legacy experiment name
    branch1_experiment_name = ctrldir_basename
    check_branch_metadata(repo,
                          expected_uuid=uuid1,
                          expected_current_branch="Branch1",
                          expected_experiment=branch1_experiment_name)


@patch("uuid.uuid4")
def test_checkout_new_branch_existing_legacy_archive(mock_uuid):
    # Using payu checkout new branch should generate new uuid,
    # and experiment name - even if there"s a legacy archive
    repo = setup_control_repository()

    # Add archive under legacy name
    restart_path = Path(make_expt_archive_dir(type="restart"))

    # Mock uuid1 value
    uuid1 = "d4437aae-8370-4567-a698-94d00ba87cdc"
    mock_uuid.return_value = uuid1

    with cd(ctrldir):
        # Test checkout new branch (with no existing metadata)
        checkout_branch(branch_name="Branch1",
                        is_new_branch=True,
                        restart_path=restart_path,
                        config_path=config_path,
                        lab_path=labdir)

    # Check metadata was created and commited - with branch-uuid aware name
    branch1_experiment_name = f"{ctrldir_basename}-Branch1-d4437aae"
    check_branch_metadata(repo,
                          expected_uuid=uuid1,
                          expected_current_branch="Branch1",
                          expected_experiment=branch1_experiment_name)

    # Check restart path was added to configuration file
    config = read_config(config_path)
    assert config["restart"] == str(restart_path)


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


@patch("uuid.uuid4")
def test_checkout_branch_with_restart_path(mock_uuid):
    # Make experiment archive restart - starting with no metadata
    restart_path = tmpdir / "remote_archive" / "restart0123"
    restart_path.mkdir(parents=True)

    # Setup repo
    repo = setup_control_repository()

    # Mock uuid1 value
    uuid1 = "df050eaf-c8bb-4b10-9998-e0202a1eabd2"
    mock_uuid.return_value = uuid1

    with cd(ctrldir):
        # Test checkout with restart path with no metadata
        checkout_branch(is_new_branch=True,
                        branch_name="Branch1",
                        lab_path=labdir,
                        restart_path=restart_path)

    # Check metadata
    experiment1_name = f"{ctrldir_basename}-Branch1-df050eaf"
    check_branch_metadata(repo,
                          expected_current_branch='Branch1',
                          expected_uuid=uuid1,
                          expected_experiment=experiment1_name)

    # Create restart directory in Branch1 archive
    restart_path = archive_dir / experiment1_name / 'restart0123'
    restart_path.mkdir()

    # Mock uuid2 value
    uuid2 = "9cc04c9b-f13d-4f1d-8a35-87146a4381ef"
    mock_uuid.return_value = uuid2

    with cd(ctrldir):
        # Test checkout with restart path with metadata
        checkout_branch(is_new_branch=True,
                        branch_name="Branch2",
                        lab_path=labdir,
                        restart_path=restart_path)

    # Check metadta - Check parent experiment is experment 1 UUID
    experiment2_name = f"{ctrldir_basename}-Branch2-9cc04c9b"
    check_branch_metadata(repo,
                          expected_current_branch='Branch2',
                          expected_uuid=uuid2,
                          expected_experiment=experiment2_name,
                          expected_parent_uuid=uuid1)


@patch("payu.laboratory.Laboratory.initialize")
def test_checkout_laboratory_path_error(mock_lab_initialise):
    mock_lab_initialise.side_effect = PermissionError

    repo = setup_control_repository()
    current_commit = repo.active_branch.object.hexsha

    with cd(ctrldir):
        # Test raises a permission error
        with pytest.raises(PermissionError):
            checkout_branch(branch_name="Branch1",
                            is_new_branch=True,
                            lab_path=labdir)

    # Assert new commit has not been added
    assert repo.active_branch.object.hexsha == current_commit

    assert str(repo.active_branch) == "Branch1"
    assert not (ctrldir / "metadata.yaml").exists()

    # Test removing lab directory
    shutil.rmtree(labdir)
    mock_lab_initialise.side_effect = None
    with cd(ctrldir):
        # Test runs without an error - directory is initialised
        checkout_branch(branch_name="Branch2",
                        is_new_branch=True,
                        lab_path=labdir)

    # Assert new commit has been added
    assert repo.active_branch.object.hexsha != current_commit


@patch("uuid.uuid4")
def test_clone(mock_uuid):
    # Create a repo to clone
    source_repo_path = tmpdir / "sourceRepo"
    source_repo_path.mkdir()
    source_repo = setup_control_repository(path=source_repo_path)
    source_main_branch = str(source_repo.active_branch)

    # Create and checkout branch
    branch1 = source_repo.create_head("Branch1")
    branch1.checkout()

    # Mock uuid1 value
    uuid1 = "9cc04c9b-f13d-4f1d-8a35-87146a4381ef"
    mock_uuid.return_value = uuid1

    # Test clone
    cloned_repo_path = tmpdir / "clonedRepo"
    clone(str(source_repo_path), cloned_repo_path, lab_path=labdir)

    # Check new commit added and expected metadata
    cloned_repo = git.Repo(cloned_repo_path)
    metadata_file = cloned_repo_path / "metadata.yaml"
    check_branch_metadata(repo=cloned_repo,
                          expected_current_branch="Branch1",
                          expected_uuid=uuid1,
                          expected_experiment="clonedRepo-Branch1-9cc04c9b",
                          metadata_file=metadata_file)
    branch_1_commit_hash = cloned_repo.active_branch.object.hexsha

    cloned_repo.git.checkout(source_main_branch)

    # Test clone of a clone - adding a new branch
    uuid2 = "fd7b4804-d306-4a18-9d95-a8f565abfc9a"
    mock_uuid.return_value = uuid2

    # Run clone
    with cd(tmpdir):
        clone(str(cloned_repo_path), Path("clonedRepo2"),
              lab_path=labdir, new_branch_name="Branch2", branch="Branch1",
              parent_experiment=uuid1)

    # Check new commit added and expected metadata
    cloned_repo2 = git.Repo(tmpdir / "clonedRepo2")
    metadata_file = tmpdir / "clonedRepo2" / "metadata.yaml"
    check_branch_metadata(repo=cloned_repo2,
                          expected_current_branch="Branch2",
                          expected_uuid=uuid2,
                          expected_experiment="clonedRepo2-Branch2-fd7b4804",
                          expected_parent_uuid=uuid1,
                          metadata_file=metadata_file)

    # Check branched from Branch1
    second_latest_commit = list(cloned_repo2.iter_commits(max_count=2))[1]
    assert second_latest_commit.hexsha == branch_1_commit_hash

    # Check local branches
    assert [head.name for head in cloned_repo2.heads] == ["Branch1", "Branch2"]


@pytest.mark.parametrize(
    "start_point_type", ["commit", "tag"]
)
def test_clone_startpoint(start_point_type):
    # Create a repo to clone
    source_repo_path = tmpdir / "sourceRepo"
    source_repo_path.mkdir()
    source_repo = setup_control_repository(path=source_repo_path)

    # Create branch1
    branch1 = source_repo.create_head("Branch1")
    branch1_commit = branch1.object.hexsha
    if start_point_type == "tag":
        source_repo.create_tag('v1.0', ref=branch1.commit)
        start_point = 'v1.0'
    elif start_point_type == "commit":
        start_point = branch1_commit

    # Add another commit on main branch so the commit is different to branch1
    (source_repo_path / "mock_file.txt").touch()
    source_repo.index.add("mock_file.txt")
    source_repo.index.commit("Another commit with a mock file")

    source_repo_commit = source_repo.active_branch.object.hexsha
    assert source_repo_commit != branch1_commit

    # Run Clone
    cloned_repo_path = tmpdir / "clonedRepo"
    with cd(tmpdir):
        clone(
            repository=str(source_repo_path),
            directory=cloned_repo_path,
            lab_path=labdir,
            new_branch_name="Branch3",
            start_point=start_point
        )

    cloned_repo = git.Repo(cloned_repo_path)

    # Check branched starting from start point
    second_latest_commit = list(cloned_repo.iter_commits(max_count=2))[1]
    assert second_latest_commit.hexsha == branch1_commit

    # Latest commit is different (new commit from metadata)
    assert source_repo_commit != cloned_repo.active_branch.object.hexsha


def test_clone_startpoint_with_no_new_branch_error():
    """Test clone when -s/--start-point is used without -b/--new-branch"""
    # Create a repo to clone
    source_repo_path = tmpdir / "sourceRepo"
    source_repo_path.mkdir()
    source_repo = setup_control_repository(path=source_repo_path)

    # Create branch1
    branch1 = source_repo.create_head("Branch1")
    branch1_commit = branch1.object.hexsha

    expected_msg = (
        "Starting from a specific commit or tag requires a new branch "
        "name to be specified. Use the --new-branch/-b flag in payu clone "
        "to create a new git branch."
    )

    # Run Clone
    cloned_repo_path = tmpdir / "clonedRepo"
    with cd(tmpdir):
        with pytest.raises(PayuBranchError, match=expected_msg):
            clone(
                repository=str(source_repo_path),
                directory=cloned_repo_path,
                lab_path=labdir,
                start_point=branch1_commit,
            )

    # Check cloned repo is not created
    assert not cloned_repo_path.exists()


def test_clone_with_relative_restart_path():
    """Test clone with a restart path that is relative with respect to
    the directory in which the clone command is run from"""
    # Create a repo to clone
    source_repo_path = tmpdir / "sourceRepo"
    source_repo_path.mkdir()
    setup_control_repository(path=source_repo_path)

    # Create restart path
    restart_path = tmpdir / "archive" / "tmpRestart"
    restart_path.mkdir(parents=True)
    relative_restart_path = Path("archive") / "tmpRestart"

    cloned_repo_path = tmpdir / "clonedRepo"
    with cd(tmpdir):
        # Run clone
        clone(repository=str(source_repo_path),
              directory=cloned_repo_path,
              lab_path=labdir,
              restart_path=relative_restart_path)

    # Test restart was added to config.yaml file
    with cd(cloned_repo_path):
        config = read_config()

    assert config["restart"] == str(restart_path)


def add_and_commit_metadata(repo, metadata):
    """Helper function to create/update metadata file and commit"""
    metadata_path = ctrldir / "metadata.yaml"
    YAML().dump(metadata, metadata_path)
    repo.index.add("*")
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
    repo.index.add("*")
    repo.index.commit("Added config.yaml")

    # Checkout and add metadata to new branch
    branch2 = repo.create_head("Branch2")
    branch2.checkout()
    write_config(config)
    branch_2_metadata = {
        "experiment_uuid": "b12345678",
    }
    add_and_commit_metadata(repo, branch_2_metadata)

    # New branch with no uuid in metadata
    branch3 = repo.create_head("Branch3")
    branch3.checkout()
    branch_3_metadata = {
        "email": "test@email.com",
        "contact": "TestUser"
    }
    add_and_commit_metadata(repo, branch_3_metadata)

    # Test list branches
    with cd(ctrldir):
        list_branches()

    expected_printed_output = f"""* Current Branch: Branch3
    No UUID in metadata file
Branch: Branch1
    No metadata file found
Branch: Branch2
    experiment_uuid: b12345678
Branch: {main_branch_name}
    No config file found"""
    captured = capsys.readouterr()
    assert captured.out.strip() == expected_printed_output

    # Test list branches with verbose set
    with cd(ctrldir):
        list_branches(verbose=True)

    expected_verbose_output = f"""* Current Branch: Branch3
    email: test@email.com
    contact: TestUser
Branch: Branch1
    No metadata file found
Branch: Branch2
    experiment_uuid: b12345678
Branch: {main_branch_name}
    No config file found"""
    captured = capsys.readouterr()
    assert captured.out.strip() == expected_verbose_output

    # Test remote branches
    cloned_repo_path = tmpdir / "cloned_repo"
    repo.clone(cloned_repo_path)

    with cd(cloned_repo_path):
        list_branches(remote=True)
    expected_remote_output = f"""* Current Branch: Branch3
    No UUID in metadata file
Remote Branch: Branch1
    No metadata file found
Remote Branch: Branch2
    experiment_uuid: b12345678
Remote Branch: Branch3
    No UUID in metadata file
Remote Branch: HEAD
    No UUID in metadata file
Remote Branch: {main_branch_name}
    No config file found"""
    captured = capsys.readouterr()
    assert captured.out.strip() == expected_remote_output
