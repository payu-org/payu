import datetime
import glob
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
from payu.fsops import list_archive_dirs

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
        'experiment_metadata': metadata_dict
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
    start_time = timings['payu_start_time']
    finish_time = datetime.datetime.now(datetime.timezone.utc)
    # Convert start and end times to isoformat strings
    timings['payu_start_time'] = start_time.isoformat()
    timings['payu_finish_time'] = finish_time.isoformat()
    elapsed_time = finish_time - start_time
    timings['payu_total_duration_seconds'] = elapsed_time.total_seconds()
    return {
        'timings': timings
    }


def get_scheduler_run_info(scheduler: Scheduler) -> dict[str, Any]:
    """Returns a dictionary of the scheduler job information"""
    scheduler_job_id = scheduler.get_job_id(short=False)
    scheduler_info = scheduler.get_job_info()

    info = {}
    if scheduler_info is not None:
        info['scheduler_job_info'] = scheduler_info
        info['scheduler_type'] = scheduler.name
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
        transformed['model_calendar'] = calendar
    return transformed


def get_external_telemetry_config() -> Optional[dict[str, Any]]:
    """Loads the external telemetry configuration file.
    If a valid file does not exist, return None"""
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
        'Content-type': 'application/json',
        'Authorization': 'Token ' + token,
        'HOST': host,
    }

    data = {
        "service": service_name,
        "version": TELEMETRY_VERSION,
        "date": datetime.date.today().isoformat(),
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
    # environment variable for an external telemetry config file is set
    telemetry_enabled = (
        config.get('telemetry', {}).get('enable', True)
        and TELEMETRY_CONFIG in os.environ
    )
    if not telemetry_enabled:
        return

    # Skip telemetry if model was not run
    if 'payu_model_run_status' not in run_info:
        return

    # Check for valid external telemetry configuration file
    external_config = get_external_telemetry_config()
    if external_config is None:
        # Skip any external telemetry
        return

    # Add hostname to the run info fields
    run_info['hostname'] = external_config[CONFIG_FIELDS['HOSTNAME']]

    # Using threading to run the one post request in the background
    thread = threading.Thread(
        target=post_telemetry_data,
        kwargs={
            'url': external_config[CONFIG_FIELDS['URL']],
            'token': external_config[CONFIG_FIELDS['TOKEN']],
            'data': run_info,
            'service_name': external_config[CONFIG_FIELDS['SERVICE_NAME']],
            'host': external_config[CONFIG_FIELDS['HOST']],
        },
    )
    thread.start()


def find_run_job_file(paths: list[Path]) -> Optional[Path]:
    """Find the run job file in the specified paths.
    This file path will be different depending if there are model errors,
    whether archive runs or not, or if payu
    exits during initialisation"""
    for path in paths:
        run_file = get_job_file_path(path)
        if run_file.exists() and run_file.is_file():
            return run_file
    return None


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


def get_job_file_path(base_path: Path, type: str = 'payu-run') -> Path:
    """Return the path to the run job file given the base path"""
    return base_path / 'payu-jobs' / f'{type}.json'


def read_job_file(file_path: Path) -> dict[str, Any]:
    """Read the json file and return it's contents"""
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(f"Job file not found: {file_path}")
    with open(file_path, 'r') as f:
        return json.load(f)


def write_queued_job_file(
            control_path: Path,
            job_id: str,
            type: str,
            scheduler_type: str
        ) -> None:
    """Initialise the queued job file in the control path with the job ID

    Parameters
    ----------
    control_path: Path
        Path to the control directory for the run
    job_id: str
        Job ID of the queued job
    type: str
        Type of the job, e.g. 'payu-run'
    scheduler_type: str
        Type of the scheduler used for the job, e.g. 'pbs', 'slurm'
    """
    job_file_path = get_job_file_path(control_path, type)
    data = {
        'scheduler_job_id': job_id,
        'scheduler_type': scheduler_type,
        'stage': 'queued'
    }
    atomic_write_file(
        file_path=job_file_path,
        data=data
    )


def setup_run_job_file(
            control_path: Path,
            work_path: Path,
            scheduler: Scheduler,
            metadata: Metadata,
            extra_info: Optional[dict[str, Any]] = None
        ) -> None:
    """Setup the job file for the running payu-run job in the work directory.
    Remove any existing queued payu-run job file if it exists in the
    control directory.

    Parameters
    ----------
    control_path: Path
        Path to the control directory for the run
    work_path: Path
        Path to the work directory for the run
    scheduler: Scheduler
        Scheduler object for the run - used to get job ID
    metadata: Metadata
        Metadata object for the run - used to get experiment metadata
    extra_info: Optional[dict[str, Any]], default None
        Any raw information to add directly to the run job file
    """
    # Get the job ID from the scheduler
    scheduler_job_id = scheduler.get_job_id(short=False)

    # Check if there's an existing queued job file (there might not be one if
    # running payu-run directly on login node)
    queued_job_file_path = get_job_file_path(base_path=control_path)
    if queued_job_file_path.exists():
        # If it exists, read the file
        queued_job_data = read_job_file(queued_job_file_path)

        # Check job ID matches
        queued_id = queued_job_data.get('scheduler_job_id')
        if queued_id != scheduler_job_id:
            # Should it raise an error or just warn?
            raise RuntimeError(
                f"Job ID in queued payu run file does not "
                f"match the current scheduler job ID: "
                f"{queued_id} != {scheduler_job_id}.\n"
                "This could indicate multiple payu runs in parallel"
            )

    # Build the data to write to the file
    data = {
        'scheduler_job_id': scheduler_job_id,
        'stage': 'setup'
    }
    # Add metadata
    data.update(get_metadata(metadata))

    # Add extra information if provided
    data.update(extra_info or {})

    # Write the file to the work directory
    atomic_write_file(
        filepath=get_job_file_path(base_path=work_path),
        data=data
    )

    # Remove the queued job file if it exists
    if queued_job_file_path.exists():
        queued_job_file_path.unlink()
    if not any(queued_job_file_path.parent.iterdir()):
        queued_job_file_path.parent.rmdir()


def update_run_job_file(
            base_path: Path,
            stage: Optional[str] = None,
            extra_info: Optional[dict[str, Any]] = None,
            manifests: Optional[dict[str, Any]] = None,
            model_restart_datetimes: Optional[dict[str, Any]] = None
        ) -> None:
    """Update the payu-run job file with the current stage and any extra info
    if defined

    Parameters
    ----------
    base_path: Path
        Base path where the run job file is located (e.g. work or output path)
    stage: Optional[str], default None
        Stage of the run to update in the job file
    extra_info: Optional[dict[str, Any]], default None
        Any raw information to add directly to the run job file
    manifests: Optional[dict[str, Any]], default None
        Add manifests to the run job file
    model_restart_datetimes: Optional[dict[str, Any]], default None
        Model restart datetimes to add to the run job file
    """
    # Read existing run info
    job_file_path = get_job_file_path(base_path=base_path)
    run_info = read_job_file(job_file_path)

    # Update the stage and any extra info if provided
    if stage:
        run_info['stage'] = stage
    if manifests:
        run_info.update(get_manifests(manifests))
    if model_restart_datetimes:
        run_info.update(transform_model_datetimes(model_restart_datetimes))
    if extra_info:
        run_info.update(extra_info)

    # Write back to the file
    atomic_write_file(
        filepath=job_file_path,
        data=run_info
    )


def record_run(
            timings: dict[str, Any],
            scheduler: Scheduler,
            run_status: int,
            config: dict[str, Any],
            archive_path: Path,
            control_path: Path,
            work_path: Path,
            output_path: Path,
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
    archive_path: Path
        Path to the archive directory for the run
    control_path: Path
        Path to the control directory for the run
    work_path: Path
        Path to the work directory for the run
    output_path: Path
        Path to the output directory for the run
    """
    # Find the pre-existing run job file - this path will be different
    # depending if there are model errors, whether archive runs or not, or
    # if payu exits during initialisation
    run_job_file = find_run_job_file([output_path, work_path, control_path])
    if run_job_file is None:
        # No job file found, skip telemetry
        return
    # Read the existing run job file
    run_info = read_job_file(run_job_file)

    # Add timings to the run info and add end time and total run duration
    run_info.update(get_timings(timings))

    # Add run status
    run_info['payu_run_status'] = run_status
    run_info['stage'] = 'completed'

    # Query the scheduler just before recording the run information to
    # try get the most up-to-date information of the usage statistics
    # as they only get updated periodically
    run_info.update(get_scheduler_run_info(scheduler))

    # Write run job information to a JSON file
    atomic_write_file(
        filepath=run_job_file,
        data=run_info
    )

    # If model exited with errors, copy the updated run job file to the
    # error logs directory
    if ('payu_model_run_status' in run_info
            and run_info['payu_model_run_status'] != 0):
        error_logs_path = Path(archive_path) / 'error-logs'
        error_logs_path.mkdir(parents=True, exist_ok=True)
        job_id = run_info.get('scheduler_job_id')
        if job_id != '' and job_id is not None:
            job_id = job_id.split('.')[0]  # Remove any suffix
            error_filename = f"{run_job_file.stem}.{job_id}.json"
        else:
            error_filename = run_job_file.name

        shutil.copy(run_job_file, error_logs_path / error_filename)

    record_telemetry(
        run_info=run_info,
        config=config
    )