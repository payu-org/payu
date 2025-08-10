import json
import pytest

from payu.status import (
    find_file_match,
    find_scheduler_log_path,
    find_scheduler_logs,
    get_job_file_list,
    query_job_info
)


def test_find_file_match(tmp_path):
    test_file = tmp_path / "job_name.o146702704"
    test_file.touch()
    result = find_file_match(pattern="*.o146702704", path=tmp_path)
    assert result == test_file


def test_find_file_match_no_match(tmp_path):
    result = find_file_match(pattern="*.nonexistent", path=tmp_path)
    assert result is None

    result = find_file_match(
        pattern="*.o146702704",
        path=tmp_path / "nonexistent_dir"
    )
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
def test_find_scheduler_log_path(tmp_path, base_dir):
    if base_dir is None:
        file_path = None
    else:
        file_path = tmp_path / base_dir / "test.o123"
        file_path.mkdir(parents=True, exist_ok=True)
        file_path.touch()

    result = find_scheduler_log_path(
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


@pytest.fixture
def queued_job_file(tmp_path, request):
    """Fixture to create a queued job file"""
    if request.param:
        job_file = tmp_path / "control" / "payu-jobs" / "payu-run.json"
        job_file.parent.mkdir(parents=True, exist_ok=True)
        with open(job_file, 'w') as f:
            json.dump({
                "scheduler_job_id": "12345",
                "scheduler_type": "pbs",
                "metadata": {"uuid": "test-uuid"},
                "payu_current_run": 3,
                "stage": "queued"
            }, f)
        return job_file


@pytest.fixture
def work_job_file(tmp_path, request):
    """Fixture to create a work job file"""
    if request.param:
        job_file = tmp_path / "work" / "payu-jobs" / "payu-run.json"
        job_file.parent.mkdir(parents=True, exist_ok=True)
        with open(job_file, 'w') as f:
            json.dump({
                "scheduler_job_id": "12345",
                "scheduler_type": "pbs",
                "metadata": {"uuid": "test-uuid"},
                "payu_current_run": 3,
                "stage": "model-run"
            }, f)
        return job_file


@pytest.fixture
def archive_job_files(tmp_path, request):
    """Fixture to create an archived job files"""
    if request.param:
        files = []
        for i in range(3):
            output_dir = tmp_path / "archive" / f"output00{i}"
            job_file = output_dir / "payu-jobs" / "payu-run.json"
            job_file.parent.mkdir(parents=True, exist_ok=True)
            with open(job_file, 'w') as f:
                json.dump({
                    "scheduler_job_id": f"test-job-id-{i}",
                    "scheduler_type": "pbs",
                    "metadata": {"uuid": "test-uuid"},
                    "payu_current_run": i,
                    "stage": "archived"
                }, f)
            files.append(job_file)
        return files


@pytest.mark.parametrize(
    "archive_job_files,work_job_file,queued_job_file,latest_file,all_files",
    [
        # Only queued job file exists
        (
            False, False, True, ["control/payu-jobs/payu-run.json"],
            ["control/payu-jobs/payu-run.json"]
        ),
        # Archive job file exists but there's a queued job file
        (
            True, False, True, ["control/payu-jobs/payu-run.json"],
            [
                "control/payu-jobs/payu-run.json",
                "archive/output002/payu-jobs/payu-run.json",
                "archive/output001/payu-jobs/payu-run.json",
                "archive/output000/payu-jobs/payu-run.json"
            ]
        ),
        # Only work job file exists
        (
            False, True, False, ["work/payu-jobs/payu-run.json"],
            ["work/payu-jobs/payu-run.json"]
        ),
        # Both archive and work job files exist
        (
            True, True, False, ["work/payu-jobs/payu-run.json"],
            [
                "work/payu-jobs/payu-run.json",
                "archive/output002/payu-jobs/payu-run.json",
                "archive/output001/payu-jobs/payu-run.json",
                "archive/output000/payu-jobs/payu-run.json"
            ]
        ),
        # Only archive job files exist
        (
            True, False, False, ["archive/output002/payu-jobs/payu-run.json"],
            [
                "archive/output002/payu-jobs/payu-run.json",
                "archive/output001/payu-jobs/payu-run.json",
                "archive/output000/payu-jobs/payu-run.json"
            ]
        ),
        # No job files exist
        (False, False, False, [], []),
    ],
    indirect=["archive_job_files", "queued_job_file", "work_job_file"]
)
def test_get_job_file_list(tmp_path, archive_job_files, queued_job_file,
                           work_job_file, latest_file, all_files):
    """Test both default and all_runs=True"""
    files = get_job_file_list(
        control_path=tmp_path / "control",
        archive_path=tmp_path / "archive",
        work_path=tmp_path / "work",
    )
    # Expand expected paths to full paths
    expected_latest_paths = [tmp_path / file for file in latest_file]
    assert files == expected_latest_paths

    all_files = get_job_file_list(
        control_path=tmp_path / "control",
        archive_path=tmp_path / "archive",
        work_path=tmp_path / "work",
        all_runs=True
    )
    expected_all_paths = [tmp_path / file for file in all_files]
    assert all_files == expected_all_paths


@pytest.mark.parametrize(
    "archive_job_files,work_job_file,queued_job_file,run_number,expected_file",
    [
        # Test with a queued job file
        # Note: Run number with queued and work files don't need to match
        # as these files are checked later
        (False, False, True, 10, ["control/payu-jobs/payu-run.json"]),
        # Test with a work job file
        (False, True, False, 3, ["work/payu-jobs/payu-run.json"]),
        # Test with an archived job files
        (True, False, False, 2, ["archive/output002/payu-jobs/payu-run.json"]),
        (True, False, False, 0, ["archive/output000/payu-jobs/payu-run.json"]),
        # Test with no files
        (False, False, False, 1, []),
        # Test with a too high run number that does not match any file
        (True, False, False, 5, []),
    ],
    indirect=["archive_job_files", "queued_job_file", "work_job_file"]
)
def test_get_job_file_list_selected_run(tmp_path, queued_job_file,
                                        work_job_file, archive_job_files,
                                        run_number, expected_file):
    """Test selecting the run number"""
    files = get_job_file_list(
        control_path=tmp_path / "control",
        archive_path=tmp_path / "archive",
        work_path=tmp_path / "work",
        run_number=run_number
    )
    assert files == [tmp_path / file for file in expected_file]


@pytest.mark.parametrize(
    "archive_job_files,work_job_file,queued_job_file,expected",
    [
        (
            False, False, True,
            {
                'runs': {
                    3: {
                        'run': {
                            'exit_status': None,
                            'job_id': '12345',
                            'model_exit_status': None,
                            'stage': 'queued',
                            'stderr_file': None,
                            'stdout_file': None
                        }
                    }
                }
            }
        ),
        (
            True, True, False,
            {
                'runs': {
                    0: {
                        'run': {
                            'exit_status': None,
                            'job_id': 'test-job-id-0',
                            'model_exit_status': None,
                            'stage': 'archived',
                            'stderr_file': None,
                            'stdout_file': None
                        }
                    },
                    1: {
                        'run': {
                            'exit_status': None,
                            'job_id': 'test-job-id-1',
                            'model_exit_status': None,
                            'stage': 'archived',
                            'stderr_file': None,
                            'stdout_file': None
                        }
                    },
                    2: {
                        'run': {
                            'exit_status': None,
                            'job_id': 'test-job-id-2',
                            'model_exit_status': None,
                            'stage': 'archived',
                            'stderr_file': None,
                            'stdout_file': None
                        }
                    },
                    3: {
                        'run': {
                            'exit_status': None,
                            'job_id': '12345',
                            'model_exit_status': None,
                            'stage': 'model-run',
                            'stderr_file': None,
                            'stdout_file': None
                        }
                    }
                }
            }
        ),
        (False, False, False, {})
    ],
    indirect=["archive_job_files", "work_job_file", "queued_job_file"]
)
def test_query_job_info(tmp_path, archive_job_files, work_job_file,
                        queued_job_file, expected):

    latest_data = query_job_info(
        control_path=tmp_path / "control",
        archive_path=tmp_path / "archive",
        work_path=tmp_path / "work",
        all_runs=True
    )

    # Remove job file from check as it contains tmp_path
    if 'runs' in latest_data:
        for run in latest_data['runs'].values():
            if 'run' in run:
                del run['run']['job_file']

    assert latest_data == expected
