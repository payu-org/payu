from datetime import datetime
import json
import os
from pathlib import Path

import pytest
from unittest.mock import patch, Mock
import jsonschema

from payu.telemetry import get_external_telemetry_config, post_telemetry_data
from payu.telemetry import Telemetry
from payu.telemetry import (
    TELEMETRY_CONFIG,
    TELEMETRY_URL_FIELD,
    HOSTNAME_FIELD,
    TELEMETRY_SERVICE_NAME_FIELD,
    TELEMETRY_TOKEN_FIELD,
    TELEMETRY_HOST_FIELD,
)

TELEMETRY_1_0_0_SCHEMA_PATH = (
    Path(__file__).parent / "resources" / "schema" / "telemetry" / "1-0-0.json"
)


@pytest.fixture
def config_path(tmp_path):
    """Returns the path to the telemetry config file"""
    config_dir = tmp_path / "telemetry_config"
    config_dir.mkdir()
    return config_dir / "1-0-0.json"


@pytest.fixture
def setup_env(config_path, monkeypatch):
    """Set the telemetry config environment variable for the test"""
    monkeypatch.setenv(TELEMETRY_CONFIG, str(config_path.parent))


def test_get_external_telemetry_config_valid(setup_env, config_path):
    config_data = {
        TELEMETRY_URL_FIELD: "some/server/url",
        HOSTNAME_FIELD: "gadi",
        TELEMETRY_SERVICE_NAME_FIELD: "payu",
        TELEMETRY_TOKEN_FIELD: "some_token",
        TELEMETRY_HOST_FIELD: "some_host",
    }
    with open(config_path, 'w') as f:
        json.dump(config_data, f)

    result = get_external_telemetry_config()
    assert result == config_data


def test_get_external_telemetry_config_no_file(setup_env, config_path):
    expected_warning = (
        f"No config file found at {TELEMETRY_CONFIG}: {config_path}. "
        "Skipping posting telemetry"
    )
    with pytest.warns(UserWarning, match=expected_warning):
        result = get_external_telemetry_config()
        assert result is None


def test_get_external_telemetry_config_missing_fields(setup_env, config_path):
    config_data = {
        TELEMETRY_URL_FIELD: "some/server/url",
        TELEMETRY_SERVICE_NAME_FIELD: "payu",
        TELEMETRY_TOKEN_FIELD: "some_token",
    }
    with open(config_path, 'w') as f:
        json.dump(config_data, f)

    expected_warning = (
        f"Required field '{HOSTNAME_FIELD}' not found in "
        f"configuration file at {TELEMETRY_CONFIG}: {config_path}. "
        "Skipping posting telemetry"
    )
    with pytest.warns(UserWarning, match=expected_warning):
        result = get_external_telemetry_config()
        assert result is None


def test_get_external_telemetry_config_invalid_json(setup_env, config_path):
    with open(config_path, 'w') as f:
        f.write("{invalid_json")

    expected_warning = (
        f"Error parsing json in configuration file at "
        f"{TELEMETRY_CONFIG}: {config_path}. Skipping posting telemetry"
    )
    with pytest.warns(UserWarning, match=expected_warning):
        result = get_external_telemetry_config()
        assert result is None


@patch('payu.telemetry.get_scheduler_run_info')
@patch('payu.telemetry.get_external_telemetry_config')
@patch('payu.telemetry.post_telemetry_data')
def test_telemetry_record_run_no_telemetry_config(
    mock_post_telemetry_data,
    mock_telemetry_get_external_config,
    mock_telemetry_scheduler_run_info,
    tmp_path
):
    mock_telemetry_scheduler_run_info.return_value = {
        "test_field": "test_value"
    }
    mock_telemetry_get_external_config.return_value = None
    mock_post_telemetry_data.return_value = None

    # Setup Telemetry class
    telemetry = Telemetry(config={}, scheduler=None)
    job_info_filepath = tmp_path / "job.json"
    telemetry.set_run_info_filepath(job_info_filepath)
    telemetry.telemetry_enabled = False

    # Run method
    telemetry.record_run()

    # Check post telemetry method was not called
    mock_telemetry_get_external_config.assert_not_called()
    mock_post_telemetry_data.assert_not_called()

    # Check job.yaml was written
    assert job_info_filepath.exists()
    with open(job_info_filepath, 'r') as f:
        assert json.load(f) == {
            "test_field": "test_value"
        }


def test_telemetry_not_enabled_no_environment_config(monkeypatch):
    # Ensure telemetry config is not in os environment
    if TELEMETRY_CONFIG in os.environ:
        monkeypatch.delenv(TELEMETRY_CONFIG, raising=False)

    telemetry = Telemetry(config={}, scheduler=None)
    assert not telemetry.telemetry_enabled


def test_telemetry_not_enabled_config(tmp_path, setup_env):
    config = {
        "telemetry": {
            "enable": False
        }
    }
    telemetry = Telemetry(config=config, scheduler=None)
    assert not telemetry.telemetry_enabled


def test_telemetry_enabled(tmp_path, setup_env):
    telemetry = Telemetry(config={}, scheduler=None)
    assert telemetry.telemetry_enabled


@patch('payu.__version__', new='2.0.0')
def test_telemetry_payu_run(tmp_path, config_path, setup_env):
    """Test whole telemetry build run info and record run

    It's a bit of complex test as it mocks a lot of class objects and methods
    """

    # Mock the experiment values
    experiment = Mock()
    experiment.run_id = "test-commit-hash"
    experiment.counter = 0
    experiment.n_runs = 0
    experiment.run_job_status = 0
    experiment.start_time = datetime(2025, 1, 1, 0, 0, 0)
    experiment.finish_time = datetime(2025, 1, 1, 0, 0, 30)
    experiment.payu_path = "path/to/testenv/payu"
    experiment.control_path = "path/to/control/dir"
    experiment.archive_path = "path/to/archive/dir"
    experiment.config = {"model": "TEST_MODEL"}

    # Mock manifests
    test_exe_manifest = {
        "work/TEST_EXE1": {
            "fullpath": "/path/to/work/TEST_EXE1",
            "hashes": {
                "binhash": "529d8a94bd3c2eac0f54264e2e133d91",
                "md5": "85d681c54553914b7baa3cf7e02bb299"
            }
        }
    }
    test_input_manifest = {
        "work/TEST_INPUT1": {
            "fullpath": "/path/to/input/TEST_INPUT1",
            "hashes": {
                "binhash": "a1b2c3d4e5f67890a1b2c3d4e5f67890",
                "md5": "1234567890abcdef1234567890abcdef"
            }
        },
        "work/TEST_INPUT2": {
            "fullpath": "/path/to/input/TEST_INPUT2",
            "hashes": {
                "binhash": "0987654321fedcba0987654321fedc",
                "md5": "fedcba0987654321fedcba0987654321"
            }
        }
    }
    test_restart_manifest = {}
    exe_manifest = Mock()
    exe_manifest.data = test_exe_manifest
    restart_manifest = Mock()
    restart_manifest.data = test_restart_manifest
    input_manifest = Mock()
    input_manifest.data = test_input_manifest
    manifests = Mock()
    manifests.manifests = {
        "exe": exe_manifest,
        "restart": restart_manifest,
        "input": input_manifest,
    }
    experiment.manifest = manifests

    # Mock metadata
    test_metadata = {
        "experiment_uuid": "test-uuid",
        "created": "2025-01-01",
        "name": "test-expt-name",
        "model": "test-model"
    }
    metadata = Mock()
    metadata.read_file.return_value = test_metadata
    experiment.metadata = metadata

    # Mock scheduler
    test_job_info = {
        "job_id": "test-job-id",
        "project": "test-project"
    }
    scheduler = Mock()
    scheduler.get_job_id.return_value = "test-job-id"
    scheduler.get_job_info.return_value = test_job_info
    scheduler.name = "test-scheduler"

    # Create telemetry config and environment variable
    telemetry_config = {
        TELEMETRY_URL_FIELD: "some/server/url",
        HOSTNAME_FIELD: "test-host",
        TELEMETRY_SERVICE_NAME_FIELD: "payu",
        TELEMETRY_TOKEN_FIELD: "some_token",
        TELEMETRY_HOST_FIELD: "some_host",
    }

    with open(config_path, 'w') as f:
        json.dump(telemetry_config, f)

    # Setup Telemetry class
    telemetry = Telemetry(config={}, scheduler=scheduler)
    # Save run state information during experiment run
    telemetry.set_run_info(experiment=experiment)
    # Configure job info path during experiment run
    job_info_filepath = tmp_path / "job.json"
    telemetry.set_run_info_filepath(job_info_filepath)

    # Mock threading to call post_telemetry_data directly
    with patch('threading.Thread') as mock_thread_cls:
        mock_thread = Mock()
        mock_thread_cls.return_value = mock_thread

        def start_side_effect():
            # Get the args and kwargs passed to Thread
            thread_args = mock_thread_cls.call_args[1].get('args', ())
            thread_kwargs = mock_thread_cls.call_args[1].get('kwargs', {})
            # Call the post_telemetry_data function directly
            post_telemetry_data(*thread_args, **thread_kwargs)

        mock_thread.start.side_effect = start_side_effect

        # Mock the post request
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "success"}
            mock_post.return_value = mock_response

            # Store & post run job information
            telemetry.record_run()

            # Get data from the mock request
            assert mock_post.called
            args, kwargs = mock_post.call_args

    sent_data = json.loads(kwargs.get('data'))
    assert args == ("some/server/url",)
    assert kwargs.get('headers') == {
        'Content-type': 'application/json',
        'Authorization': 'Token some_token',
        'HOST': 'some_host',
    }
    assert kwargs.get('timeout') == 10
    assert kwargs.get('verify') is False

    record = sent_data["telemetry"]
    assert record['payu_run_id'] == 'test-commit-hash'
    assert record['payu_current_run'] == 0
    assert record['payu_n_runs'] == 0
    assert record['payu_job_status'] == 0
    assert record['payu_start_time'] == '2025-01-01T00:00:00'
    assert record['payu_finish_time'] == '2025-01-01T00:00:30'
    assert record['payu_walltime_seconds'] == 30.0
    assert record['payu_version'] == '2.0.0'
    assert record['payu_path'] == 'path/to/testenv'
    assert record['hostname'] == 'test-host'
    assert record['payu_control_path'] == 'path/to/control/dir'
    assert record['payu_archive_path'] == 'path/to/archive/dir'
    assert record['experiment_metadata'] == test_metadata
    assert record['manifests']['exe'] == test_exe_manifest
    assert record['manifests']['input'] == test_input_manifest
    assert record['manifests']['restart'] == test_restart_manifest
    assert record['payu_config'] == {"model": "TEST_MODEL"}
    assert record['scheduler_job_info'] == test_job_info

    # Validate sent record against schema for top level fields
    with open(TELEMETRY_1_0_0_SCHEMA_PATH, "r") as f:
        schema = json.load(f)
    jsonschema.validate(sent_data, schema)

    telemetry.clear_run_info()
    assert telemetry.run_info == {}
