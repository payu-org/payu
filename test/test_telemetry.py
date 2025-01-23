from datetime import datetime
import json
import os

import pytest
from unittest.mock import patch, Mock

from payu.telemetry import get_external_telemetry_config, post_telemetry_data
from payu.telemetry import Telemetry
from payu.telemetry import TELEMETRY_CONFIG, SERVER_URL_FIELD, HOSTNAME_FIELD


@pytest.fixture
def setup_env(tmp_path):
    config_path = tmp_path / "telemetry_config.json"
    os.environ[TELEMETRY_CONFIG] = str(config_path)
    return config_path


def test_get_external_telemetry_config_valid(setup_env):
    config_path = setup_env
    config_data = {
        SERVER_URL_FIELD: "some/server/url",
        HOSTNAME_FIELD: "gadi"
    }
    with open(config_path, 'w') as f:
        json.dump(config_data, f)

    result = get_external_telemetry_config()
    assert result == config_data


def test_get_external_telemetry_config_no_file(setup_env):
    config_path = setup_env

    expected_warning = (
        f"No config file found at {TELEMETRY_CONFIG}: {config_path}. "
        "Skipping posting telemetry"
    )
    with pytest.warns(UserWarning, match=expected_warning):
        result = get_external_telemetry_config()
        assert result is None


def test_get_external_telemetry_config_missing_fields(setup_env):
    config_path = setup_env
    config_data = {
        SERVER_URL_FIELD: "some/server/url",
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


def test_get_external_telemetry_config_invalid_json(setup_env):
    config_path = setup_env
    with open(config_path, 'w') as f:
        f.write("{invalid_json")

    expected_warning = (
        f"Error parsing json in configuration file at "
        f"{TELEMETRY_CONFIG}: {config_path}. Skipping posting telemetry"
    )
    with pytest.warns(UserWarning, match=expected_warning):
        result = get_external_telemetry_config()
        assert result is None


@patch('access_py_telemetry.api.ApiHandler')
def test_post_telemetry_data_missing_access_py_telemetry(mock_api_handler):
    """Test import error is caught with a warning if
    access_py_telemetry module is not available"""
    mock_api = Mock()
    mock_api_handler.return_value = mock_api

    expected_warning = (
        "access_py_telemetry module not found. Skipping posting telemetry."
    )
    with patch.dict('sys.modules', {'access_py_telemetry.api': None}):
        with pytest.warns(UserWarning, match=expected_warning):
            post_telemetry_data("http://example.com", {}, "service_name",
                                "function_name")

    mock_api_handler.assert_not_called()


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


def test_telemetry_not_enabled_config(monkeypatch, tmp_path):
    # Set up the environment variable
    config_path = tmp_path / "telemetry_config.json"
    monkeypatch.setenv(TELEMETRY_CONFIG, str(config_path))

    config = {
        "telemetry": {
            "enable": False
        }
    }
    telemetry = Telemetry(config=config, scheduler=None)
    assert not telemetry.telemetry_enabled


def test_telemetry_enabled(monkeypatch, tmp_path):
    # Set up the environment variable
    config_path = tmp_path / "telemetry_config.json"
    monkeypatch.setenv(TELEMETRY_CONFIG, str(config_path))

    telemetry = Telemetry(config={}, scheduler=None)
    assert telemetry.telemetry_enabled


@patch('payu.__version__', new='2.0.0')
def test_telemetry_payu_run(monkeypatch, tmp_path):
    """Test whole telemetry build run info and record run"""

    # Mock out experiment values
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

    # Mock metadata
    metadata = Mock()
    metadata.read_file.return_value = {
        "experiment_uuid": "test-uuid",
        "created": "2025-01-01",
        "name": "test-expt-name",
        "model": "test-model"
    }
    experiment.metadata = metadata

    # Mock scheduler
    scheduler = Mock()
    scheduler.get_job_id.return_value = "test-job-id"
    scheduler.get_job_info.return_value = {
        "job_id": "test-job-id",
        "project": "test-project"
    }
    scheduler.name = "test-scheduler"

    # Create telemetry config and environment variable
    telemetry_config = {
        "server_url": "test-persistent-session-hostname",
        "hostname": "test-host"
    }

    telemetry_config_path = tmp_path / "telemetry_config.json"
    with open(telemetry_config_path, 'w') as f:
        json.dump(telemetry_config, f)
    monkeypatch.setenv(TELEMETRY_CONFIG, str(telemetry_config_path))

    # Setup Telemetry class
    telemetry = Telemetry(config={}, scheduler=scheduler)
    # Save run state information during experiment run
    telemetry.set_run_info(experiment=experiment)
    # Configure job info path during experiment run
    job_info_filepath = tmp_path / "job.json"
    telemetry.set_run_info_filepath(job_info_filepath)
    # Store & post run job information
    telemetry.record_run()

    # Should this be tested here - how likely is this to change
    # - would there be a fixed access_py_telemetry version shipped with payu?
    from access_py_telemetry.api import ApiHandler
    record = ApiHandler()._last_record
    assert record['function'] == 'payu.subcommands.run_cmd.runscript'
    assert record['args'] == {}
    assert record['kwargs'] == {}
    assert record['experiment_uuid'] == 'test-uuid'
    assert record['experiment_created'] == '2025-01-01'
    assert record['experiment_name'] == 'test-expt-name'
    assert record['model'] == 'test-model'
    assert record['payu_run_id'] == 'test-commit-hash'
    assert record['payu_current_run'] == 0
    assert record['payu_n_runs'] == 0
    assert record['payu_job_status'] == 0
    assert record['payu_start_time'] == '2025-01-01T00:00:00'
    assert record['payu_finish_time'] == '2025-01-01T00:00:30'
    assert record['payu_walltime_seconds'] == 30.0
    assert record['payu_version'] == '2.0.0'
    assert record['payu_path'] == 'path/to/testenv'
    assert record['payu_control_dir'] == 'path/to/control/dir'
    assert record['payu_archive_dir'] == 'path/to/archive/dir'
    assert record['scheduler_type'] == 'test-scheduler'
    assert record['scheduler_job_id'] == 'test-job-id'
    assert record['hostname'] == 'test-host'

    telemetry.clear_run_info()
    assert telemetry.run_info == {}
