import datetime
import json
import os
from pathlib import Path
import requests
import threading
from typing import Any, Dict, Optional
import warnings

import payu
from payu.metadata import Metadata
from payu.schedulers import Scheduler

# Environment variable for external telemetry configuration file
TELEMETRY_CONFIG = "PAYU_TELEMETRY_CONFIG"
TELEMETRY_CONFIG_VERSION = "1-0-0"

# Required telemetry configuration fields
CONFIG_FIELDS = {
    "URL" : "telemetry_url",
    "TOKEN" : "telemetry_token",
    "SERVICE_NAME": "telemetry_service_name",
    "HOST": "telemetry_host",
    "HOSTNAME": "hostname",
}

REQUEST_TIMEOUT = 10

TELEMETRY_VERSION = "1.0.0"


def get_metadata(metadata: Metadata) -> Optional[Dict[str, Any]]:
    """Returns a dictionary of the experiment metadata to record"""
    metadata_dict = metadata.read_file()
    if len(metadata_dict) == 0:
        return {}

    return {
        'experiment_metadata': metadata_dict
    }


def get_manifests(experiment_manifests) -> Optional[Dict[str, Any]]:
    """Returns a dictionary of content of input, restart and executable
    manifest data"""
    manifests = {}
    for mf in experiment_manifests.manifests:
        manifests[mf] = experiment_manifests.manifests[mf].data

    return {
        "manifests": manifests
    }


def get_timings(timings: Dict[str, int]) -> Dict[str, int]:
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


def get_scheduler_run_info(scheduler: Scheduler) -> Dict[str, Any]:
    """Returns a dictionary of the scheduler job information"""
    scheduler_job_id = scheduler.get_job_id(short=False)
    scheduler_info = scheduler.get_job_info()

    info = {}
    if scheduler_info is not None:
        info['scheduler_job_info'] = scheduler_info
        info['scheduler_type'] = scheduler.name
    return info


def get_external_telemetry_config() -> Optional[Dict[str, Any]]:
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
            f"Required field(s) {missing_fields} not found in configuration file "
            f"at {TELEMETRY_CONFIG}: {config_path}. "
            "Skipping posting telemetry"
        )
        return None

    return telemetry_config


def post_telemetry_data(url: str,
                        token: Dict[str, Any],
                        data: Dict[str, Any],
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
    data: Dict[str, Any]
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

class Telemetry():
    """Telemetry class to store and post telemetry information.
    Currently these class methods are accessed during an Experiment run -
    so in payu.Experiment class and in the payu run subcommand.
    """

    def __init__(self, config):

        self.run_info = {}
        self.run_info_filepath = None

        # Check for config.yaml option to disable telemetry, and if an
        # environment variable for an external telemetry config file is set
        self.telemetry_enabled = (
            config.get('telemetry', {}).get('enable', True)
            and TELEMETRY_CONFIG in os.environ
        )

    def set_run_info_filepath(self, filepath: Path):
        """This file path will be different depending depending if there
        are model errors, whether archive runs or not. This is updated
        in different stages the Experiment class"""
        self.run_info_filepath = filepath

    def set_run_info(self, run_info, metadata, manifests):
        """Set the run information for the current run. This is
        called in Experiment class after the model run is complete"""
        self.run_info.update(run_info)
        self.run_info.update(get_metadata(metadata))
        self.run_info.update(get_manifests(manifests))

    def record_run(self, timings, scheduler, run_status):
        """
        Build information for the current run and write it to a JSON file.
        If telemetry is configured, post the telemetry job information
        """
        # Skip telemetry if no run information has been set, e.g. the model
        # has not been run
        if self.run_info == {}:
            return

        # Query the scheduler just before recording the run information to
        # try get the most up-to-date information of the usage statistics
        # as they only get updated periodically
        self.run_info.update(get_scheduler_run_info(scheduler))

        # Add timings to the run info and add end time and total run duration
        self.run_info.update(get_timings(timings))

        # Add run status
        self.run_info['payu_run_status'] = run_status

        # Write run job information to a JSON file
        if self.run_info_filepath is None:
            warnings.warn(
                "Run job output file is not defined"
            )
        else:
            with open(self.run_info_filepath, 'w', encoding='utf-8') as f:
                json.dump(self.run_info, f, ensure_ascii=False, indent=4)

        if not self.telemetry_enabled:
            # Skip any external telemetry
            return

        # Check for valid external telemetry configuration file
        external_config = get_external_telemetry_config()
        if external_config is None:
            # Skip any external telemetry
            return

        # Add hostname to the run info fields
        self.run_info['hostname'] = external_config[CONFIG_FIELDS['HOSTNAME']]

        # Using threading to run the one post request in the background
        thread = threading.Thread(
            target=post_telemetry_data,
            kwargs= {
                'url': external_config[CONFIG_FIELDS['URL']],
                'token': external_config[CONFIG_FIELDS['TOKEN']],
                'data': self.run_info,
                'service_name': external_config[CONFIG_FIELDS['SERVICE_NAME']],
                'host': external_config[CONFIG_FIELDS['HOST']],
            },
        )
        thread.start()
