"""
Methods used by the `payu status` command to display the status of
payu runs by inspecting the job files generated for telemetry,
scheduler stdout/stderr logs, and querying the scheduler
"""

from pathlib import Path
from typing import Any, Optional
import warnings

from payu.schedulers import Scheduler
from payu.telemetry import (
    read_job_file,
    update_job_file,
    remove_job_file
)


def find_file_match(pattern: str, path: Path) -> Optional[Path]:
    """Find a file matching the pattern in the given path"""
    files = list(path.glob(pattern))
    if not files:
        return None
    if len(files) > 1:
        warnings.warn(
            f"Multiple files found for pattern {pattern} in path {path}: "
            f"{files}."
        )
    return files[0]


def get_scheduler_log(
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
    if not job_id:
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
    stdout_path = get_scheduler_log(stdout_pattern, control_path, archive_path)
    stderr_path = get_scheduler_log(stderr_pattern, control_path, archive_path)
    return stdout_path, stderr_path


def get_job_file_list(
            archive_path: Path,
            run_number: Optional[int] = None,
            all_runs: Optional[bool] = False
        ) -> list[Path]:
    """
    Generate a list of run job files for the specified run number, all runs,
    or the latest run.

    Filtering the files here, reduces the number of files to read and parse
    later on
    """
    payu_jobs = archive_path / "payu_jobs"
    if not payu_jobs.exists():
        return []

    if run_number is not None:
        return list(payu_jobs.glob(f"{run_number}/run/*.json"))

    if all_runs:
        return list(payu_jobs.glob("*/run/*.json"))

    # Latest run
    run_dirs = [
        d for d in payu_jobs.iterdir() if d.is_dir() and d.name.isdigit()
    ]
    if not run_dirs:
        return []
    latest_run = max(run_dirs, key=lambda d: int(d.name))
    return list(latest_run.glob("run/*.json"))


def build_job_info(
            archive_path: Path,
            control_path: Path,
            run_number: Optional[int] = None,
            all_runs: Optional[bool] = False
        ) -> Optional[dict[str, Any]]:
    """
    Generate a dictionary of jobs information (exit status, stage),
    and mapping stdout and stderr files.

    This reads files for the specified run number, all runs,
    or the latest run.

    # TODO: Extend with collate, sync when their job files are implemented
    """
    job_files = get_job_file_list(archive_path, run_number, all_runs)
    if not job_files:
        return {}

    status_data: dict[str, Any] = {}
    runs: dict[int, dict[str, list]] = {}

    for job_file in job_files:
        data = read_job_file(job_file)

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
            "start_time": data.get("timings", {}).get("payu_start_time"),
        }

        run_num = data["payu_current_run"]
        runs.setdefault(run_num, {"run": []})["run"].append(run_info)

    # Sort runs by run number
    status_data["runs"] = dict(
        sorted(runs.items(), key=lambda item: int(item[0]))
    )
    # Sort internal jobs by start time
    for run_num, run_jobs in status_data["runs"].items():
        run_jobs["run"].sort(key=lambda x: (
            # Put queued jobs at the end (None start_time)
            x.get("start_time") is None,
            # Sort by start time
            x.get("start_time") or ""
        ))

    if not all_runs:
        # Use latest run job
        for run_num, run_jobs in status_data["runs"].items():
            run_jobs["run"] = [run_jobs["run"][-1]]

    return status_data


def update_all_job_files(
            status_data: dict[str, Any],
            scheduler: Scheduler
        ) -> None:
    """
    Update job files in the queried job information.
    Removes queued jobs that have exited or been deleted before running.
    Updates the job file with the exit status if the job has exited.

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
        warnings.warn("Failed to get job information from the scheduler")
        return

    for jobs in status_data.get("runs", {}).values():
        for data in jobs["run"]:
            job_id = data.get("job_id")
            if job_id is None or job_id == "":
                # No job ID, nothing to update
                continue

            # Get the stage and job file from the file data
            stage = data["stage"]
            job_file = Path(data["job_file"])
            run_status = data.get("exit_status")

            # Get job status from the scheduler data
            job_status = all_jobs.get(job_id)
            exit_status = job_status.get("exit_status") if job_status else None

            if not job_status:
                # Job not found in scheduler
                if stage == "queued":
                    remove_job_file(file_path=job_file)
                elif run_status is None:
                    # Run status isn't set, so job must have exited earlier
                    update_job_file(
                        file_path=job_file,
                        data={"payu_run_status": 1}
                    )
            elif exit_status is not None:
                if stage == "queued":
                    remove_job_file(file_path=job_file)
                elif run_status is None:
                    update_job_file(
                        file_path=job_file,
                        data={
                            "payu_run_status": exit_status
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
        for run_info in jobs["run"]:
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
