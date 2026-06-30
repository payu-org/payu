import json
import os
import copy
import shutil

import pytest

import payu

from test.common import cd
from test.common import tmpdir, ctrldir, labdir, expt_archive_dir
from test.common import config as config_orig
from test.common import metadata as metadata_orig
from test.common import write_config
from test.common import make_all_files, make_random_file, write_metadata
from test.common import make_expt_archive_dir

verbose = True

# Global config
config = copy.deepcopy(config_orig)

# Enable metadata
config.pop('metadata')

@pytest.fixture(autouse=True)
def setup_module(setup_test_dir):
    """
    Put any test-wide setup code in here, e.g. creating test files.
    Files created here will be automatically cleaned up by `setup_test_dir` fixture after tests.
    """
    make_all_files()
    write_metadata()

    # Create 5 restarts and outputs
    for dir_type in ['restart', 'output']:
        for i in range(5):
            path = make_expt_archive_dir(type=dir_type, index=i)
            make_random_file(os.path.join(path, f'test-{dir_type}00{i}-file'))

    yield


def setup_sync(additional_config, monkeypatch, add_envt_vars=None):
    """Given additional configuration and envt_vars, return initialised
    class used to build/run rsync commands"""

    # Clean up all environment variables that may affect sync
    for var in ['PAYU_CURRENT_RUN', 'PAYU_SYNC_IGNORE_LAST', 'PAYU_SYNC_RESTARTS']:
        monkeypatch.delenv(var, raising=False)

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
            monkeypatch.setenv(var, value)

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


def test_filter_previous_runs(monkeypatch):
    """
    Test filter_previous_runs pick up runs <= the current run.
    filter_previous_runs expects to have sorted directories from lowest to highest as inputs.
    """
    # Set current run to 3
    monkeypatch.setenv("PAYU_CURRENT_RUN", "999")

    all_dirs = ['output997', 'output998', 'output999', 'output1001', 'output1002']
    prefix = 'output'
    
    expected = ['output997', 'output998', 'output999']
    result = payu.sync.filter_previous_runs(all_dirs, prefix=prefix)
    
    assert result == expected


def test_filter_previous_runs_no_current_run(monkeypatch):
    """Test filter_previous_runs returns all dirs when PAYU_CURRENT_RUN is not set."""
    
    monkeypatch.delenv("PAYU_CURRENT_RUN", raising=False)

    all_dirs = ['output997', 'output998', 'output999', 'output1001', 'output1002']
    prefix = 'output'

    result = payu.sync.filter_previous_runs(all_dirs, prefix=prefix)
    assert result == all_dirs


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
def test_add_outputs_to_sync(monkeypatch, envt_vars, expected_outputs,
                             expected_protected_outputs):
    sync = setup_sync(additional_config={}, monkeypatch=monkeypatch, add_envt_vars=envt_vars)

    # Test function
    sync.add_outputs_to_sync()

    # Assert expected outputs and protected outputs are added
    assert_expected_archive_paths(sync.source_paths,
                                  expected_outputs,
                                  expected_protected_outputs)


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
def test_restarts_to_sync(monkeypatch,add_config, envt_vars,
                          expected_restarts, expected_protected_restarts):
    sync = setup_sync(add_config, monkeypatch, envt_vars)

    # Test function
    sync.add_restarts_to_sync()

    # Assert expected restarts and protected restarts are added
    assert_expected_archive_paths(sync.source_paths,
                                  expected_restarts,
                                  expected_protected_restarts)


@pytest.mark.parametrize(
    "config_sync_path, expected_sync_dest",
    [
        ({"sync" : {
            "base_path": str(tmpdir)
        }}, 
        str(tmpdir)+"/expt_name/"),
        ({"sync" : {
            "path": str(tmpdir) + "/mom6_sync/"
        }},
        str(tmpdir) + "/mom6_sync/"),
        ({"sync" : {
            "base_path": str(tmpdir),
            "path": str(tmpdir) + "/mom6_sync/"
        }},
        str(tmpdir) + "/mom6_sync/"),
        ({"sync" : {
            "url": "test.domain",
            "user": "test-usr",
            "path": str(tmpdir) + "/mom6_sync/"
        }},
        "test-usr@test.domain:"+str(tmpdir) + "/mom6_sync/")
    ]
)

def test_set_destination_path(monkeypatch, config_sync_path, expected_sync_dest):
    """Test setting destination path with different combinations of
    base_path, path, url and user"""
    additional_config = config_sync_path
    sync = setup_sync(additional_config=additional_config, monkeypatch=monkeypatch)
    sync.expt.name = "expt_name"

    # Test destination_path
    sync.set_destination_path()
    assert sync.destination_path == expected_sync_dest


def test_set_destination_path_value_error(monkeypatch):
    """Test value error raised when path is not set"""
    sync = setup_sync(additional_config={}, monkeypatch=monkeypatch)
    with pytest.raises(ValueError, match="payu: error: Sync path is not defined."):
        sync.set_destination_path()


@pytest.mark.parametrize(
    "existing_metadata, path_for_sync, path_for_metadata",
    [
        (   # Matching UUIDs
            metadata_orig,
            tmpdir / "sync_dir", 
            tmpdir / "sync_dir" / "metadata.yaml"
        ),
        (   # No UUID in metadata.yaml in sync dir
            {},
            tmpdir / "sync_dir", 
            tmpdir / "sync_dir" / "metadata.yaml"
        ),
        (   # No metadata.yaml in desinated sync dir
            {},
            tmpdir / "sync_dir",
            tmpdir / "diff_sync_dir" / "metadata.yaml")
    ]
)
def test_check_uuid(monkeypatch, existing_metadata, path_for_sync, path_for_metadata):
    """Test check_uuid pass when UUIDs match, no UUID and no metadata.yaml"""
    # First, make sure the sync dir and metadata.yaml path exist
    path_for_sync.mkdir(parents=True, exist_ok=True)
    path_for_metadata.parent.mkdir(parents=True, exist_ok=True)

    # Write metadata.yaml
    write_metadata(metadata = existing_metadata, path=path_for_metadata)
    
    additional_config = {
        "sync": {
            "path": str(path_for_sync),
        }
    }
    sync = setup_sync(additional_config=additional_config, monkeypatch=monkeypatch)

    # Test destination_path
    sync.set_destination_path()
    assert sync.destination_path == str(path_for_sync)

def test_check_uuid_value_error(monkeypatch):
    """Test check_uuid raises ValueError when UUIDs do not match"""
    # First, set up a metadata.yaml with `different-UUID` in the destination sync path
    sync_dir = tmpdir / "sync_dir"
    sync_dir.mkdir(parents=True, exist_ok=True)
    existing_metadata = {
        "experiment_uuid": "different-UUID",
    }   
    write_metadata(existing_metadata, path=sync_dir / "metadata.yaml")
    
    additional_config = {
        "sync": {
            "path": str(sync_dir),
        }
    }
    sync = setup_sync(additional_config=additional_config, monkeypatch=monkeypatch)

    # Test check_uuid raises ValueError
    with pytest.raises(ValueError, match="payu: error: Mismatched experiment UUIDs in sync destination."):
        sync.set_destination_path()

@pytest.mark.parametrize(
    "add_config, expected_excludes",
    [
        (
            {
                "sync": {
                    "exclude": ["iceh.????-??-??.nc", "*-DEPRECATED"]
                },
            }, ("--exclude iceh.????-??-??.nc --exclude *-DEPRECATED")
        ),
        (
            {
                "sync": {
                    "exclude_uncollated": False
                },
            }, ""
        ),
        (
            {
                "sync": {
                    "exclude_uncollated": True,
                },
            }, "--exclude *.nc.*"
        ),
        (
            {
                "sync": {
                    "exclude_uncollated": True,
                    "exclude": ["iceh.????-??-??.nc"]
                },
            }, "--exclude iceh.????-??-??.nc --exclude *.nc.*"
        ),
        (
            {
                "sync": {
                    "exclude_uncollated": True,
                    "exclude": ["iceh.????-??-??.nc", "*.nc.*"]
                },
            }, "--exclude iceh.????-??-??.nc --exclude *.nc.*"
        ),
        (
            {
                "sync": {
                    "rsync_flags": ["--exclude *.nc.*"],
                    "exclude_uncollated": True,
                },
            }, ""
        )
    ])
def test_set_excludes_flags(monkeypatch, add_config, expected_excludes):
    sync = setup_sync(additional_config=add_config, monkeypatch=monkeypatch)

    # Test setting excludes
    sync.set_excludes_flags()
    assert sync.excludes == expected_excludes


def test_sync(monkeypatch):
    # Add some logs
    pbs_logs_path = os.path.join(expt_archive_dir, 'pbs_logs')
    os.makedirs(pbs_logs_path)
    log_filename = 'test_s.e1234'
    test_log_content = 'Test log file content'
    with open(os.path.join(pbs_logs_path, log_filename), 'w') as f:
        f.write(test_log_content)

    # Add some job files
    payu_jobs_path = os.path.join(expt_archive_dir, 'payu_jobs')
    os.makedirs(payu_jobs_path)
    job_filename = 'test-id.json'
    job_content = {"job_id": "test-id"}
    with open(os.path.join(payu_jobs_path, job_filename), 'w') as f:
        json.dump(job_content, f)

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
    sync = setup_sync(additional_config, monkeypatch, add_envt_vars={'PAYU_CURRENT_RUN': '4'})

    # Function to test
    sync.run()

    expected_dirs_synced = {'output000', 'output001', 'output002',
                            'output003', 'output004',
                            'payu_jobs', 'pbs_logs', 'metadata.yaml'}

    # Test output is moved to remote dir
    assert set(os.listdir(remote_archive)) == expected_dirs_synced

    # Test inner log files are copied
    remote_log_path = os.path.join(remote_archive, 'pbs_logs', log_filename)
    assert os.path.exists(remote_log_path)

    with open(remote_log_path, 'r') as f:
        assert test_log_content == f.read()

    # Test payu_jobs are copied
    remote_job_path = os.path.join(remote_archive, 'payu_jobs', job_filename)
    assert os.path.exists(remote_job_path)

    with open(remote_job_path, 'r') as f:
        assert json.load(f) == job_content

    # Check nested output dirs are synced
    assert os.path.exists(os.path.join(remote_archive, nested_output_dirs))

    # Check that uncollated files are also synced by default
    assert os.path.exists(os.path.join(remote_archive, uncollated_file))
    assert os.path.exists(os.path.join(remote_archive, collated_file))

    # Check synced file still exist locally
    local_archive_dirs = os.listdir(expt_archive_dir)
    for dir in expected_dirs_synced:
        assert dir in local_archive_dirs

    # Test sync with remove synced files locally flag
    additional_config['sync']['remove_local_files'] = True
    sync = setup_sync(additional_config, monkeypatch)
    sync.run()

    # Check synced files are removed from local archive
    # Except for the protected paths (last output in this case)
    for output in ['output000', 'output001', 'output002', 'output003']:
        file_path = os.path.join(expt_archive_dir, output, f'test-{output}-file')
        print(f"Checking {file_path} is removed")
        assert not os.path.exists(file_path)

    last_output_path = os.path.join(expt_archive_dir, 'output004')
    last_output_file = os.path.join(last_output_path, f'test-output004-file')
    assert os.path.exists(last_output_file)

    # Test sync with remove synced dirs flag as well
    additional_config['sync']['remove_local_dirs'] = True
    sync = setup_sync(additional_config, monkeypatch)
    sync.run()

    # Assert synced output dirs removed (except for the last output)
    local_archive_dirs = os.listdir(expt_archive_dir)
    for output in ['output000', 'output001', 'output002', 'output003']:
        assert output not in local_archive_dirs
    assert 'output004' in local_archive_dirs

    # Assert that payu_jobs are not removed since they are protected
    assert 'payu_jobs' in local_archive_dirs

def test_sync_jobs_file_with_excludes(monkeypatch):
    """Test job files are synced even when excludes are set to exclude *.json files"""
    # Add some job files
    payu_jobs_path = os.path.join(expt_archive_dir, 'payu_jobs')
    os.makedirs(payu_jobs_path)
    job_filename = 'test-id.json'
    job_content = {"job_id": "test-id"}
    with open(os.path.join(payu_jobs_path, job_filename), 'w') as f:
        json.dump(job_content, f)

    # Add a json file to the output dir that should be excluded
    output_json_file = os.path.join(expt_archive_dir, 'output000', 'test_output.json')
    with open(output_json_file, 'w') as f:
        json.dump({"test": "output"}, f)

    # Remote archive path
    remote_archive = tmpdir / 'remote'

    additional_config = {
        "sync": {
            "path": str(remote_archive),
            "exclude": ["*.json"]
        }
    }
    sync = setup_sync(additional_config, monkeypatch, add_envt_vars={'PAYU_CURRENT_RUN': '4'})

    # Function to test
    sync.run()

    # Test json output is not synced due to excludes
    assert not os.path.exists(os.path.join(remote_archive, 'output000', 'test_output.json'))

    # Test payu_jobs are still copied
    remote_job_path = os.path.join(remote_archive, 'payu_jobs', job_filename)
    with open(remote_job_path, 'r') as f:
        assert json.load(f) == job_content
