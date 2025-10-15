from datetime import datetime
import json
import os
from pathlib import Path
from unittest.mock import patch, Mock

import cftime
import jsonschema
import pytest

from payu.telemetry import (
    transform_model_datetimes,
    get_external_telemetry_config,
    post_telemetry_data,
    TELEMETRY_CONFIG,
    record_run,
    record_telemetry,
    get_job_file_path,
    write_queued_job_file,
    setup_run_job_file,
    update_run_job_file
)
from payu.fsops import movetree

TELEMETRY_1_0_0_SCHEMA_PATH = (
    Path(__file__).parent / "resources" / "schema" / "telemetry" / "1-0-0.json"
)


@pytest.fixture
def mock_scheduler():
    """Generate an example scheduler object"""
    mock = Mock()
    mock.get_job_id.return_value = "test-job-id"
    mock.get_job_info.return_value = {
        "job_id": "test-job-id",
        "project": "test-project"
    }
    mock.name = "test-scheduler"
    return mock


@pytest.fixture
def mock_metadata():
    """Generate an example metadata object"""
    mock = Mock()
    mock.read_file.return_value = {
        "experiment_uuid": "test-uuid",
    }
    return mock


@pytest.fixture
def mock_manifests():
    """Generate an example manifests object"""
    exe_manifest = Mock()
    exe_manifest.data = {
        "work/TEST_EXE1": {
            "fullpath": "/path/to/work/TEST_EXE1",
            "hashes": {
                "binhash": "529d8a94bd3c2eac0f54264e2e133d91",
                "md5": "85d681c54553914b7baa3cf7e02bb299"
            }
        }
    }
    restart_manifest = Mock()
    restart_manifest.data = {}
    input_manifest = Mock()
    input_manifest.data = {
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
    manifests = Mock()
    manifests.manifests = {
        "exe": exe_manifest,
        "restart": restart_manifest,
        "input": input_manifest,
    }
    return manifests


@pytest.fixture
def mock_post_telemetry_data():
    """Mock the post_telemetry_data function"""
    with patch('payu.telemetry.post_telemetry_data') as mock:
        mock.return_value = None
        yield mock


@pytest.fixture
def mock_telemetry_get_external_config():
    """Mock the get_external_telemetry_config function"""
    with patch('payu.telemetry.get_external_telemetry_config') as mock:
        mock.return_value = None
        yield mock


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


@pytest.fixture
def setup_config(config_path):
    """Helper function to set up the telemetry config file"""
    config_data = {
        "telemetry_url": "some/server/url",
        "hostname": "gadi",
        "telemetry_service_name": "payu",
        "telemetry_token": "some_token",
        "telemetry_proxy_url": "some_persistent_session_url",
    }
    with open(config_path, 'w') as f:
        json.dump(config_data, f)


def check_invalid_get_external_config(tmp_path, expected_error):
    telemetry_log = tmp_path / "archive" / "error_logs" / "telemetry.log"
    expected_warning = (
        "Error sending telemetry. See error log at "
        f"{telemetry_log} for details."
    )
    with pytest.warns(UserWarning, match=expected_warning):
        result = get_external_telemetry_config(
            archive_path=tmp_path / "archive",
            job_file_path=tmp_path / "job_file.json"
        )
        assert result is None

    assert telemetry_log.exists()
    with open(telemetry_log, 'r') as f:
        # Read last line of the log file
        last_line = f.readlines()[-1].strip()
        json_log = json.loads(last_line)
        assert json_log["error"] == expected_error
        assert json_log["timestamp"] is not None
        assert json_log["jobfile"] == str(tmp_path / "job_file.json")


def test_get_external_telemetry_config_no_file(
            tmp_path, setup_env, config_path
        ):
    expected_error = (
        f"No config file found at {TELEMETRY_CONFIG}: {config_path}."
    )
    check_invalid_get_external_config(tmp_path, expected_error)


@pytest.mark.parametrize("missing_field", [
    "telemetry_url",
    "hostname",
    "telemetry_service_name",
    "telemetry_token",
    "telemetry_proxy_url"
])
def test_get_external_telemetry_config_missing_fields(
            tmp_path, setup_env, config_path, missing_field
        ):
    config_data = {
        "telemetry_url": "some/server/url",
        "hostname": "gadi",
        "telemetry_service_name": "payu",
        "telemetry_token": "some_token",
        "telemetry_proxy_url": "some_persistent_session_url",
    }
    # Remove the specified missing field
    config_data.pop(missing_field)
    with open(config_path, 'w') as f:
        json.dump(config_data, f)

    expected_error = (
        f"Required field(s) {set([missing_field])} not found in "
        f"configuration file at {TELEMETRY_CONFIG}: {config_path}."
    )
    check_invalid_get_external_config(tmp_path, expected_error)


def test_get_external_telemetry_config_invalid_json(
            tmp_path, setup_env, config_path
        ):
    with open(config_path, 'w') as f:
        f.write("{invalid_json")

    expected_error = (
        f"Error parsing json in configuration file at "
        f"{TELEMETRY_CONFIG}: {config_path}."
    )
    check_invalid_get_external_config(tmp_path, expected_error)


@pytest.mark.parametrize("datetimes, transformed_datetimes", [
    (
        {
            "model_end_time": cftime.datetime(2025, 2, 1, calendar='julian'),
            "model_start_time": cftime.datetime(2025, 1, 1, calendar='julian'),
        },
        {
            "model_end_time": "2025-02-01T00:00:00",
            "model_calendar": "julian",
            "model_start_time": "2025-01-01T00:00:00",
        }
    ),
    ({}, {}),
    (
        {
            "model_end_time": cftime.datetime(2025, 2, 1, calendar='standard'),
        },
        {
            "model_end_time": "2025-02-01T00:00:00",
            "model_calendar": "standard",
        }
    ),
])
def test_transform_model_datetime(datetimes, transformed_datetimes):
    """Test the transform_model_datetimes converts cftime datetimes to ISO
    format strings and calendars"""
    result = transform_model_datetimes(datetimes)
    assert result == transformed_datetimes


def test_transform_model_datetime_warning():
    """Test the transform_model_datetimes raises a warning
    for unexpected type"""
    expected_warning = (
        "Expected cftime.datetime for model datetimes, "
        "but got datetime"
    )
    with pytest.warns(UserWarning, match=expected_warning):
        result = transform_model_datetimes(
            {
                "model_end_time": datetime(2025, 1, 1, 12, 0, 0),
                "model_start_time": datetime(2025, 1, 1, 0, 0, 0),
            }
        )
    assert result == {}


def test_telemetry_not_enabled_no_environment_config(
            tmp_path,
            mock_telemetry_get_external_config,
            mock_post_telemetry_data,
            monkeypatch
        ):
    # Ensure telemetry config is not in os environment
    if TELEMETRY_CONFIG in os.environ:
        monkeypatch.delenv(TELEMETRY_CONFIG, raising=False)

    record_telemetry(run_info={}, config={},
                     archive_path=tmp_path / "archive",
                     job_file_path=tmp_path / "job_file.json")

    # Check post telemetry method was not called
    mock_telemetry_get_external_config.assert_not_called()
    mock_post_telemetry_data.assert_not_called()


def test_telemetry_not_enabled_config(
            tmp_path,
            mock_telemetry_get_external_config,
            mock_post_telemetry_data,
            setup_env
        ):
    config = {
        "telemetry": {
            "enable": False
        }
    }

    record_telemetry(run_info={}, config={},
                     archive_path=tmp_path / "archive",
                     job_file_path=tmp_path / "job_file.json")

    # Check post telemetry method was not called
    mock_telemetry_get_external_config.assert_not_called()
    mock_post_telemetry_data.assert_not_called()


def test_write_queued_job_file(tmp_path, mock_scheduler, mock_metadata):
    """Test queued job file is written correctly"""

    write_queued_job_file(
        archive_path=tmp_path / "archive",
        job_id="test-id",
        type="run",
        scheduler=mock_scheduler,
        metadata=mock_metadata,
        current_run=99
    )
    queued_file = (
        tmp_path / "archive" / "payu_jobs" / str(99) / "run" / "test-id.json"
    )
    assert queued_file.exists()
    with open(queued_file, 'r') as f:
        assert json.load(f) == {
            "stage": "queued",
            "scheduler_job_id": "test-id",
            "scheduler_type": "test-scheduler",
            "experiment_metadata": {
                "experiment_uuid": "test-uuid"
            },
            "payu_current_run": 99,
        }


@pytest.mark.parametrize("queued_file", [True, False])
def test_setup_run_job_file(tmp_path, mock_scheduler, mock_metadata,
                            queued_file):
    """Test the run job file is created with the correct data"""
    job_info_filepath = tmp_path / "archive-payu-jobs" / "payu-run.json"
    if queued_file:
        job_info_filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(job_info_filepath, 'w') as f:
            json.dump({"stage": "queued", "scheduler_job_id": "test-id"}, f)

    setup_run_job_file(
        file_path=job_info_filepath,
        scheduler=mock_scheduler,
        metadata=mock_metadata,
        timings={'payu_start_time': datetime(2025, 1, 1)}
    )

    assert job_info_filepath.exists()
    with open(job_info_filepath, 'r') as f:
        assert json.load(f) == {
            "stage": "setup",
            "scheduler_job_id": "test-job-id",
            "scheduler_type": "test-scheduler",
            "experiment_metadata": {
                "experiment_uuid": "test-uuid"
            },
            "timings": {
                "payu_start_time": "2025-01-01T00:00:00"
            },
        }


def test_setup_run_job_file_no_path(mock_scheduler, mock_metadata):
    """Test setup_run_job_file returns early if no file path is provided
    e.g. in payu setup command"""
    setup_run_job_file(
        file_path=None,
        scheduler=mock_scheduler,
        metadata=mock_metadata,
        timings={'payu_start_time': datetime(2025, 1, 1)}
    )
    assert not mock_scheduler.get_job_id.called


def test_update_run_job_file_no_path(mock_manifests):
    """Test update_run_job_file returns early if no file path is provided
    e.g. in payu archive command"""
    with patch('payu.telemetry.get_manifests') as mock_get_manifests:
        update_run_job_file(
            file_path=None,
            stage="model-run",
            manifests=mock_manifests,
        )
        assert not mock_get_manifests.called


def test_update_run_job_file(tmp_path, mock_manifests):
    """Test update that runs at model runs and archive"""

    run_job_file = tmp_path / "payu-run-id.json"
    with open(run_job_file, 'w') as f:
        json.dump({
            "payu_current_run": 0,
        }, f)

    update_run_job_file(
        file_path=run_job_file,
        stage="model-run",
        manifests=mock_manifests,
        model_restart_datetimes={
            "model_end_time": cftime.datetime(2025, 1, 1, calendar='julian'),
        },
        extra_info={
            "payu_run_id": "test-run-id",
        }
    )

    assert run_job_file.exists()
    with open(run_job_file, 'r') as f:
        run_info = json.load(f)

    assert run_info['payu_current_run'] == 0
    assert run_info['stage'] == 'model-run'
    assert run_info['payu_run_id'] == 'test-run-id'
    assert run_info['manifests']['exe'] == {
        "work/TEST_EXE1": {
            "fullpath": "/path/to/work/TEST_EXE1",
            "hashes": {
                "binhash": "529d8a94bd3c2eac0f54264e2e133d91",
                "md5": "85d681c54553914b7baa3cf7e02bb299"
            }
        }
    }
    assert run_info['manifests']['restart'] == {}
    assert run_info['model_end_time'] == "2025-01-01T00:00:00"
    assert run_info['model_calendar'] == "julian"


def test_telemetry_payu_run(tmp_path, config_path, setup_env,
                            setup_config, mock_scheduler,
                            mock_metadata, mock_manifests):
    """
    Test all telemetry methods run in sequence (as if it was a real
    payu run job), and check posted telemetry data is valid with the schema.
    """
    timings = {
        'payu_start_time': datetime(2025, 1, 1)
    }

    # Set jobfile path=
    file_path = get_job_file_path(
        archive_path=tmp_path / "archive",
        run_number=0,
        timings=timings,
        scheduler=mock_scheduler,
        type="run"
    )
    # Run setup job file to create the job file
    setup_run_job_file(
        file_path=file_path,
        scheduler=mock_scheduler,
        metadata=mock_metadata,
        extra_info={
            "payu_run_id": "test-commit-hash",
            "payu_current_run": 0,
            "payu_n_runs": 0,
            "payu_version": "2.0.0",
            "payu_path": "path/to/testenv",
            "payu_control_path": "path/to/control/dir",
            "payu_archive_path": "path/to/archive/dir",
            "user_id": "test_user",
            "payu_config": {"model": "TEST_MODEL"},
        },
        timings=timings
    )
    # Before model run
    update_run_job_file(
        file_path=file_path,
        stage='model-run',
        manifests=mock_manifests,
        extra_info={"payu_run_id": "test-commit-hash"}
    )
    # Post model run
    update_run_job_file(
        file_path=file_path,
        extra_info={"payu_model_run_status": 0}
    )
    # Pre-archive
    update_run_job_file(
        file_path=file_path,
        stage='archive',
    )
    # During archive
    update_run_job_file(
        file_path=file_path,
        model_restart_datetimes={
            "model_end_time": cftime.datetime(2025, 1, 1, calendar='julian'),
        }
    )

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
            record_run(
                timings=timings,
                scheduler=mock_scheduler,
                run_status=0,
                config={},
                file_path=file_path,
                archive_path=tmp_path / "archive",
            )

            # Get data from the mock request
            assert mock_post.called
            args, kwargs = mock_post.call_args

    sent_data = json.loads(kwargs.get('data'))
    assert args == ("some/server/url",)
    assert kwargs.get('headers') == {
        'Content-type': 'application/json',
        'Authorization': 'Token some_token',
    }
    assert kwargs.get('timeout') == 10
    assert kwargs.get('proxies') == {"https": "some_persistent_session_url", "http": "some_persistent_session_url"}

    assert sent_data["service"] == "payu"
    assert sent_data["version"] == "1.0.0"

    record = sent_data["telemetry"]

    # Validate sent record against schema for top level fields
    with open(TELEMETRY_1_0_0_SCHEMA_PATH, "r") as f:
        schema = json.load(f)
    jsonschema.validate(sent_data, schema)
