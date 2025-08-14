"""
Methods used by the `payu status` command to display the status of
payu runs by inspecting the job files generated for telemetry,
scheduler stdout/stderr logs, and querying the scheduler
"""

import glob
from pathlib import Path
from typing import Any, Optional
import warnings

from payu.metadata import Metadata
from payu.schedulers import Scheduler
from payu.fsops import list_archive_dirs
from payu.telemetry import (
    find_run_job_file,
    read_job_file,
    update_job_file,
    remove_job_file
)


def find_file_match(
            pattern: str,
            path: Path
        ) -> Optional[Path]:
    """Find a file matching the pattern in the given path"""
    files = glob.glob(str(path / pattern))
    if len(files) >= 1:
        if len(files) != 1:
            warnings.warn(
                f"Multiple files found for pattern {pattern} in path {path}: "
                f"{files}."
            )
        return Path(files[0])
    return None


def find_scheduler_log_path(
            pattern: str,
            control_path: Path,
            archive_path: Path,
        ) -> Optional[Path]:
    """Given a glob pattern, find the scheduler log file either in
    the control path or in the archive's pbs_logs path"""
    file = find_file_match(pattern, control_path)
    if file is None:
        file = find_file_match(pattern, archive_path / "pbs_logs")
    return file


def find_scheduler_logs(
            job_id: str,
            control_path: Path,
            archive_path: Path,
            type: str = "pbs",
        ) -> tuple[Optional[Path], Optional[Path]]:
    """Find the stdout and stderr log files for the scheduler job ID"""
    if job_id is None or job_id == "":
        # No job ID - payu job could have run locally
        return None, None

    # TODO: Support non-default stderr and stdout file names
    if type == "pbs":
        # For PBS, the log files are named .o<jobid> and .e<jobid>
        job_id = job_id.split(".")[0]  # Remove any suffix
        stdout_pattern = f"*.o{job_id}"
        stderr_pattern = f"*.e{job_id}"
    elif type == "slurm":
        # For Slurm, the default log files are named slurm-<jobid>.out
        stdout_pattern = f"slurm-{job_id}.out"
        stderr_pattern = f"slurm-{job_id}.err"
    else:
        warnings.warn(f"Unsupported scheduler type: {type}")
        return None, None

    # Find the stdout and stderr log files
    stdout_path = find_scheduler_log_path(
        pattern=stdout_pattern,
        control_path=control_path,
        archive_path=archive_path
    )
    stderr_path = find_scheduler_log_path(
        pattern=stderr_pattern,
        control_path=control_path,
        archive_path=archive_path
    )
    return stdout_path, stderr_path


def get_job_file_list(
            control_path: Path,
            work_path: Path,
            archive_path: Path,
            run_number: Optional[int] = None,
            all_runs: Optional[bool] = False
        ) -> list[Path]:
    """
    Generate a list of run job files to query for job information.
    By default, this will return the latest run job file
    that is either in the control, work or latest archive output directory.
    Otherwise it returns any queued or running jobs,
    and either:
     - completed job in the selected output if `run_number` is specified
     - all completed jobs in archive if `all_runs` is True,

    Filtering the files here, reduces the number of files to read and parse
    later on
    """
    search_paths = [control_path, work_path]
    outputs = []
    if archive_path.exists():
        outputs = list_archive_dirs(archive_path=archive_path,
                                    dir_type='output')
    if not outputs:
        # If no output directories, return any queued or running jobs
        pass
    elif run_number is not None:
        if f"output{run_number:03}" in outputs:
            search_paths.append(archive_path / f"output{run_number:03}")
    elif all_runs:
        search_paths.extend([archive_path / output for output in outputs])
    else:
        # Only return latest payu run job file
        # Note: Priority in search is given to running and queued jobs
        search_paths.append(archive_path / outputs[-1])
        job_file = find_run_job_file(search_paths)
        return [] if job_file is None else [job_file]

    # Find all run job files in the search paths
    files = []
    for path in search_paths:
        file = find_run_job_file([path])
        if file is not None:
            files.append(file)
    return files


def query_job_info(
            control_path: Path,
            work_path: Path,
            archive_path: Path,
            run_number: Optional[int] = None,
            all_runs: Optional[bool] = False
        ) -> Optional[dict[str, Any]]:
    """
    Generate a dictionary of jobs information (exit status, stage),
    and mapping stdout and stderr files.

    By default, this uses the latest run job file - e.g.
    any that is queued or running, or the latest archived output

    If `run_number` is specified, it will return the jobs for that run number
    If `all_runs` is True, it will also include all jobs in the archive
    for every run number

    # TODO: Extend with collate, sync when their job files are implemented
    """
    job_files = get_job_file_list(
        control_path=control_path,
        work_path=work_path,
        archive_path=archive_path,
        run_number=run_number,
        all_runs=all_runs
    )
    if job_files == []:
        return {}

    # Build the data file
    status_data = {}

    for job_file in job_files:
        # Read the job file
        data = read_job_file(job_file)

        # Filter out jobs that aren't the specified run number
        if run_number is not None and data['payu_current_run'] != run_number:
            continue

        if "experiment_uuid" in data.get("experiment_metadata", {}):
            uuid = data["experiment_metadata"]["experiment_uuid"]
            status_data["experiment_uuid"] = uuid

        stdout, stderr = find_scheduler_logs(
            job_id=data.get("scheduler_job_id"),
            control_path=control_path,
            archive_path=archive_path,
            type=data.get("scheduler_type")
        )
        run_info = {
            "job_id": data.get("scheduler_job_id"),
            "stage": data.get("stage"),
            "exit_status": data.get("payu_run_status"),
            "model_exit_status": data.get("payu_model_run_status"),
            "stdout_file": str(stdout) if stdout else None,
            "stderr_file": str(stderr) if stderr else None,
            "job_file": str(job_file),
        }
        if "runs" not in status_data:
            status_data["runs"] = {}
        status_data["runs"][data["payu_current_run"]] = {"run": run_info}

    # Ensure runs are sorted by run number
    if "runs" in status_data:
        sorted_runs = dict(sorted(
            status_data["runs"].items(),
            key=lambda item: int(item[0])
        ))
        status_data["runs"] = sorted_runs

    return status_data


def update_all_job_files(
            status_data: dict[str, Any],
            scheduler: Scheduler
        ) -> None:
    """
    Update job files in the queried job information

    This will remove any queued files that have exited or were deleted
    before running.

    If a job is marked as still running in the job file, it will
    check whether the job is still in the scheduler's job list,
    and it's respective exit status if it has exited.

    As this job queries the scheduler for running jobs, it is recommended to
    not run this method too frequently. NCI may consider repeated queries
    to the scheduler in quick succession as an attack. This is also why
    this method only queries the scheduler once for all jobs

    TODO: Parse the stdout files to get the exit status (though this will
    require specific scheduler methods..)
    TODO: Could copy the job files to the error logs so these
    can be included in the status output
    """
    # Get all jobs status and exit codes from the scheduler
    all_jobs = scheduler.get_all_jobs_status()
    if all_jobs is None:
        warnings.warn(
            "Failed to get job information from the scheduler"
        )
        return

    for run_number, jobs in status_data.get("runs", {}).items():
        data = jobs["run"]

        job_id = data.get("job_id")
        if job_id is None or job_id == "":
            # No job ID, nothing to update
            continue
        elif job_id not in all_jobs:
            # If the job is not in the scheduler's job list, it has
            # exited or been deleted
            if data["stage"] == "queued":
                remove_job_file(file_path=Path(data["job_file"]))
            elif data["stage"] != "completed":
                # Job has exited before payu has completed
                update_job_file(
                    file_path=Path(data["job_file"]),
                    data={
                        "stage": "completed",
                        "payu_run_status": 1
                    }
                )
        elif all_jobs[job_id].get("exit_status", None) is not None:
            if data["stage"] == "queued":
                # Job may have exited on startup, remove the queued file
                remove_job_file(file_path=Path(data["job_file"]))
            elif data["stage"] != "completed":
                # Update the job file with the exit status
                update_job_file(
                    file_path=Path(data["job_file"]),
                    data={
                        "stage": "completed",
                        "payu_run_status": all_jobs[job_id]["exit_status"]
                    }
                )


def print_line(label: str, key: Any, data: dict[str, Any]) -> None:
    """Print a line with label and value from the data,
    if it is defined"""
    value = data.get(key)
    label_width = 18
    if value is not None and value != "":
        print(f"  {f'{label}:':<{label_width}} {value}")


def display_job_info(data: dict[str, Any]) -> None:
    """
    Display the job information in a human-readable way
    """
    runs = data.get("runs", {})
    if not runs:
        print("No run information available.")
        return

    for run_number, jobs in runs.items():
        run_info = jobs["run"]
        print("=" * 40)
        print(f"Run: {run_number}")
        print_line("Job ID", "job_id", run_info)
        print_line("Stage", "stage", run_info)
        exit_status = run_info.get("exit_status")
        if exit_status is not None:
            status_str = "Success" if exit_status == 0 else "Failed"
            print(f"  Exit Status:       {exit_status} ({status_str})")
        model_exit = run_info.get("model_exit_status")
        if model_exit is not None:
            status_str = "Success" if model_exit == 0 else "Failed"
            print(f"  Model Exit Code:   {model_exit} ({status_str})")
        print_line("Output Log", "stdout_file", run_info)
        print_line("Error Log", "stderr_file", run_info)
        print_line("Job File", "job_file", run_info)
    print("=" * 40)
