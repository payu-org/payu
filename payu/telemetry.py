from datetime import date, datetime
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
TELEMETRY_CONFIG = 'PAYU_TELEMETRY_CONFIG_PATH'

# Required telemetry configuration fields
TELEMETRY_URL_FIELD = "telemetry_url"
TELEMETRY_TOKEN_FIELD = "telemetry_token"
TELEMETRY_SERVICE_NAME_FIELD = "telemetry_service_name"
HOSTNAME_FIELD = "hostname"

TELEMETRY_CONFIG_FIELDS = [TELEMETRY_URL_FIELD, TELEMETRY_TOKEN_FIELD, TELEMETRY_SERVICE_NAME_FIELD, HOSTNAME_FIELD]

REQUEST_TIMEOUT = 10

TELEMETRY_VERSION = "1.0.0"


def get_metadata(metadata: Metadata) -> Optional[Dict[str, Any]]:
    """Returns a dictionary of the experiment metadata to record"""
    metadata_dict = metadata.read_file()
    if len(metadata_dict) == 0:
        return {}

    return {
        'experiment_uuid': metadata_dict.get('experiment_uuid', None),
        'experiment_metadata': metadata_dict
    }


def get_experiment_run_state(experiment) -> Optional[Dict[str, Any]]:
    """Returns a dictionary of the experiment run state"""
    info = {
        'payu_run_id': experiment.run_id,
        'payu_current_run': experiment.counter,
        'payu_n_runs':  experiment.n_runs,
        'payu_job_status': experiment.run_job_status,
        'payu_start_time': experiment.start_time.isoformat(),
        'payu_finish_time': experiment.finish_time.isoformat(),
        'payu_walltime_seconds':
            (experiment.finish_time - experiment.start_time).total_seconds(),
        'payu_version': payu.__version__,
        'payu_path': os.path.dirname(experiment.payu_path),
    }
    return info


def get_scheduler_run_info(scheduler: Scheduler) -> Dict[str, Any]:
    """Returns a dictionary of the scheduler job information"""
    scheduler_job_id = scheduler.get_job_id(short=False)
    scheduler_info = scheduler.get_job_info()

    info = {}
    if scheduler_info is not None:
        info['scheduler_job_info'] = scheduler_info
        info['scheduler_type'] = scheduler.name
        info['scheduler_job_id'] = scheduler_job_id
    return info


def get_external_telemetry_config() -> Optional[Dict[str, Any]]:
    """Loads the external telemetry configuration file.
    If a valid file does not exist, return None"""
    # Check path to telemetry config file exists
    config_path = Path(os.environ[TELEMETRY_CONFIG])
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
    for field in TELEMETRY_CONFIG_FIELDS:
        if field not in telemetry_config:
            warnings.warn(
                f"Required field '{field}' not found in configuration file "
                f"at {TELEMETRY_CONFIG}: {config_path}. "
                "Skipping posting telemetry"
            )
            return None

    return telemetry_config


def post_telemetry_data(telemetry_url: str,
                        telemetry_token: Dict[str, Any],
                        telemetry_data: Dict[str, Any],
                        telemetry_service_name: str,
                        request_timeout: int = REQUEST_TIMEOUT,
                        ) -> None:
    """Posts telemetry data

    Parameters
    ----------
    telemetry_url: str
        Endpoint for the telemetry
    telemetry_token: str
        Header token for the telemetry request
    telemetry_data: Dict[str, Any]
        Unstructured run information
    telemetry_service_name: str
        Service name for the telemetry record
    request_timeout: int, default REQUEST_TIMEOUT
        Timeout while waiting for request
    """
    headers = {
        'Content-type': 'application/json',
        'Authorization': 'Token ' + telemetry_token
    }

    data = {
        "service": telemetry_service_name,
        "version": TELEMETRY_VERSION,
        "date": date.today().isoformat(),
        "telemetry": telemetry_data
    }

    starttime = datetime.now()
    print(f"**Debug**: posting telemetry to {telemetry_url}")
    try:
        response = requests.post(telemetry_url, data=json.dumps(data), headers=headers, timeout=request_timeout)
        if response.status_code >= 400:
            warnings.warn(
                f"Error posting telemetry: {response.status_code} - {response.json()}"
            )
    except Exception as e:
        warnings.warn(f"Error posting telemetry: {e}")

    print(f"**Debug**: post request took {(datetime.now() - starttime).total_seconds()} seconds")


class Telemetry():
    """Telemetry class to store and post telemetry information.
    Currently these class methods are accessed during an Experiment run -
    so in payu.Experiment class and in the payu run subcommand.
    """

    def __init__(self, config, scheduler):

        self.run_info = {}
        self.run_info_filepath = None

        # Check for config.yaml option to disable telemetry, and if an
        # environment variable for an external telemetry config file is set
        self.telemetry_enabled = (
            config.get('telemetry', {}).get('enable', True)
            and TELEMETRY_CONFIG in os.environ
        )

        self.scheduler = scheduler

    def set_run_info_filepath(self, filepath: Path):
        """This file path will be different depending depending if there
        are model errors, whether archive runs or not. This is updated
        in different stages the Experiment class"""
        self.run_info_filepath = filepath

    def set_run_info(self, experiment):
        """Set the run information for the current run. This is
        called in Experiment class after the model run is complete"""
        self.run_info.update(get_metadata(experiment.metadata))
        self.run_info.update(get_experiment_run_state(experiment))

    def clear_run_info(self):
        self.run_info = {}

    def record_run(self):
        """
        Build information for the current run and write it to a JSON file.
        If telemetry is configured, post the telemetry job information
        """
        # Query the scheduler just before recording the run information to
        # try get the most up-to-date information of the usage statistics
        # as they only get updated periodically
        self.run_info.update(get_scheduler_run_info(self.scheduler))

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
        self.run_info.update({'hostname': external_config[HOSTNAME_FIELD]})

        starttime = datetime.now()

        # Using threading to run the one post request in the background
        thread = threading.Thread(
            target=post_telemetry_data,
            args=(
                external_config[TELEMETRY_URL_FIELD],
                external_config[TELEMETRY_TOKEN_FIELD],
                self.run_info,
                external_config[TELEMETRY_SERVICE_NAME_FIELD]
            )
        )
        thread.start()
        print(f"**Debug**: post_telemetry_data took {(datetime.now() - starttime).total_seconds()} seconds")
