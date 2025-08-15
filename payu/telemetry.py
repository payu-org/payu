"""
Module for generating and managing payu run job files, and sending
this data to telemetry services at the end of a run, if configured.
"""

import datetime
import json
import os
from pathlib import Path
import requests
import shutil
import tempfile
import threading
from typing import Any, Optional
import warnings

import cftime

from payu.metadata import Metadata
from payu.schedulers import Scheduler

# Environment variable for external telemetry configuration file
TELEMETRY_CONFIG = "PAYU_TELEMETRY_CONFIG"
TELEMETRY_CONFIG_VERSION = "1-0-0"

# Required telemetry configuration fields
CONFIG_FIELDS = {
    "URL": "telemetry_url",
    "TOKEN": "telemetry_token",
    "SERVICE_NAME": "telemetry_service_name",
    "HOST": "telemetry_host",
    "HOSTNAME": "hostname",
}

REQUEST_TIMEOUT = 10

TELEMETRY_VERSION = "1.0.0"


def get_metadata(metadata: Metadata) -> Optional[dict[str, Any]]:
    """Returns a dictionary of the experiment metadata to record"""
    metadata_dict = metadata.read_file()
    if len(metadata_dict) == 0:
        return {}

    return {
        "experiment_metadata": metadata_dict
    }


def get_manifests(experiment_manifests) -> Optional[dict[str, Any]]:
    """Returns a dictionary of content of input, restart and executable
    manifest data"""
    manifests = {}
    for mf in experiment_manifests.manifests:
        manifests[mf] = experiment_manifests.manifests[mf].data

    return {
        "manifests": manifests
    }


def get_timings(timings: dict[str, int]) -> dict[str, int]:
    """Returns a dictionary of the timings for the run.
    Adds end time and total duration of the experiment run so far.
    """
    start_time = timings["payu_start_time"]
    finish_time = datetime.datetime.now()
    # Convert start and end times to isoformat strings
    timings["payu_start_time"] = start_time.isoformat()
    timings["payu_finish_time"] = finish_time.isoformat()
    elapsed_time = finish_time - start_time
    timings["payu_total_duration_seconds"] = elapsed_time.total_seconds()
    return {
        "timings": timings
    }


def get_scheduler_run_info(scheduler: Scheduler) -> dict[str, Any]:
    """Returns a dictionary of the scheduler job information"""
    scheduler_job_id = scheduler.get_job_id(short=False)
    scheduler_info = scheduler.get_job_info()

    info = {}
    if scheduler_info is not None:
        info["scheduler_job_id"] = scheduler_job_id
        info["scheduler_job_info"] = scheduler_info
        info["scheduler_type"] = scheduler.name
    return info


def transform_model_datetimes(
            datetimes: dict[str, cftime.datetime]
        ) -> dict[str, str]:
    """Transforms model cftime datetimes to a dictionary with ISO-format
    strings so they are JSON serializable"""
    transformed = {}
    calendar = None
    for key, value in datetimes.items():
        if isinstance(value, cftime.datetime):
            # Convert cftime datetime to ISO format string
            transformed[key] = value.isoformat()
            calendar = str(value.calendar)
        else:
            warnings.warn(
                f"Expected cftime.datetime for model datetimes, "
                f"but got {type(value).__name__}"
            )
    if calendar:
        transformed["model_calendar"] = calendar
    return transformed


def get_external_telemetry_config() -> Optional[dict[str, Any]]:
    """Loads the external telemetry configuration file.
    If a valid file does not exist, return None
    """
    # Check path to telemetry config file exists
    config_dir = Path(os.environ[TELEMETRY_CONFIG])
    config_path = config_dir / f"{TELEMETRY_CONFIG_VERSION}.json"
    if not (config_path.exists() and config_path.is_file()):
        warnings.warn(
            f"No config file found at {TELEMETRY_CONFIG}: {config_path}. "
            "Skipping posting telemetry",
            UserWarning
        )
        return None

    # Attempt to read config file
    try:
        with open(config_path, 'r') as f:
            telemetry_config = json.load(f)
    except json.JSONDecodeError:
        warnings.warn(
            "Error parsing json in configuration file "
            f"at {TELEMETRY_CONFIG}: {config_path}. "
            "Skipping posting telemetry"
        )
        return None

    # Check for required fields in the telemetry configuration
    missing_fields = CONFIG_FIELDS.values() - telemetry_config.keys()
    if missing_fields:
        warnings.warn(
            f"Required field(s) {missing_fields} not found in configuration "
            f"file at {TELEMETRY_CONFIG}: {config_path}. "
            "Skipping posting telemetry"
        )
        return None

    return telemetry_config


def post_telemetry_data(url: str,
                        token: str,
                        data: dict[str, Any],
                        service_name: str,
                        host: str,
                        request_timeout: int = REQUEST_TIMEOUT,
                        ) -> None:
    """Posts telemetry data

    Parameters
    ----------
    url: str
        Endpoint for the telemetry
    token: str
        Header token for the telemetry request
    data: dict[str, Any]
        Data to be posted in the telemetry request
    service_name: str
        Service name for the telemetry record
    host: str
        Host for the telemetry record header
    request_timeout: int, default REQUEST_TIMEOUT
        Timeout while waiting for request
    """
    headers = {
        "Content-type": "application/json",
        "Authorization": "Token " + token,
        "HOST": host,
    }

    data = {
        "service": service_name,
        "version": TELEMETRY_VERSION,
        "telemetry": data
    }

    try:
        response = requests.post(
            url,
            data=json.dumps(data),
            headers=headers,
            timeout=request_timeout,
            verify=False
        )
        if response.status_code >= 400:
            warnings.warn(
                f"Error posting telemetry: Status {response.status_code} - "
                f"{response.json()}"
            )
    except Exception as e:
        warnings.warn(f"Error posting telemetry: {e}")


def record_telemetry(run_info: dict[str, Any],
                     config: dict[str, Any]) -> None:
    """If configured, post the telemetry data for the payu run"""
    # Check for config.yaml option to disable telemetry, and if an
    # environment variable for an external telemetry config file is set,
    # and whether the model was run
    if not (
        config.get("telemetry", {}).get("enable", True)
        and TELEMETRY_CONFIG in os.environ
        and "payu_model_run_status" in run_info
    ):
        return

    # Check for valid external telemetry configuration file
    external_config = get_external_telemetry_config()
    if external_config is None:
        # Skip any external telemetry
        return

    # Add hostname to the run info fields
    run_info["hostname"] = external_config[CONFIG_FIELDS["HOSTNAME"]]

    # Using threading to run the one post request in the background
    thread = threading.Thread(
        target=post_telemetry_data,
        kwargs={
            "url": external_config[CONFIG_FIELDS["URL"]],
            "token": external_config[CONFIG_FIELDS["TOKEN"]],
            "data": run_info,
            "service_name": external_config[CONFIG_FIELDS["SERVICE_NAME"]],
            "host": external_config[CONFIG_FIELDS["HOST"]],
        },
    )
    thread.start()


def atomic_write_file(
            file_path: Path,
            data: dict[str, Any],
        ) -> None:
    """Write the job information to a temporary file and
    replace the existing if it exists so the update is atomic"""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode='w', dir=file_path.parent, delete=False
    ) as temp_file:
        json.dump(data, temp_file, ensure_ascii=False, indent=4)
        temp_name = temp_file.name
    os.replace(temp_name, file_path)


def get_job_file_path_with_id(
            archive_path: Path,
            run_number: int,
            job_id: str,
            type: str = "run",
        ) -> Path:
    """Return the path to the run job file given the archive path
    following the format:
    <archive_path>/payu_jobs/<run_number>/<type>/<job_id>.json
    """
    return (
        archive_path / "payu_jobs" / str(run_number) / type / f"{job_id}.json"
    )


def get_job_file_path(
            archive_path: Path,
            run_number: int,
            timings: dict[str, Any],
            scheduler: Scheduler,
            type: str = "run",
        ) -> Path:
    """Return the path to the run job file given the archive path"""
    scheduler_job_id = scheduler.get_job_id(short=False)
    if scheduler_job_id is None or scheduler_job_id == "":
        # Job may be running locally, so use the start time as file ID
        file_id = timings["payu_start_time"].strftime("%Y%m%d%H%M%S")
    else:
        # Use the scheduler job ID as file ID
        file_id = scheduler_job_id

    file_path = get_job_file_path_with_id(
        archive_path=archive_path,
        run_number=run_number,
        job_id=file_id,
        type='run'
    )
    return file_path


def read_job_file(file_path: Path) -> dict[str, Any]:
    """Read the json file and return it's contents"""
    if not file_path.exists():
        return {}
    with open(file_path, 'r') as f:
        return json.load(f)


def write_queued_job_file(
            archive_path: Path,
            job_id: str,
            type: str,
            scheduler: Scheduler,
            metadata: Metadata,
            current_run: int
        ) -> None:
    """Initialise the queued job file in the control path with the job ID

    Parameters
    ----------
    archive_path: Path
        Path to the archive directory for the experiment
    job_id: str
        Job ID of the queued job
    type: str
        Type of the job, e.g. 'run'
    scheduler: Scheduler
        Type of the scheduler used for the job, e.g. 'pbs', 'slurm'
    metadata: Metadata
        Metadata object for the run - used to get uuid if it exists
    current_run: int
        Current run number for the queued job
    """
    job_file_path = get_job_file_path_with_id(
        archive_path,
        run_number=current_run,
        job_id=job_id,
        type=type
    )
    data = {
        "scheduler_job_id": job_id,
        "scheduler_type": scheduler.name,
        "stage": "queued",
        "payu_current_run": current_run,
    }
    data.update(get_metadata(metadata))
    atomic_write_file(file_path=job_file_path, data=data)


def remove_job_file(file_path: Path) -> None:
    """Remove the queued job file in the control path if it exists
    and <run_number>/<type> directory if is empty
    """
    if not file_path.exists():
        return

    file_path.unlink()
    # File format is <run_number>/run/<job_id>.json
    # So should remove <run_number>/run/ if empty
    if not any(file_path.parent.iterdir()):
        file_path.parent.rmdir()
        if not any(file_path.parent.parent.iterdir()):
            file_path.parent.parent.rmdir()


def setup_run_job_file(
            file_path: Optional[Path],
            scheduler: Scheduler,
            metadata: Metadata,
            extra_info: Optional[dict[str, Any]] = None
        ) -> None:
    """
    Add setup information to the run job file

    Parameters
    ----------
    file_path: Path
        Path to the run job file in the archive directory
    current_run: int
        Current run number for the queued job
    timings: dict[str, Any]
        Timings for the run
    scheduler: Scheduler
        Scheduler object for the run - used to get job ID
    metadata: Metadata
        Metadata object for the run - used to get experiment metadata
    extra_info: Optional[dict[str, Any]], default None
        Any raw information to add directly to the run job file
    """
    if file_path is None:
        # This might be payu setup being run on it's own,
        # so skip setting up the run job file
        return

    # Get the job ID from the scheduler
    scheduler_job_id = scheduler.get_job_id(short=False)
    scheduler_type = scheduler.name

    # Build the data to write to the file
    data = {
        "scheduler_job_id": scheduler_job_id,
        "scheduler_type": scheduler_type,
        "stage": "setup"
    }
    # Add metadata
    data.update(get_metadata(metadata))

    # Add extra information if provided
    data.update(extra_info or {})

    # Write the file
    atomic_write_file(file_path=file_path, data=data)


def update_job_file(
            file_path: Path,
            data: dict[str, Any],
        ) -> dict[str, Any]:
    """
    Update the job file with the provided data
    and return the updated data
    """
    run_info = read_job_file(file_path)
    run_info.update(data)
    atomic_write_file(file_path=file_path, data=run_info)
    return run_info


def update_run_job_file(
            file_path: Path,
            stage: Optional[str] = None,
            extra_info: Optional[dict[str, Any]] = None,
            manifests: Optional[dict[str, Any]] = None,
            model_restart_datetimes: Optional[dict[str, Any]] = None
        ) -> None:
    """Update the payu-run job file with the current stage and any extra info
    if defined

    Parameters
    ----------
    file_path: Path
        Path to the run job file to update
    stage: Optional[str], default None
        Stage of the run to update in the job file
    extra_info: Optional[dict[str, Any]], default None
        Any raw information to add directly to the run job file
    manifests: Optional[dict[str, Any]], default None
        Add manifests to the run job file
    model_restart_datetimes: Optional[dict[str, Any]], default None
        Model restart datetimes to add to the run job file
    """
    run_info = {}
    if stage:
        run_info["stage"] = stage
    if manifests:
        run_info.update(get_manifests(manifests))
    if model_restart_datetimes:
        run_info.update(transform_model_datetimes(model_restart_datetimes))
    if extra_info:
        run_info.update(extra_info)

    update_job_file(file_path=file_path, data=run_info)


def record_run(
            timings: dict[str, Any],
            scheduler: Scheduler,
            run_status: int,
            config: dict[str, Any],
            file_path: Path,
        ) -> None:
    """Record the run information for the current run and post telemetry
    if enabled

    Parameters
    ----------
    timings: dict[str, Any]
        Timings for the run includes timing of functions, user-scripts
        and model run
    scheduler: Scheduler
        Scheduler object for the run - used to query recent job information
    run_status: int
        Status of the payu run as a whole, 0 for success, 1 for failure
    config: dict[str, Any]
        Configuration (config.yaml) - used to check if telemetry is enabled
    file_path: Path
        Path to the run job file to update
    """
    # Additional information to the run info
    run_info = {"payu_run_status": run_status, "stage": "completed"}

    # Query the scheduler just before recording the run information to
    # try get the most up-to-date information of the usage statistics
    # as they only get updated periodically
    run_info.update(get_scheduler_run_info(scheduler))

    # Add timings to the run info and add end time and total run duration
    run_info.update(get_timings(timings))

    # Update the run job file
    run_info = update_job_file(file_path=file_path, data=run_info)

    record_telemetry(run_info=run_info, config=config)
