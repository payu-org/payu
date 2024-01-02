import os
import copy
import shutil

import pytest

import payu

from test.common import cd
from test.common import tmpdir, ctrldir, labdir, expt_archive_dir
from test.common import config as config_orig
from test.common import write_config
from test.common import make_all_files, make_random_file, write_metadata
from test.common import make_expt_archive_dir

verbose = True

# Global config
config = copy.deepcopy(config_orig)

# Enable metadata
config.pop('metadata')
pytestmark = pytest.mark.filterwarnings(
    "ignore::payu.git_utils.PayuGitWarning")


def setup_module(module):
    """
    Put any test-wide setup code in here, e.g. creating test files
    """
    if verbose:
        print("setup_module      module:%s" % module.__name__)

    # Should be taken care of by teardown, in case remnants lying around
    try:
        shutil.rmtree(tmpdir)
    except FileNotFoundError:
        pass

    try:
        tmpdir.mkdir()
        labdir.mkdir()
        ctrldir.mkdir()
        make_all_files()
        write_metadata()
    except Exception as e:
        print(e)

    # Create 5 restarts and outputs
    for dir_type in ['restart', 'output']:
        for i in range(5):
            path = make_expt_archive_dir(type=dir_type, index=i)
            make_random_file(os.path.join(path, f'test-{dir_type}00{i}-file'))


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


def setup_sync(additional_config, add_envt_vars=None):
    """Given additional configuration and envt_vars, return initialised
    class used to build/run rsync commands"""
    # Set experiment config
    test_config = copy.deepcopy(config)
    test_config.update(additional_config)
    write_config(test_config)

    # Set up Experiment
    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        experiment = payu.experiment.Experiment(lab, reproduce=False)

    # Set enviroment vars
    if add_envt_vars is not None:
        for var, value in add_envt_vars.items():
            os.environ[var] = value

    return payu.sync.SyncToRemoteArchive(experiment)


def assert_expected_archive_paths(source_paths,
                                  expected_dirs,
                                  expected_protected_dirs):
    """Check given source archive source paths that it includes
    the expected dirs to sync"""
    dirs, protected_dirs = [], []
    for source_path in source_paths:
        path = source_path.path
        assert os.path.dirname(path) == str(expt_archive_dir)

        dir = os.path.basename(path)
        if source_path.protected:
            protected_dirs.append(dir)
        else:
            dirs.append(dir)

    assert dirs == expected_dirs
    assert protected_dirs == expected_protected_dirs


@pytest.mark.parametrize(
    "envt_vars, expected_outputs, expected_protected_outputs",
    [
        (
            {},
            ['output000', 'output001', 'output002', 'output003'], ['output004']
        ),
        (
            {'PAYU_SYNC_IGNORE_LAST': 'True'},
            ['output000', 'output001', 'output002', 'output003'], []
        ),
    ])
def test_add_outputs_to_sync(envt_vars, expected_outputs,
                             expected_protected_outputs):
    sync = setup_sync(additional_config={}, add_envt_vars=envt_vars)

    # Test function
    sync.add_outputs_to_sync()

    # Assert expected outputs and protected outputs are added
    assert_expected_archive_paths(sync.source_paths,
                                  expected_outputs,
                                  expected_protected_outputs)

    # Tidy up test - Remove any added enviroment variables
    for envt_var in envt_vars.keys():
        del os.environ[envt_var]


@pytest.mark.parametrize(
    "add_config, envt_vars, expected_restarts, expected_protected_restarts",
    [
        (
            {
                "sync": {
                    'restarts': True
                },
                "restart_freq": 5
            }, {},
            [], ['restart000']
        ),
        (
            {
                "sync": {
                    'restarts': True
                },
                "restart_freq": 2
            }, {},
            ['restart000', 'restart002'], ['restart004']
        ),
        (
            {
                "sync": {
                    "restarts": True
                },
                "restart_freq": 2
            }, {'PAYU_SYNC_IGNORE_LAST': 'True'},
            ['restart000', 'restart002'], []
        ),
        (
            {"restart_freq": 3}, {'PAYU_SYNC_RESTARTS': 'True'},
            ['restart000', 'restart001', 'restart002'],
            ['restart003', 'restart004']
        ),
    ])
def test_restarts_to_sync(add_config, envt_vars,
                          expected_restarts, expected_protected_restarts):
    sync = setup_sync(add_config, envt_vars)

    # Test function
    sync.add_restarts_to_sync()

    # Assert expected restarts and protected restarts are added
    assert_expected_archive_paths(sync.source_paths,
                                  expected_restarts,
                                  expected_protected_restarts)

    # Tidy up test - Remove any added enviroment variables
    for envt_var in envt_vars.keys():
        del os.environ[envt_var]


def test_set_destination_path():
    additional_config = {
        "sync": {
            "url": "test.domain",
            "user": "test-usr",
            "path": "remote/path",
        }}
    sync = setup_sync(additional_config=additional_config)

    # Test destination_path
    sync.set_destination_path()
    assert sync.destination_path == "test-usr@test.domain:remote/path"

    # Test value error raised when path is not set
    sync = setup_sync(additional_config={})
    with pytest.raises(ValueError):
        sync.set_destination_path()


@pytest.mark.parametrize(
    "add_config, expected_excludes",
    [
        (
            {
                "sync": {
                    "exclude": ["iceh.????-??-??.nc", "*-DEPRECATED"]
                },
                "collate": {
                    "enable": True
                }
            }, ("--exclude iceh.????-??-??.nc --exclude *-DEPRECATED"
                " --exclude *.nc.*")
        ),
        (
            {
                "sync": {
                    "exclude_uncollated": False
                },
                "collate": {
                    "enable": True
                }
            }, ""
        ),
        (
            {
                "sync": {
                    "exclude": "*-DEPRECATED"
                },
                "collate": {
                    "enable": False
                }
            }, "--exclude *-DEPRECATED"
        )
    ])
def test_set_excludes_flags(add_config, expected_excludes):
    sync = setup_sync(additional_config=add_config)

    # Test setting excludes
    sync.set_excludes_flags()
    assert sync.excludes == expected_excludes


def test_sync():
    # Add some logs
    pbs_logs_path = os.path.join(expt_archive_dir, 'pbs_logs')
    os.makedirs(pbs_logs_path)
    log_filename = 'test_s.e1234'
    test_log_content = 'Test log file content'
    with open(os.path.join(pbs_logs_path, log_filename), 'w') as f:
        f.write(test_log_content)

    # Add nested directories to output000
    nested_output_dirs = os.path.join('output000', 'submodel', 'test_sub-dir')
    nested_output_path = os.path.join(expt_archive_dir, nested_output_dirs)
    os.makedirs(nested_output_path)

    # Add empty uncollated file
    uncollated_file = os.path.join(nested_output_dirs, 'test0.res.nc.0000')
    with open(os.path.join(expt_archive_dir, uncollated_file), 'w'):
        pass

    # Add empty collated file
    collated_file = os.path.join(nested_output_dirs, 'test1.res.nc')
    with open(os.path.join(expt_archive_dir, collated_file), 'w'):
        pass

    # Remote archive path
    remote_archive = tmpdir / 'remote'

    additional_config = {
        "sync": {
            "path": str(remote_archive),
            "runlog": False
        }
    }
    sync = setup_sync(additional_config)

    # Function to test
    sync.run()

    expected_dirs_synced = {'output000', 'output001', 'output002',
                            'output003', 'output004',
                            'pbs_logs', 'metadata.yaml'}

    # Test output is moved to remote dir
    assert set(os.listdir(remote_archive)) == expected_dirs_synced

    # Test inner log files are copied
    remote_log_path = os.path.join(remote_archive, 'pbs_logs', log_filename)
    assert os.path.exists(remote_log_path)

    with open(remote_log_path, 'r') as f:
        assert test_log_content == f.read()

    # Check nested output dirs are synced
    assert os.path.exists(os.path.join(remote_archive, nested_output_dirs))

    # Check that uncollated files are not synced by default
    assert not os.path.exists(os.path.join(remote_archive, uncollated_file))
    assert os.path.exists(os.path.join(remote_archive, collated_file))

    # Check synced file still exist locally
    local_archive_dirs = os.listdir(expt_archive_dir)
    for dir in expected_dirs_synced:
        assert dir in local_archive_dirs

    # Test sync with remove synced files locally flag
    additional_config['sync']['remove_local_files'] = True
    sync = setup_sync(additional_config)
    sync.run()

    # Check synced files are removed from local archive
    # Except for the protected paths (last output in this case)
    for output in ['output000', 'output001', 'output002', 'output003']:
        file_path = os.path.join(expt_archive_dir, dir, f'test-{output}-file')
        assert not os.path.exists(file_path)

    last_output_path = os.path.join(expt_archive_dir, 'output004')
    last_output_file = os.path.join(last_output_path, f'test-output004-file')
    assert os.path.exists(last_output_file)

    # Test sync with remove synced dirs flag as well
    additional_config['sync']['remove_local_dirs'] = True
    sync = setup_sync(additional_config)
    sync.run()

    # Assert synced output dirs removed (except for the last output)
    local_archive_dirs = os.listdir(expt_archive_dir)
    for output in ['output000', 'output001', 'output002', 'output003']:
        assert output not in local_archive_dirs
    assert 'output004' in local_archive_dirs
