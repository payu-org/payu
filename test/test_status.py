import json
import pytest
from freezegun import freeze_time
import cftime
import shutil
from unittest.mock import Mock, MagicMock

from test.common import cd, tmpdir, labdir, write_config, ctrldir_basename, ctrldir

from payu.status import (
    _sort_run_jobs,
    find_file_match,
    get_scheduler_log,
    find_scheduler_logs,
    get_job_file_list,
    build_job_info,
    display_job_info,
    collect_expt_paths,
    display_expt_paths,
)

from payu.laboratory import Laboratory
from payu.experiment import Experiment
from payu.subcommands.status_cmd import runcmd
from payu.git_utils import PayuGitWarning
import payu.errors as errors

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


def write_job_file(archive_path, job_id, run_number, job_data, type="run"):
    """Helper function to write job data to a file"""
    job_file = (
        archive_path / "payu_jobs" / str(run_number) / type / f"{job_id}.json"
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
                        "model_finish_time": "1901-03-15T00:30:00",
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
            job_id="test-job-id-0failed",
            run_number=3,
            job_data={
                "scheduler_job_id": "test-job-id-0failed",
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

@pytest.fixture
def archived_collate_jobs(tmp_path, request):
    """Fixture to create a collate job files"""
    if request.param:
        files = []
        # I design the test to have success collate run on run 0 and 2,
        # And still running collate on run 1.
        for i in [0, 2]:
            files.append(
                write_job_file(
                    archive_path=tmp_path / "archive",
                    job_id=f"test-collate-id-{i}",
                    run_number=i,
                    job_data={
                        "scheduler_job_id": f"test-collate-id-{i}",
                        "scheduler_type": "pbs",
                        "metadata": {"uuid": "test-uuid"},
                        "payu_current_run": i,
                        "stage": "exited",
                        "payu_collate_status": 0,
                        "timings": {
                            "payu_start_time": f"2025-08-1{i}T12:00:00"
                        }
                    },
                    type="collate"
                )
            )
        return files

@pytest.fixture
def failed_collate_jobs(tmp_path, request):
    """Fixture to create a failed collate job file for run 2"""
    if request.param:
        return write_job_file(
            archive_path=tmp_path / "archive",
            job_id="test-collate-id-0failed",
            run_number=2,
            job_data={
                "scheduler_job_id": "test-collate-id-0failed",
                "scheduler_type": "pbs",
                "metadata": {"uuid": "test-uuid"},
                "payu_current_run": 2,
                "stage": "exited",
                "payu_collate_status": 1,
                "timings": {
                    "payu_start_time": "2025-08-12T09:00:00"
                }
            },
            type="collate"
        )

@pytest.fixture
def running_collate_jobs(tmp_path, request):
    """Fixture to create a running collate job file for run 1"""
    if request.param:
        return write_job_file(
            archive_path=tmp_path / "archive",
            job_id="test-collate-id-running",
            run_number=1,
            job_data={
                "scheduler_job_id": "test-collate-id-1",
                "scheduler_type": "pbs",
                "metadata": {"uuid": "test-uuid"},
                "payu_current_run": 1,
                "stage": "running",
                "timings": {
                    "payu_start_time": "2025-08-11T09:00:00"
                }
            },
            type="collate"
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
        'model_finish_time': '1901-03-15T00:30:00',
        'stage': 'archive',
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
        'model_finish_time': None,
        'stage': 'model-run',
        'stderr_file': None,
        'stdout_file': None,
        'start_time': '2025-08-15T16:30:00',
        'cur_expt_time': '1901-01-15T00:30:00'
    }


def expected_queued_job_info():
    return {
        'exit_status': None,
        'job_id': 'test-job-id-3',
        'run_id': None,
        'model_exit_status': None,
        'model_finish_time': None,
        'stage': 'queued',
        'stderr_file': None,
        'stdout_file': None,
        'start_time': None
    }


def expected_failed_job_info():
    return {
        'exit_status': 1,
        'job_id': 'test-job-id-0failed',
        'run_id': 'commit-hash-failed',
        'model_exit_status': None,
        'model_finish_time': None,
        'stage': 'setup',
        'stderr_file': None,
        'stdout_file': None,
        'start_time': '2025-08-13T12:00:00'
    }

def expected_running_collate_job_info(run_number):
    return {
        'job_id': f'test-collate-id-{run_number}',
        'stage': 'running',
        'exit_status': None,
        'stderr_file': None,
        'stdout_file': None,
        'start_time': f'2025-08-1{run_number}T09:00:00'
    }

def expected_collate_job_info(run_number):
    return {
        'job_id': f'test-collate-id-{run_number}',
        'stage': 'exited',
        'exit_status': 0,
        'stderr_file': None,
        'stdout_file': None,
        'start_time': f'2025-08-1{run_number}T12:00:00'
    }

def expected_failed_collate_job_info():
    return {
        'job_id': "test-collate-id-0failed",
        'stage': 'exited',
        'exit_status': 1,
        'stderr_file': None,
        'stdout_file': None,
        'start_time': '2025-08-12T09:00:00'
    }


def remove_job_file_paths(data):
    """Remove job_file paths from the data for comparison."""
    if 'runs' in data:
        for payu_jobs in data['runs'].values():
            for job_type in payu_jobs.keys():
                for job_info in payu_jobs[job_type]:
                    del job_info['job_file']


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
    # Mock expt.get_model_cur_expt_time() in build_job_info
    mock_expt = MagicMock()
    mock_expt.get_model_cur_expt_time.return_value = cftime.datetime(1901, 1, 15, 0, 30, 0)

    all_runs = build_job_info(
        control_path=tmp_path / "control",
        archive_path=tmp_path / "archive",
        all_runs=True,
        expt=mock_expt
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
    # Mock expt.get_model_cur_expt_time() in build_job_info
    mock_expt = MagicMock()
    mock_expt.get_model_cur_expt_time.return_value = cftime.datetime(1901, 1, 15, 0, 30, 0)

    latest_data = build_job_info(
        control_path=tmp_path / "control",
        archive_path=tmp_path / "archive",
        expt=mock_expt
    )

    # Remove job file from check as it contains tmp_path
    remove_job_file_paths(latest_data)

    assert latest_data == expected


@pytest.mark.parametrize(
    "archive_jobs, running_collate_jobs, archived_collate_jobs, failed_collate_jobs, expected",
    [
        (True, True, True, True,
        {
                'runs': {
                    0: {'run': [expected_archive_job_info(0)],
                        'collate': [expected_collate_job_info(0)]},
                    1: {'run': [expected_archive_job_info(1)],
                        'collate': [expected_running_collate_job_info(1)]},
                    2: {'run': [expected_archive_job_info(2)],
                        'collate': [expected_failed_collate_job_info(),
                                    expected_collate_job_info(2)]}
                }
            }),
    ],
    indirect=["archive_jobs", "running_collate_jobs", "archived_collate_jobs", "failed_collate_jobs"]
)
def test_build_job_info_collate(tmp_path, archive_jobs, running_collate_jobs, 
                                archived_collate_jobs, failed_collate_jobs, expected):
    """ Test collate job info is correctly included in build_job_info."""
    # Mock expt.get_model_cur_expt_time() in build_job_info
    mock_expt = MagicMock()
    mock_expt.get_model_cur_expt_time.return_value = cftime.datetime(1901, 1, 15, 0, 30, 0)

    # ---- For the latest runs ----
    latest_data = build_job_info(
        control_path=tmp_path / "control",
        archive_path=tmp_path / "archive",
        expt=mock_expt
    )

    # Remove job file from check as it contains tmp_path
    remove_job_file_paths(latest_data)

    expected_latest = {
        # Should only include the last run number
        'runs': {
            2: {
                'run': expected['runs'][2]['run'],
                # Should only include the lastest colalte job
                'collate': [expected['runs'][2]['collate'][1]]}
        }}
    assert latest_data == expected_latest

    # ---- For all runs ----
    all_runs = build_job_info(
        control_path=tmp_path / "control",
        archive_path=tmp_path / "archive",
        all_runs=True,
        expt=mock_expt
    )

    # Remove job file from check as it contains tmp_path
    remove_job_file_paths(all_runs)

    assert all_runs == expected


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
        with pytest.raises(errors.PayuRuntimeError, match="Metadata is not setup"):
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
            "Current Queue Time:",
            "0h 5m ",
        ),

        # Test running job with total qtime 5 minutes
        ("model-run", 
        "Tue Feb 10 15:00:00 2026", 
        "Tue Feb 10 15:05:00 2026", 
        "Total Queue Time:", 
        "0h 5m 0s"),

        # Test archived job with total qtime 30 minutes
        ("archive", 
        "Tue Feb 10 15:00:00 2026", 
        "Tue Feb 10 15:30:00 2026", 
        "Total Queue Time:", 
        "0h 30m 0s"),
    ]
)
def test_status_queue_time(tmp_path, capsys, job_stage, qtime, stime, time_label, time_message):
    """Test that queue time is calculated and displayed for a queued job."""
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
        "experiment_metadata": {"experiment_uuid": "test-uuid"},
        "payu_current_run": 3,
        "stage": job_stage,
        "scheduler_job_info":{
           "Jobs": {
                "test-job-id-3":{
                    "Job_Name": "double_gyre",
                    "qtime": qtime,
                    "stime": stime
                }
            }
        }
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

@pytest.mark.parametrize("cur_expt_time", [
    (cftime.datetime(2026, 2, 10, 15, 0, 0)),
    (None)
])
def test_status_cur_expt_time(tmp_path, monkeypatch, capsys, cur_expt_time):
    """Test that current experiment time is displayed at the stage of model-run."""
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
        "experiment_metadata": {"experiment_uuid": "test-uuid"},
        "payu_current_run": 3,
        "stage": "model-run",
        "scheduler_job_info":{
           "Jobs": {
                "test-job-id-3":{"Job_Name": "double_gyre",}
            }
        }
    }
    with open(job_file, 'w') as f:
        json.dump(job_data, f)

    # Run the command
    monkeypatch.setattr(Experiment, "get_model_cur_expt_time", lambda self: cur_expt_time)
    with pytest.warns(PayuGitWarning):
        runcmd(
            lab_path=str(lab_path),
            config_path=str(config_path),
            json_output=False,
            update_jobs=False,
            all_runs=False,
            run_number=None
        )

    # Check the output contains the expected cur_expt_time
    output = capsys.readouterr().out
    if cur_expt_time:
        assert "Current Expt Time:" in output
        assert cur_expt_time.isoformat() in output
    else:
        assert "Current Expt Time:" not in output


def test_status_model_finish_time(tmp_path, capsys):
    """Test that model finish time is displayed for an archived job."""
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

    # Create an archived job file
    job_file = archive_path / "payu_jobs" / "3" / "run" / "test-job-id-3.json"
    job_file.parent.mkdir(parents=True, exist_ok=True)

    job_data = {
        "scheduler_job_id": "test-job-id-3",
        "scheduler_type": "pbs",
        "experiment_metadata": {"experiment_uuid": "test-uuid"},
        "payu_current_run": 3,
        "stage": "archive",
        "payu_model_run_status": 0,
        "model_finish_time": "2026-03-11T15:00:00"
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

    # Check the output contains the expected model finish time
    output = capsys.readouterr().out
    assert "Model Finish Time:" in output
    assert "2026-03-11T15:00:00" in output


@pytest.mark.parametrize("archive_jobs,running_job,queued_job,failed_job, job_info",
    [
        (True, False, False, False, expected_archive_job_info(3)),
        (False, True, False, False, expected_running_job_info()),
        (False, False, True, False, expected_queued_job_info()),
        (False, False, False, True, expected_failed_job_info()),
    ])
def test_display_job_info(tmp_path, capsys, archive_jobs, running_job, queued_job, failed_job, job_info):
    """ Test that job info is displayed correctly for different stages and available information."""
    job_info['job_file'] = str(tmp_path / "payu_jobs" / "3" / "run" / "test-job-id-3.json")
    data = {'runs': {3: {'run': [job_info]}}}
    display_job_info(data)

    captured = capsys.readouterr().out

    if archive_jobs:
        assert "Model Finish Time:" in captured
        assert job_info['model_finish_time'] in captured
    elif running_job:
        assert "Current Expt Time:" in captured
        assert "1901-01-15T00:30:00" in captured
    else:
        assert "Current Expt Time:" not in captured
        assert "Model Finish Time:" not in captured


@pytest.mark.parametrize("running_job", [True], indirect=True)
def test_build_job_info_error_get_cur_expt_time(tmp_path, running_job):
    """Test that if get_model_cur_expt_time raises an error, other parts of job info are built correctly."""
    # Mock get_model_cur_expt_time to raise an error
    mock_expt = MagicMock()
    mock_expt.get_model_cur_expt_time.side_effect = FileNotFoundError("Log file not found")

    data = build_job_info(
        control_path=tmp_path / "control",
        archive_path=tmp_path / "archive",
        expt=mock_expt
    )

    # Remove job file from check as it contains tmp_path
    remove_job_file_paths(data)

    expected_info = expected_running_job_info()
    del expected_info["cur_expt_time"]

    assert data == {'runs': {3: {'run': [expected_info]}}}


def test_get_job_file():
    """Test the expt.get_job_file function returns the correct path"""
    tmpdir.mkdir(parents=True, exist_ok=True)
    labdir.mkdir(parents=True, exist_ok=True)
    ctrldir.mkdir(parents=True, exist_ok=True)

    # Write a minimal config file
    config = {
            'laboratory': 'lab',
            'jobname': 'testrun',
            'model': 'mom6',
            'exe': 'test.exe',
            'experiment': ctrldir_basename,
            'metadata': {
                'enable': False
            }
    }
    write_config(config)

    # Set up a mock experiment
    with cd(ctrldir):
        lab = Laboratory(lab_path=str(labdir))
        expt = Experiment(lab, reproduce=False)
    expt.archive_path = tmpdir / "archive" 
    expt.counter = 3
    expt.scheduler.get_job_id = Mock(return_value="12345")

    assert expt.get_job_file() == expt.archive_path / "payu_jobs" / "3" / "run" / "12345.json"
    assert expt.get_job_file(type='collate') == expt.archive_path / "payu_jobs" / "3" / "collate" / "12345.json"

    shutil.rmtree(tmpdir)

@pytest.mark.parametrize("sync_path", ["path/to/sync", None])
def test_collect_expt_paths(tmp_path, sync_path):
    """Test that collect_expt_paths returns the correct paths"""
    # Create a temporary lab and config
    lab_path = tmp_path / "lab"
    lab_path.mkdir()
    control_path = tmp_path / "control"
    control_path.mkdir()

    # Write a minimal config file
    config = {
            'model': 'mom6',
            'experiment': ctrldir_basename,
            'sync':{
                'enable': False,    
                'path': sync_path,
            }
    }
    with open(control_path / "config.yaml", 'w') as f:
        json.dump(config, f)

    # Create a minimal metadata file
    metadata_path = control_path / "metadata.yaml"
    with open(metadata_path, 'w') as f:
        json.dump({'experiment_uuid': 'test-uuid'}, f)

    # Set up a mock experiment
    with cd(control_path):
        lab = Laboratory(lab_path=str(lab_path))
        expt = Experiment(lab, reproduce=False)

    expt_paths = collect_expt_paths(expt)
    assert expt_paths['experiment_uuid'] == "test-uuid"
    assert expt_paths['experiment_name'] == ctrldir_basename
    assert str(expt_paths['control_path']) == str(control_path)
    assert str(expt_paths['lab_path']) == str(lab_path)
    assert str(expt_paths['work_path']) == str(expt.work_path)
    assert str(expt_paths['archive_path']) == str(expt.archive_path)
    if sync_path:
        assert str(expt_paths['sync_path']) == str(sync_path)
    else:
        assert expt_paths['sync_path'] == "Unconfigured"

    
def test_collect_expt_paths_no_metadata(tmp_path):
    """Test that collect_expt_paths raises an error when metadata is not set up"""
    # Create a temporary lab and config
    lab_path = tmp_path / "lab"
    lab_path.mkdir()
    control_path = tmp_path / "control"
    control_path.mkdir()

    # Write a minimal config file
    config = {
            'model': 'mom6'
    }
    with open(control_path / "config.yaml", 'w') as f:
        json.dump(config, f)

    # Set up a mock experiment
    with cd(control_path):
        lab = Laboratory(lab_path=str(lab_path))
        expt = Experiment(lab, reproduce=False)
        expt.metadata = None  # Mock a bad metadata

    with pytest.warns(UserWarning, match="Failed to collect experiment paths: 'NoneType' object has no attribute 'uuid'"):
        expt_paths = collect_expt_paths(expt)
        assert expt_paths == {}


def test_display_expt_paths(capsys):
    """Test that display_expt_paths prints the correct paths"""
    expt_paths = {
        'experiment_uuid': "test-uuid",
        'experiment_name': "test-experiment",
        'control_path': "/path/to/control",
        'lab_path': None,
        'sync_path': "Unconfigured"
    }
    display_expt_paths(expt_paths)

    label_width = 18
    captured = capsys.readouterr().out
    assert f"{f'Experiment UUID:':<{label_width}} test-uuid" in captured
    assert f"{f'Experiment Name:':<{label_width}} test-experiment" in captured
    assert f"{f'Control Directory:':<{label_width}} /path/to/control" in captured
    assert "Laboratory Path" not in captured
    assert f"{f'Sync Destination:':<{label_width}} Unconfigured" in captured



@pytest.mark.parametrize(
    "archive_jobs", [True], indirect=True
)
def test_build_job_info_string_run_number(tmp_path, archive_jobs):
    """Test that build_job_info ignore the runs with string run numbers ."""
    job_file = tmp_path / "archive" / "payu_jobs" / "2" / "run" / "test-job-id-2.json"
    with open(job_file, 'r') as f:
        job_data = json.load(f)

    # Change one of the payu_current_run values to a string
    job_data["payu_current_run"] = "2"
    with open(job_file, 'w') as f:
        json.dump(job_data, f)

    # Mock expt.get_model_cur_expt_time() in build_job_info
    mock_expt = MagicMock()
    mock_expt.get_model_cur_expt_time.return_value = cftime.datetime(1901, 1, 15, 0, 30, 0)

    all_runs = build_job_info(
        control_path=tmp_path / "control",
        archive_path=tmp_path / "archive",
        all_runs=True,
        expt=mock_expt
    )

    # Remove job file from check as it contains tmp_path
    remove_job_file_paths(all_runs)

    expected = {
                'runs': {
                    0: {'run': [expected_archive_job_info(0)]},
                    1: {'run': [expected_archive_job_info(1)]},
                    2: {'run': [expected_archive_job_info(2)]}
                }
            }
    assert all_runs == expected


def test__sort_run_jobs():
    """Test that _sort_run_jobs correctly sorts jobs by job_id and then start_time."""
    run_info = [
        {"job_id": "3", "start_time": "2025-06-03T09:00:00"},
        {"start_time": "2025-06-06T09:00:00"},
        {"job_id": "1", "start_time": "2025-06-01T09:00:00"},
        {"start_time": "2025-06-04T09:00:00"},
    ]

    _sort_run_jobs(run_info)

    assert run_info == [
        {"start_time": "2025-06-04T09:00:00"},
        {"start_time": "2025-06-06T09:00:00"},
        {"job_id": "1", "start_time": "2025-06-01T09:00:00"},
        {"job_id": "3", "start_time": "2025-06-03T09:00:00"},
    ]