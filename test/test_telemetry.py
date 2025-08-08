from datetime import datetime, timezone
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
        "telemetry_host": "some_host",
    }
    with open(config_path, 'w') as f:
        json.dump(config_data, f)


def test_get_external_telemetry_config_no_file(setup_env, config_path):
    expected_warning = (
        f"No config file found at {TELEMETRY_CONFIG}: {config_path}. "
        "Skipping posting telemetry"
    )
    with pytest.warns(UserWarning, match=expected_warning):
        result = get_external_telemetry_config()
        assert result is None


@pytest.mark.parametrize("missing_field", [
    "telemetry_url",
    "hostname",
    "telemetry_service_name",
    "telemetry_token",
    "telemetry_host"
])
def test_get_external_telemetry_config_missing_fields(setup_env, config_path,
                                                      missing_field):
    config_data = {
        "telemetry_url": "some/server/url",
        "hostname": "gadi",
        "telemetry_service_name": "payu",
        "telemetry_token": "some_token",
        "telemetry_host": "some_host",
    }
    # Remove the specified missing field
    config_data.pop(missing_field)
    with open(config_path, 'w') as f:
        json.dump(config_data, f)

    expected_warning = (
        rf"Required field\(s\) {set([missing_field])} not found in "
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
            mock_telemetry_get_external_config,
            mock_post_telemetry_data,
            monkeypatch
        ):
    # Ensure telemetry config is not in os environment
    if TELEMETRY_CONFIG in os.environ:
        monkeypatch.delenv(TELEMETRY_CONFIG, raising=False)

    record_telemetry(run_info={}, config={})

    # Check post telemetry method was not called
    mock_telemetry_get_external_config.assert_not_called()
    mock_post_telemetry_data.assert_not_called()


def test_telemetry_not_enabled_config(
            mock_telemetry_get_external_config,
            mock_post_telemetry_data,
            setup_env
        ):
    config = {
        "telemetry": {
            "enable": False
        }
    }

    record_telemetry(run_info={}, config={})

    # Check post telemetry method was not called
    mock_telemetry_get_external_config.assert_not_called()
    mock_post_telemetry_data.assert_not_called()


def test_write_queued_job_file(tmp_path, mock_scheduler, mock_metadata):
    """Test queued job file is written correctly"""

    write_queued_job_file(
        control_path=tmp_path / "control",
        job_id="test-job-id",
        type="payu-test",
        scheduler=mock_scheduler,
        metadata=mock_metadata,
        current_run=99
    )
    queued_file = tmp_path / "control" / "payu-jobs" / "payu-test.json"
    assert queued_file.exists()
    with open(queued_file, 'r') as f:
        assert json.load(f) == {
            "stage": "queued",
            "scheduler_job_id": "test-job-id",
            "scheduler_type": "test-scheduler",
            "experiment_metadata": {
                "experiment_uuid": "test-uuid"
            },
            "payu_current_run": 99,
        }


def test_setup_run_job_file(tmp_path, mock_scheduler, mock_metadata):
    """Test the run job file is created with the correct data"""
    setup_run_job_file(
        control_path=tmp_path / "control",
        work_path=tmp_path / "work",
        scheduler=mock_scheduler,
        metadata=mock_metadata
    )

    job_info_filepath = tmp_path / "work" / "payu-jobs" / "payu-run.json"
    assert job_info_filepath.exists()
    with open(job_info_filepath, 'r') as f:
        assert json.load(f) == {
            "stage": "setup",
            "scheduler_job_id": "test-job-id",
            "scheduler_type": "test-scheduler",
            "experiment_metadata": {
                "experiment_uuid": "test-uuid"
            },
        }


def test_setup_run_job_file_queued_file(tmp_path, mock_scheduler,
                                        mock_metadata):
    """Test the queued file is removed"""
    queued_file = tmp_path / "control" / "payu-jobs" / "payu-run.json"
    queued_file.parent.mkdir(parents=True, exist_ok=True)
    with open(queued_file, 'w') as f:
        json.dump({"stage": "queued", "scheduler_job_id": "test-job-id"}, f)

    setup_run_job_file(
        control_path=tmp_path / "control",
        work_path=tmp_path / "work",
        scheduler=mock_scheduler,
        metadata=mock_metadata
    )

    # Expect the queued file and parent directory to be removed
    assert not queued_file.exists()
    assert not queued_file.parent.exists()


def test_setup_run_job_file_job_id_different(tmp_path, mock_scheduler,
                                             mock_metadata):
    """Test the queued and setup job IDs match"""
    queued_file = tmp_path / "control" / "payu-jobs" / "payu-run.json"
    queued_file.parent.mkdir(parents=True, exist_ok=True)
    with open(queued_file, 'w') as f:
        json.dump(
            {"stage": "queued", "scheduler_job_id": "different-job-id"}, f
        )

    error_msg = r"Job ID in queued payu run file does not match *"
    with pytest.raises(RuntimeError, match=error_msg):
        setup_run_job_file(
            control_path=tmp_path / "control",
            work_path=tmp_path / "work",
            scheduler=mock_scheduler,
            metadata=mock_metadata
        )


def test_update_run_job_file(tmp_path, mock_manifests):
    """Test update that runs at model runs and archive"""

    run_job_file = tmp_path / "work" / "payu-jobs" / "payu-run.json"
    run_job_file.parent.mkdir(parents=True, exist_ok=True)
    with open(run_job_file, 'w') as f:
        json.dump({
            "payu_current_run": 0,
        }, f)

    update_run_job_file(
        base_path=tmp_path / "work",
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
    # Run setup job file to create the job file
    setup_run_job_file(
        control_path=tmp_path / "control",
        work_path=tmp_path / "work",
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
        }
    )
    # Before model run
    update_run_job_file(
        base_path=tmp_path / "work",
        stage='model-run',
        manifests=mock_manifests,
        extra_info={"payu_run_id": "test-commit-hash"}
    )
    # Post model run
    update_run_job_file(
        base_path=tmp_path / "work",
        extra_info={"payu_model_run_status": 0}
    )
    # Pre-archive
    update_run_job_file(
        base_path=tmp_path / "work",
        stage='archive',
    )
    movetree(tmp_path / "work", tmp_path / "archive" / "output000")
    # During archive
    update_run_job_file(
        base_path=tmp_path / "archive" / "output000",
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

        timings = {
            'payu_start_time': datetime(2025, 1, 1, tzinfo=timezone.utc)
        }

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
                archive_path=tmp_path / "archive",
                control_path=tmp_path / "control",
                work_path=tmp_path / "work",
                output_path=tmp_path / "archive" / "output000",
            )

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

    # Validate sent record against schema for top level fields
    with open(TELEMETRY_1_0_0_SCHEMA_PATH, "r") as f:
        schema = json.load(f)
    jsonschema.validate(sent_data, schema)


def test_record_run_error_logs(
    mock_post_telemetry_data,
    mock_telemetry_get_external_config,
    mock_scheduler,
    tmp_path,
):
    # Add a job file to the output path
    output_path = tmp_path / "archive" / "output000"
    job_info_filepath = output_path / "payu-jobs" / "payu-run.json"
    job_info_filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(job_info_filepath, 'w') as f:
        json.dump({
            "payu_current_run": 0,
            'payu_model_run_status': 1,
        }, f)

    record_run(
        timings={'payu_start_time': datetime(2025, 1, 1, tzinfo=timezone.utc)},
        scheduler=mock_scheduler,
        run_status=1,
        config={},
        archive_path=tmp_path / "archive",
        control_path=tmp_path / "control",
        work_path=tmp_path / "work",
        output_path=output_path,
    )

    # Check post telemetry method was not called
    mock_telemetry_get_external_config.assert_not_called()
    mock_post_telemetry_data.assert_not_called()

    # Check job file was updated
    assert job_info_filepath.exists()
    with open(job_info_filepath, 'r') as f:
        data = json.load(f)

    assert data['payu_current_run'] == 0
    assert data['payu_run_status'] == 1
    assert data['payu_model_run_status'] == 1
    assert data['stage'] == 'completed'
    assert data['scheduler_job_id'] == 'test-job-id'
    assert data['timings']['payu_start_time'] == "2025-01-01T00:00:00+00:00"

    # Check log file was copied with errors
    error_log_dir = tmp_path / 'archive' / 'error_logs'
    error_file = error_log_dir / 'payu-run.test-job-id.json'
    assert error_file.exists()
    with open(error_file, 'r') as f:
        error_data = json.load(f)
    assert error_data == data
