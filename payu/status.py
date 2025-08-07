"""
Methods used by the `payu status` command to display the status of
payu runs by inspecting the job files generated for telemetry,
scheduler stdout/stderr logs, and querying the scheduler
"""

import glob
import json
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


def find_scheduler_log_path(
            pattern: str,
            control_path: Path,
            archive_path: Path,
        ) -> Path:
    """Given a glob pattern, find the scheduler log file either in
    the control path or in the archive path"""
    # First search the control path
    filename = glob.glob(str(control_path / pattern))
    if len(filename) == 1:
        return Path(filename[0])
    # Search the pbs-logs directory in the archive path
    filename = glob.glob(str(archive_path / 'pbs_logs' / pattern))
    if len(filename) == 1:
        return Path(filename[0])
    # If not found, return None
    return None


def find_scheduler_logs(
            job_id: str,
            control_path: Path,
            archive_path: Path,
            type: str = 'pbs',
        ) -> tuple[Optional[Path], Optional[Path]]:
    """Find the stdout and stderr log files for the scheduler job ID"""
    #TODO: Support non-default stderr and stdout file names
    if type == 'pbs':
        # For PBS, the log files are named .o<jobid> and .e<jobid>
        job_id = job_id.split('.')[0]  # Remove any suffix
        stdout_pattern = f"*.o{job_id}"
        stderr_pattern = f"*.e{job_id}"
    elif type == 'slurm':
        # For Slurm, the default log files are named slurm-<jobid>.out
        stdout_pattern = f"slurm-{job_id}.out"
        stderr_pattern = f"slurm-{job_id}.err"
    else:
        return None, None # Unknown scheduler type

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
            all: Optional[bool] = False
        ) -> list[Path]:
    """
    Generate a list of run job files to query for job information.
    By default, this will return the latest run job file
    that is either in the control, work or latest archive output directory.
    Otherwise it returns any queued or running jobs,
    and either:
     - all completed jobs in archive if `all` is True,
     - completed job in the selected output if `run_number` is specified

    Filtering the files here, reduces the number of files to read and parse
    later on
    """
    search_paths = [control_path, work_path]
    outputs = list_archive_dirs(archive_path=archive_path,
                                dir_type='output')
    if not outputs:
        # If no output directories, return the run job file only
        pass
    elif run_number is not None and f'output{run_number:03}' in outputs:
        search_paths.append(archive_path / f'output{run_number:03}')
    elif all:
        search_paths.extend([archive_path / output for output in outputs])
    else:
        # Only find the latest payu run job file
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
            all: Optional[bool] = False
        ) -> Optional[dict[str, Any]]:
    """
    Generate a dictionary of jobs information (exit status, stage), 
    and mapping stdout and stderr files.

    By default, this uses the latest run job file - e.g.
    any that is queued or running, or the latest archived output

    If `run_number` is specified, it will return the jobs for that run number
    If `all` is True, it will include all jobs in the archive
    for every run number

    # TODO: Extend with collate, sync when their job files are implemented
    """
    job_files = get_job_file_list(
        control_path=control_path,
        work_path=work_path,
        archive_path=archive_path,
        run_number=run_number,
        all=all
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

        if 'experiment_uuid' in data.get('experiment_metadata', {}):
            uuid = data['experiment_metadata']['experiment_uuid']
            status_data['experiment_uuid'] = uuid

        stdout, stderr = find_scheduler_logs(
            job_id=data.get('scheduler_job_id'),
            control_path=control_path,
            archive_path=archive_path,
            type=data.get('scheduler_type')
        )
        run_info = {
            'job_id': data.get('scheduler_job_id'),
            'stage': data.get('stage'),
            'exit_status': data.get('payu_run_status'),
            'model_exit_status': data.get('payu_model_run_status'),
            'stdout_file': str(stdout) if stdout else None,
            'stderr_file': str(stderr) if stderr else None,
            'job_file': str(job_file),
        }
        if 'runs' not in status_data:
            status_data['runs'] = {}
        status_data['runs'][data['payu_current_run']] = {'run': run_info}

    # Ensure runs are sorted by run number
    if 'runs' in status_data:
        # Sort runs by run number (key)
        sorted_runs = dict(sorted(
            status_data['runs'].items(),
            key=lambda item: int(item[0])
        ))
        status_data['runs'] = sorted_runs

    return status_data


def update_all_job_files(
            data: dict[str, Any],
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
    this method only queiries the scheduler once for all jobs

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

    for run_number, jobs in data.get('runs', {}).items():
        data = jobs['run']

        job_id = data.get('job_id')
        if job_id is None or job_id == '':
            # No job ID, nothing to update
            continue
        elif job_id not in all_jobs:
            # If the job is not in the scheduler's job list, it has
            # exited or deleted
            if data['stage'] == 'queued':
                remove_job_file(file_path=Path(data['job_file']))
            elif data['stage'] != 'completed':
                # Job has exited before payu has completed
                update_job_file(
                    file_path=Path(data['job_file']),
                    data={
                        'stage': 'completed',
                        'payu_run_status': 1
                    }
                )
        elif all_jobs[job_id].get('exit_status', None) is not None:
            if data['stage'] == 'queued':
                # Job may have exited on startup, remove the queued file
                remove_job_file(file_path=Path(data['job_file']))
            elif data['stage'] != 'completed':
                # Update the job file with the exit status
                update_job_file(
                    file_path=Path(data['job_file']),
                    data={
                        'stage': 'completed',
                        'payu_run_status': all_jobs[job_id]['exit_status']
                    }
                )


def display_job_info(data: dict[str, Any]) -> None:
    """
    Display the job information in a human-readable format

    TODO: Make this more readable?? As the --json option is currently
    better.. Otherwise just remove this function and always use --json option
    as the default
    """
    for run_number, jobs in data.get('runs', {}).items():
        run_info = jobs['run']
        print(f"Run {run_number}:")
        if run_info['job_id'] != None and run_info['job_id'] != '':
            print(f" Job ID: {run_info['job_id'] }")
        if run_info['stage'] == 'completed':
            exit_status = (
                "Run completed successfully"
                if run_info['exit_status'] == 0
                else "Run failed"
            )
            print(f" {exit_status}")
        else:
            print(f" Stage: {run_info['stage']}")
        if run_info["model_exit_status"] != None:
            print(
                f" Model run command exited with code: "
                f"{run_info['model_exit_status']}"
            )
        if run_info["stdout_file"] != None:
            print(f" STDOUT File: {run_info['stdout_file']}")
        if run_info["stderr_file"] != None:
            print(f" STDERR File: {run_info['stderr_file']}")
        if run_info["job_file"] != None:
            print(f" Job File: {run_info['job_file']}")