import json
import pytest
from freezegun import freeze_time

from payu.status import (
    find_file_match,
    get_scheduler_log,
    find_scheduler_logs,
    get_job_file_list,
    build_job_info
)

from payu.subcommands.status_cmd import runcmd
from payu.git_utils import PayuGitWarning

def test_find_file_match(tmp_path):
    test_file = tmp_path / "job_name.o146702704"
    test_file.touch()
    result = find_file_match(pattern="*.o146702704", path=tmp_path)
    assert result == test_file


def test_find_file_match_no_match(tmp_path):
    result = find_file_match(pattern="*.nonexistent", path=tmp_path)
    assert result is None

    result = find_file_match(pattern="*.o146702704", path=tmp_path / "dne")
    assert result is None

    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()
    result = find_file_match(pattern="*.o146702704", path=empty_dir)
    assert result is None


def test_find_file_match_multiple_matches(tmp_path):
    test_file1 = tmp_path / "job_name.o146702704"
    test_file2 = tmp_path / "another_file.o146702704"
    test_file1.touch()
    test_file2.touch()

    with pytest.warns(UserWarning, match=r'Multiple files found .*'):
        result = find_file_match(path=tmp_path, pattern="*.o146702704")
    assert result in (test_file1, test_file2)


@pytest.mark.parametrize(
    "base_dir",
    ["control", "archive/pbs_logs", None]
)
def test_get_scheduler_log(tmp_path, base_dir):
    if base_dir is None:
        file_path = None
    else:
        file_path = tmp_path / base_dir / "test.o123"
        file_path.mkdir(parents=True, exist_ok=True)
        file_path.touch()

    result = get_scheduler_log(
        pattern="*.o123",
        control_path=tmp_path / "control",
        archive_path=tmp_path / "archive",
    )
    assert result == file_path


@pytest.mark.parametrize(
    "scheduler,jobid,base_dir,stdout,stderr",
    [
        ("pbs", "123.gadi-pbs", "control", "test.o123", "test.e123"),
        ("slurm", "456", "archive/pbs_logs", "slurm-456.out", "slurm-456.err"),
        ("pbs", "789", None, None, None),
        ("pbs", "", None, None, None),
    ]
)
def test_find_scheduler_logs_pbs(tmp_path, scheduler, jobid, base_dir,
                                 stdout, stderr):
    if base_dir is None:
        # No files expected
        stdout_path = None
        stderr_path = None
    else:
        stdout_path = tmp_path / base_dir / stdout
        stderr_path = tmp_path / base_dir / stderr
        stdout_path.mkdir(parents=True, exist_ok=True)
        stderr_path.mkdir(parents=True, exist_ok=True)
        stdout_path.touch()
        stderr_path.touch()

    path1, path2 = find_scheduler_logs(
        job_id=jobid,
        control_path=tmp_path / "control",
        archive_path=tmp_path / "archive",
        type=scheduler
    )
    assert path1 == stdout_path
    assert path2 == stderr_path


def write_job_file(archive_path, job_id, run_number, job_data):
    """Helper function to write job data to a file"""
    job_file = (
        archive_path / "payu_jobs" / str(run_number) / "run" / f"{job_id}.json"
    )
    job_file.parent.mkdir(parents=True, exist_ok=True)
    with open(job_file, 'w') as f:
        json.dump(job_data, f)
    return job_file


@pytest.fixture
def queued_job(tmp_path, request):
    """Fixture to create a queued job file"""
    if request.param:
        return write_job_file(
            archive_path=tmp_path / "archive",
            job_id="test-job-id-3",
            run_number=3,
            job_data={
                "scheduler_job_id": "test-job-id-3",
                "scheduler_type": "pbs",
                "metadata": {"uuid": "test-uuid"},
                "payu_current_run": 3,
                "stage": "queued"
            }
        )


@pytest.fixture
def running_job(tmp_path, request):
    """Fixture to create a running job file"""
    if request.param:
        return write_job_file(
            archive_path=tmp_path / "archive",
            job_id="test-job-id-3",
            run_number=3,
            job_data={
                "scheduler_job_id": "test-job-id-3",
                "scheduler_type": "pbs",
                "metadata": {"uuid": "test-uuid"},
                "payu_current_run": 3,
                "payu_run_id": "commit-hash3",
                "stage": "model-run",
                "timings": {
                    "payu_start_time": "2025-08-15T16:30:00"
                }
            }
        )


@pytest.fixture
def archive_jobs(tmp_path, request):
    """Fixture to create an archived job files"""
    if request.param:
        files = []
        for i in range(3):
            files.append(
                write_job_file(
                    archive_path=tmp_path / "archive",
                    job_id=f"test-job-id-{i}",
                    run_number=i,
                    job_data={
                        "scheduler_job_id": f"test-job-id-{i}",
                        "scheduler_type": "pbs",
                        "metadata": {"uuid": "test-uuid"},
                        "payu_current_run": i,
                        "payu_run_id": f"commit-hash{i}",
                        "stage": "archive",
                        "payu_run_status": 0,
                        "payu_model_run_status": 0,
                        "timings": {
                            "payu_start_time": f"2025-08-1{i}T12:00:00"
                        }
                    }
                )
            )
        return files


@pytest.fixture
def failed_job(tmp_path, request):
    """Fixture to create a failed job file"""
    if request.param:
        return write_job_file(
            archive_path=tmp_path / "archive",
            job_id="test-job-id-failed",
            run_number=3,
            job_data={
                "scheduler_job_id": "test-job-id-failed",
                "scheduler_type": "pbs",
                "metadata": {"uuid": "test-uuid"},
                "payu_current_run": 3,
                "payu_run_id": "commit-hash-failed",
                "stage": "setup",
                "payu_run_status": 1,
                "timings": {
                    "payu_start_time": "2025-08-13T12:00:00"
                }
            }
        )


@pytest.mark.parametrize(
    "archive_jobs,running_job,queued_job,latest_file,all_files",
    [
        # Only queued job file exists
        (
            False, False, True, ["3/run/test-job-id-3.json"],
            ["3/run/test-job-id-3.json"]
        ),
        # Archive job file exists but there's a queued job file
        (
            True, False, True, ["3/run/test-job-id-3.json"],
            [
                "3/run/test-job-id-3.json",
                "2/run/test-job-id-2.json",
                "1/run/test-job-id-1.json",
                "0/run/test-job-id-0.json"
            ]
        ),
        # Only running job file exists
        (
            False, True, False, ["3/run/test-job-id-3.json"],
            ["3/run/test-job-id-3.json"]
        ),
        # Both archive and running job files exist
        (
            True, True, False, ["3/run/test-job-id-3.json"],
            [
                "3/run/test-job-id-3.json",
                "2/run/test-job-id-2.json",
                "1/run/test-job-id-1.json",
                "0/run/test-job-id-0.json",
            ]
        ),
        # Only archive job files exist
        (
            True, False, False, ["2/run/test-job-id-2.json"],
            [
                "2/run/test-job-id-2.json",
                "1/run/test-job-id-1.json",
                "0/run/test-job-id-0.json"
            ]
        ),
        # No job files exist
        (False, False, False, [], []),
    ],
    indirect=["archive_jobs", "queued_job", "running_job"]
)
def test_get_job_file_list(tmp_path, archive_jobs, queued_job,
                           running_job, latest_file, all_files):
    """Test both default and all_runs=True"""
    files = get_job_file_list(archive_path=tmp_path / "archive")
    # Expand expected paths to full paths
    base_path = tmp_path / "archive" / "payu_jobs"
    expected_latest_paths = [base_path / file for file in latest_file]
    assert files == expected_latest_paths

    all_files = get_job_file_list(
        archive_path=tmp_path / "archive",
        all_runs=True
    )
    expected_all_paths = [base_path / file for file in all_files]
    assert all_files == expected_all_paths


@pytest.mark.parametrize(
    "archive_jobs,running_job,queued_job,run_number,expected_file",
    [
        # Test with a queued job file
        (False, False, True, 10, []),
        # Test with a running job file
        (False, True, False, 3, ["3/run/test-job-id-3.json"]),
        # Test with an archived job files
        (True, False, False, 2, ["2/run/test-job-id-2.json"]),
        (True, False, False, 0, ["0/run/test-job-id-0.json"]),
        # Test with no files
        (False, False, False, 1, []),
        # Test with a too high run number that does not match any file
        (True, False, False, 5, []),
    ],
    indirect=["archive_jobs", "queued_job", "running_job"]
)
def test_get_job_file_list_selected_run(tmp_path, queued_job, running_job,
                                        archive_jobs, run_number,
                                        expected_file):
    """Test selecting the run number"""
    files = get_job_file_list(
        archive_path=tmp_path / "archive",
        run_number=run_number
    )
    base_path = tmp_path / "archive" / "payu_jobs"
    assert files == [base_path / file for file in expected_file]


def expected_archive_job_info(run_number):
    return {
        'exit_status': 0,
        'job_id': f'test-job-id-{run_number}',
        'run_id': f'commit-hash{run_number}',
        'model_exit_status': 0,
        'stage': 'archive',
        'qtime': None,
        'stime': None,
        'stderr_file': None,
        'stdout_file': None,
        'start_time': f'2025-08-1{run_number}T12:00:00'
    }


def expected_running_job_info():
    return {
        'exit_status': None,
        'job_id': 'test-job-id-3',
        'run_id': 'commit-hash3',
        'model_exit_status': None,
        'stage': 'model-run',
        'qtime': None,
        'stime': None,
        'stderr_file': None,
        'stdout_file': None,
        'start_time': '2025-08-15T16:30:00'
    }


def expected_queued_job_info():
    return {
        'exit_status': None,
        'job_id': 'test-job-id-3',
        'run_id': None,
        'model_exit_status': None,
        'stage': 'queued',
        'qtime': None,
        'stime': None,
        'stderr_file': None,
        'stdout_file': None,
        'start_time': None
    }


def expected_failed_job_info():
    return {
        'exit_status': 1,
        'job_id': 'test-job-id-failed',
        'run_id': 'commit-hash-failed',
        'model_exit_status': None,
        'stage': 'setup',
        'qtime': None,
        'stime': None,
        'stderr_file': None,
        'stdout_file': None,
        'start_time': '2025-08-13T12:00:00'
    }


def remove_job_file_paths(data):
    """Remove job_file paths from the data for comparison."""
    if 'runs' in data:
        for payu_jobs in data['runs'].values():
            if 'run' in payu_jobs:
                for run in payu_jobs['run']:
                    del run['job_file']


@pytest.mark.parametrize(
    "archive_jobs,running_job,queued_job,failed_job,expected",
    [
        (
            False, False, True, False,
            {'runs': {3: {'run': [expected_queued_job_info()]}}}
        ),
        (
            True, True, False, False,
            {
                'runs': {
                    0: {'run': [expected_archive_job_info(0)]},
                    1: {'run': [expected_archive_job_info(1)]},
                    2: {'run': [expected_archive_job_info(2)]},
                    3: {'run': [expected_running_job_info()]}
                }
            }
        ),
        (False, False, False, False, {}),
        (
            False, True, False, True,
            {
                'runs': {
                    3: {
                        'run': [
                            expected_failed_job_info(),
                            expected_running_job_info(),
                        ]
                    }
                }
            }
        ),
        (
            False, False, True, True,
            {
                'runs': {
                    3: {
                        'run': [
                            expected_failed_job_info(),
                            expected_queued_job_info(),
                        ]
                    }
                }
            }
        ),

    ],
    indirect=["archive_jobs", "running_job", "queued_job", "failed_job"]
)
def test_build_job_info(tmp_path, archive_jobs, running_job,
                        queued_job, failed_job, expected):

    all_runs = build_job_info(
        control_path=tmp_path / "control",
        archive_path=tmp_path / "archive",
        all_runs=True
    )

    # Remove job file from check as it contains tmp_path
    remove_job_file_paths(all_runs)

    assert all_runs == expected


@pytest.mark.parametrize(
    "archive_jobs,running_job,queued_job,failed_job,expected",
    [
        # Only archive job files
        (
            True, False, False, False,
            {'runs': {2: {'run': [expected_archive_job_info(2)]}}}
        ),
        # Even with a error job file, the latest run is the more recent job
        (
            True, True, False, True,
            {'runs': {3: {'run': [expected_running_job_info()]}}}
        ),
        # Error job file is the latest
        (
            True, False, False, True,
            {'runs': {3: {'run': [expected_failed_job_info()]}}}
        ),
        # Queued job file is the latest
        (
            True, False, True, True,
            {'runs': {3: {'run': [expected_queued_job_info()]}}}
        ),
    ],
    indirect=[
        "archive_jobs", "running_job", "queued_job", "failed_job"
    ]
)
def test_build_job_info_latest(tmp_path, archive_jobs,
                               running_job, queued_job,
                               failed_job, expected):

    latest_data = build_job_info(
        control_path=tmp_path / "control",
        archive_path=tmp_path / "archive",
    )

    # Remove job file from check as it contains tmp_path
    remove_job_file_paths(latest_data)

    assert latest_data == expected


def test_status_cmd_no_metadata(tmp_path):
    """Test error raised when metadata is not setup - rather than
    creating a new uuid"""
    # Create a temporary lab and config
    lab_path = tmp_path / "lab"
    lab_path.mkdir()
    control_path = tmp_path / "control"
    control_path.mkdir()
    config_path = control_path / "config.yaml"

    # Create a minimal config file
    with open(config_path, 'w') as f:
        json.dump({'model': 'test'}, f)

    with pytest.warns(PayuGitWarning):
        with pytest.raises(RuntimeError, match="Metadata is not setup"):
            runcmd(
                lab_path=str(lab_path),
                config_path=str(config_path),
                json_output=True,
                update_jobs=False,
                all_runs=False,
                run_number=None
            )
    assert not (control_path / "metadata.yaml").exists()


def test_status_cmd(tmp_path, capsys):
    """Test the status command returns empty JSON output."""
    # Create a temporary lab and config
    lab_path = tmp_path / "lab"
    archive_path = lab_path / "archive" / "control-exp"
    archive_path.mkdir(parents=True, exist_ok=True)
    control_path = tmp_path / "control-exp"
    control_path.mkdir()
    config_path = control_path / "config.yaml"

    # Create a minimal config file
    with open(config_path, 'w') as f:
        json.dump({'model': 'test'}, f)

    # Create a minimal metadata file
    metadata_path = control_path / "metadata.yaml"
    with open(metadata_path, 'w') as f:
        json.dump({'experiment_uuid': 'test-uuid'}, f)

    # Run the command
    with pytest.warns(PayuGitWarning):
        runcmd(
            lab_path=str(lab_path),
            config_path=str(config_path),
            json_output=True,
            update_jobs=False,
            all_runs=False,
            run_number=None
        )

    # Check only json is printed
    output = capsys.readouterr().out
    assert output.strip() == '{}'

@freeze_time("2026-02-10 15:05:00")
@pytest.mark.parametrize(
    "job_stage, qtime, stime, time_label, time_message",
    [   
        # Test queueing job with qtime 5 minutes ago
        (
            "queued",
            "Tue Feb 10 15:00:00 2026",
            None,
            "Queue time:",
            "0h 5m ",
        ),

        # Test running job with total qtime 5 minutes
        ("model-run", 
        "Tue Feb 10 15:00:00 2026", 
        "Tue Feb 10 15:05:00 2026", 
        "Total queue time:", 
        "0h 5m 0s"),

        # Test archived job with total qtime 30 minutes
        ("archive", 
        "Tue Feb 10 15:00:00 2026", 
        "Tue Feb 10 15:30:00 2026", 
        "Total queue time:", 
        "0h 30m 0s"),
    ]
)
def test_status_queue_time(tmp_path, capsys, job_stage, qtime, stime, time_label, time_message):
    """Test that queue time is calculated and displayed for a queued job."""
    print(qtime)
    # Create a temporary lab and config
    lab_path = tmp_path / "lab"
    archive_path = lab_path / "archive" / "control-exp"
    archive_path.mkdir(parents=True, exist_ok=True)
    control_path = tmp_path / "control-exp"
    control_path.mkdir()
    config_path = control_path / "config.yaml"

    # Create a minimal config file
    with open(config_path, 'w') as f:
        json.dump({'model': 'test'}, f)

    # Create a minimal metadata file
    metadata_path = control_path / "metadata.yaml"
    with open(metadata_path, 'w') as f:
        json.dump({'experiment_uuid': 'test-uuid'}, f)

    # Create a queued job file
    job_file = archive_path / "payu_jobs" / "3" / "run" / "test-job-id-3.json"
    job_file.parent.mkdir(parents=True, exist_ok=True)

    job_data = {
        "scheduler_job_id": "test-job-id-3",
        "scheduler_type": "pbs",
        "metadata": {"uuid": "test-uuid"},
        "payu_current_run": 3,
        "stage": job_stage,
        "qtime": qtime,
        "stime": stime
    }
    with open(job_file, 'w') as f:
        json.dump(job_data, f)

    # Run the command
    with pytest.warns(PayuGitWarning):
        runcmd(
            lab_path=str(lab_path),
            config_path=str(config_path),
            json_output=False,
            update_jobs=False,
            all_runs=False,
            run_number=None
        )

    # Check the output contains the expected queue time
    output = capsys.readouterr().out
    assert time_label in output
    assert time_message in output