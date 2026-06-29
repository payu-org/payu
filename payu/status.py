"""
Methods used by the `payu status` command to display the status of
payu runs by inspecting the job files generated for telemetry,
scheduler stdout/stderr logs, and querying the scheduler
"""
from pathlib import Path
from typing import Any, Optional
import warnings
from datetime import datetime
import json
import logging
from itertools import zip_longest

from payu.schedulers import Scheduler
from payu.telemetry import (
    read_job_file,
    update_job_file,
    remove_job_file
)
from payu.sync import SyncToRemoteArchive

logger = logging.getLogger(__name__)

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
            all_runs: Optional[bool] = False,
            type: str = "run"
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
        return list(payu_jobs.glob(f"{run_number}/{type}/*.json"))

    if all_runs:
        return list(payu_jobs.glob(f"*/{type}/*.json"))

    # Latest run
    run_dirs = [
        d for d in payu_jobs.iterdir() if d.is_dir() and d.name.isdigit()
    ]
    if not run_dirs:
        return []
    latest_run = max(run_dirs, key=lambda d: int(d.name))
    return list(latest_run.glob(f"{type}/*.json"))

def display_wait_time(qtime, stime) -> Optional[str]:
    """Calculate the difference between the submit queue time and the start time/current time (if job is in queue)"""
    if qtime is None and stime is None:
        return None
    elif stime is None:
        start_time = datetime.now()
        label = "Current Queue Time"
    else:
        start_time = datetime.strptime(stime, "%a %b %d %H:%M:%S %Y")
        label = "Total Queue Time"

    submit_time = datetime.strptime(qtime, "%a %b %d %H:%M:%S %Y")
    wait_time = (start_time - submit_time).total_seconds()

    # Convert the queue time to a human-readable format
    wait_hr, rem = divmod(int(wait_time), 3600)
    wait_min, wait_sec = divmod(rem, 60)
    wait_time_str = f"{wait_hr}h {wait_min}m {wait_sec}s"
    
    if wait_time_str is not None:
        print(f"  {f'{label}:':<{18}} {wait_time_str}")
    return wait_time_str

def _sort_run_jobs(run_info_one_type):
    """Sort the run_info by job_id and start_time, if job_id is not available"""
    run_info_one_type.sort(key=lambda x: (
        # Sort by increasing job_id, and put these at the end
        x.get("job_id") or "",

        # Sort by increasing start time if no job_id (e.g., payu-run in login node)
        x.get("start_time") or "",
    ))


def build_job_info(
            archive_path: Path,
            control_path: Path,
            run_number: Optional[int] = None,
            all_runs: Optional[bool] = False,
            expt=None
        ) -> Optional[dict[str, Any]]:
    """
    Generate a dictionary of jobs information (exit status, stage),
    and mapping stdout and stderr files.

    This reads files for the specified run number, all runs,
    or the latest run.

    Expected output format:
    {
        "experiment_uuid": "uuid-string",
        "runs": {
            "3(run_number)": {
                "run": [
                    {...} //previous run jobs
                    {"job_id": "12345", ...}
                ],
                "collate": [
                    {...} //previous collate jobs
                    {"job_id": "12346", ...}
                ]
            }
        }
    }
    """
    status_data: dict[str, Any] = {}
    runs: dict[int, dict[str, list]] = {}
    for job_type in ["run", "collate"]:
        job_files = get_job_file_list(archive_path, run_number, all_runs, type=job_type)
        # If no job files found for this type, skip to the next type
        if not job_files:
            continue

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
                "exit_status": data.get(f"payu_{job_type}_status"),
                "stdout_file": str(stdout) if stdout else None,
                "stderr_file": str(stderr) if stderr else None,
                "job_file": str(job_file),
                "start_time": data.get("timings", {}).get("payu_start_time"),
            }

            if job_type == "run":
                run_info.update({
                    "run_id": data.get("payu_run_id"),
                    "model_exit_status": data.get("payu_model_run_status"),
                    "model_finish_time": data.get("model_finish_time")
                })

            run_num = int(data["payu_current_run"])
            runs.setdefault(run_num, {})
            runs[run_num].setdefault(job_type, []).append(run_info)

    # If no job file found for any type, return {}
    if not runs:
        return {}

    # Sort runs by run number
    status_data["runs"] = dict(
        sorted(runs.items(), key=lambda item: int(item[0]))
    )
    # Sort internal jobs by start time
    for run_num, run_jobs in status_data["runs"].items():
        for job_type in run_jobs.keys():
            _sort_run_jobs(run_jobs[job_type])

            if not all_runs:
                # Use latest run/collate job
                run_jobs[job_type] = [run_jobs[job_type][-1]]

    # Get the current model time for run jobs
    latest_run_num = max(status_data["runs"].keys())
    latest_run_info = status_data["runs"][latest_run_num]["run"][-1]
    if latest_run_info.get("stage") == "model-run":
        try:
            cur_expt_time = expt.get_model_cur_expt_time()
            if cur_expt_time is not None:
                latest_run_info["cur_expt_time"] = cur_expt_time.isoformat()
            else:
                logger.debug("Cannot parse current experiment time: expected cftime.datetime but got None.")
        except (FileNotFoundError, IndexError, OSError, json.JSONDecodeError, ValueError, NotImplementedError) as e:
            logger.debug(f"Cannot parse current experiment time: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error while parsing current experiment time: {e}")

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

    TODO: Parse the stdout files to get the exit status - this will
    require specific scheduler methods.
    """
    # Get all jobs status and exit codes from the scheduler
    all_jobs = scheduler.get_all_job_info()
    if all_jobs is None:
        warnings.warn("Failed to get job information from the scheduler")
        return

    # Flatten the dict of status_data to get each job types and each data
    all_type_and_data = (
        (job_type, data)
        for jobs in status_data.get("runs", {}).values()
        for job_type, data_list in jobs.items()
        for data in data_list
    )

    for job_type, data in all_type_and_data:
        job_id = data.get("job_id")
        if job_id is None or job_id == "":
            # No job ID, nothing to update
            continue

        # Get the stage and job file from the file data
        stage = data["stage"]
        job_file = Path(data["job_file"])
        run_status = data.get("exit_status")

        # Get job info from the scheduler data
        job_info = all_jobs.get(job_id)
        if job_info:
            job_info_dict = job_info.get("Jobs", {}).get(job_id, {})
            exit_status = job_info_dict.get("Exit_status")
            job_state = job_info_dict.get("job_state")
        else:
            exit_status = None
            job_state = None

        if exit_status and stage == "queued":
            # Job has exited, but is still marked as queued in the job file
            remove_job_file(file_path=job_file)

        elif job_state == "F" and stage == "queued":
            # Job is killed or deleted but still exists in the job file
            remove_job_file(file_path=job_file)

        elif job_info:
            # Job is found in the scheduler, update the job file with the latest info
            update_data={
                    "scheduler_job_info": job_info
                }

            if exit_status is not None and run_status is None:
                # Update the job file with the exit status if it has exited
                update_data[f"payu_{job_type}_status"] = exit_status

            update_job_file(
                file_path=job_file,
                data=update_data
            )
                
        else:
            # Job not found in scheduler
            if stage == "queued":
                remove_job_file(file_path=job_file)

            elif run_status is None:
                # Run status isn't set, so job must have exited earlier
                update_job_file(
                    file_path=job_file,
                    data={f"payu_{job_type}_status": 1}
                )
            
def print_line(label: str, key: Any, data: dict[str, Any], is_status: bool = False, description: str = "") -> None:
    """Print a line with label and value from the data, if it is defined. 
    If is_status is True, print the status string (Success/Failed) as well."""
    value = data.get(key)
    label_width = 18
    if value is not None and value != "":
        if is_status:
            status_str = "Success" if value == 0 else "Failed"
            print(f"  {f'{label}:':<{label_width}} {value} ({status_str})")
        elif description:
            print(f"  {f'{label}:':<{label_width}} {value}\n  {'':>{label_width}}  ({description})")
        else:
            print(f"  {f'{label}:':<{label_width}} {value}")


def display_log_job_files(run_info: dict[str, Any]) -> None:
    """Display the log and job files block inside the payu status output"""
    print_line("Output Log", "stdout_file", run_info)
    print_line("Error Log", "stderr_file", run_info)
    print_line("Job File", "job_file", run_info)
   

def display_job_info(data: dict[str, Any]) -> None:
    """
    Display the job information in a human-readable way
    """
    line_width = 40
    runs = data.get("runs", {})
    if not runs:
        print("No run information available.")
        return

    for run_number, jobs in runs.items():
        print("=" * line_width)
        print(f"Run: {run_number}")

        # Loop through the job types (run and collate) for the current run
        for job_type, job_list in jobs.items():
            # Display internal job(s) for each type
            for job_info in job_list:
                print(f"  {'-' * 13} {job_type.capitalize()} Info {'-' * 13}")
                print_line("Job ID", "job_id", job_info)
                print_line("Run ID", "run_id", job_info)
                print_line("Stage", "stage", job_info)

                # Read out qtime and stime from the job file and display queue time
                job_file = job_info.get("job_file")
                job_id = job_info.get("job_id")
                all_job_info = read_job_file(Path(job_file))
                qt_info = all_job_info.get("scheduler_job_info", {}).get("Jobs", {}).get(job_id, {})
                display_wait_time(qt_info.get("qtime", None), qt_info.get("stime", None))

                if job_type == "run":
                    print_line("Current Expt Time", "cur_expt_time", job_info)
                    print_line("Model Finish Time", "model_finish_time", job_info)
                    print_line("Model Exit Code", "model_exit_status", job_info, is_status=True)
                
                # Display exit status, run log and job file paths
                print_line("Exit Status", "exit_status", job_info, is_status=True)
                display_log_job_files(job_info)

    print("=" * line_width)


def collect_expt_paths(expt):
    """Find the experiment paths (control, lab, work, archive, sync) and return them in a dictionary"""
    expt_paths = {}
    try:
        expt_paths = {
            "experiment_uuid": expt.metadata.uuid,
            "experiment_name": expt.name,
            "control_path": expt.control_path,
            "lab_path": expt.lab.basepath,
            "work_path": expt.work_path,
            "archive_path": expt.archive_path
        }

        try:
            syncer = SyncToRemoteArchive(expt)
            syncer.set_destination_path(verbose=False)
            sync_path = syncer.destination_path
            expt_paths["sync_path"] = str(sync_path)
        except ValueError:
            expt_paths["sync_path"] = "Unconfigured"

    except Exception as e:
        warnings.warn(f"Failed to collect experiment paths: {e}")
    return expt_paths

def display_expt_paths(expt_paths):
    """Display the experiment paths in a human-readable way"""
    if not expt_paths:
        print("No experiment paths available.")
        return

    line_width = 40
    print("=" * line_width)
    print("Experiment Paths:")
    print_line("Experiment UUID", "experiment_uuid", expt_paths)
    print_line("Experiment Name", "experiment_name", expt_paths)
    print_line("Control Directory", "control_path", expt_paths, description = "Where model configuration is stored")
    print_line("Laboratory Path", "lab_path", expt_paths, description = "Where model's laboratory is stored")
    print_line("Work Directory", "work_path", expt_paths, description = "Temporary directory for experiment runs")
    print_line("Archive Directory", "archive_path", expt_paths, description = "Where all experiment outputs are stored")
    print_line("Sync Destination", "sync_path", expt_paths, description = "Remote directory to sync outputs to")
    print("=" * line_width)