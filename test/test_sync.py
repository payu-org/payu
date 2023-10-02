import os
import copy
import shutil

import pytest

import payu

from test.common import cd
from test.common import tmpdir, ctrldir, labdir, expt_archive_dir
from test.common import config as config_orig
from test.common import write_config
from test.common import make_all_files
from test.common import make_expt_archive_dir

verbose = True

# Global config
config = copy.deepcopy(config_orig)


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
    except Exception as e:
        print(e)

    # Create 5 restarts and outputs
    for dir_type in ['restart', 'output']:
        for i in range(5):
            make_expt_archive_dir(type=dir_type, index=i)


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


@pytest.mark.parametrize(
    "additional_config, expected_dirs_to_sync",
    [
        (
            {},
            ['output000', 'output001', 'output002', 'output003', 'output004']
        ),
        (
            {
                "sync": {
                    'restarts': True
                },
                "restart_freq": 5
            },
            ['output000', 'output001', 'output002', 'output003', 'output004',
             'restart000']
        ),
        (
            {
                "sync": {
                    'restarts': True
                },
                "restart_freq": 2
            },
            ['output000', 'output001', 'output002', 'output003', 'output004',
             'restart000', 'restart002', 'restart004']
        ),
    ])
def test_get_archive_paths_to_sync(additional_config, expected_dirs_to_sync):
    # Write config
    test_config = copy.deepcopy(config)
    test_config.update(additional_config)
    write_config(test_config)

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)

        # Function to test
        src_paths = expt.get_archive_paths_to_sync()

    dirs = []
    for path in src_paths:
        assert os.path.dirname(path) == str(expt_archive_dir)
        dirs.append(os.path.basename(path))

    assert dirs == expected_dirs_to_sync


@pytest.mark.parametrize(
    "set_enviroment_var, expected_dirs_to_sync",
    [
        (
            'PAYU_SYNC_IGNORE_LAST',
            ['output000', 'output001', 'output002', 'output003']
        ),
        (
            'PAYU_SYNC_RESTARTS',
            ['output000', 'output001', 'output002', 'output003', 'output004',
             'restart000', 'restart001', 'restart002', 'restart003',
             'restart004']
        ),
    ])
def test_get_archive_paths_to_sync_environ_vars(set_enviroment_var,
                                                expected_dirs_to_sync):
    # Write config
    write_config(config)

    os.environ[set_enviroment_var] = 'True'

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)

        # Function to test
        src_paths = expt.get_archive_paths_to_sync()

    dirs = []
    for path in src_paths:
        assert os.path.dirname(path) == str(expt_archive_dir)
        dirs.append(os.path.basename(path))

    assert dirs == expected_dirs_to_sync

    # Tidy up test
    del os.environ[set_enviroment_var]


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
            "path": str(remote_archive)
        }
    }

    # Write config
    test_config = copy.deepcopy(config)
    test_config.update(additional_config)
    write_config(test_config)

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)

        # Function to test
        expt.sync()

    expected_dirs_synced = ['output000', 'output001', 'output002',
                            'output003', 'output004', 'pbs_logs']

    # Test output is moved to remote dir
    assert os.listdir(remote_archive) == expected_dirs_synced

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
