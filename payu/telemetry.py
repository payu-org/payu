import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
import warnings

import payu
from payu.metadata import Metadata
from payu.schedulers import Scheduler

# Environment variable for external telemetry configuration file
TELEMETRY_CONFIG = 'PAYU_TELEMETRY_CONFIG_PATH'

# Required telemetry configuration fields
SERVER_URL_FIELD = "server_url"
HOSTNAME_FIELD = "hostname"
TELEMETRY_CONFIG_FIELDS = [SERVER_URL_FIELD, HOSTNAME_FIELD]

# access-py-telemetry configuration
PAYU_RUN_SERVICE_NAME = "payu_run"
API_HANDLER_REQUEST_TIMEOUT = 10


def get_metadata(metadata: Metadata) -> Optional[Dict[str, Any]]:
    """Returns a dictionary of the experiment metadata to record"""
    metadata_dict = metadata.read_file()
    info = {
        'experiment_uuid': metadata_dict.get('experiment_uuid'),
        'experiment_created': metadata_dict.get('created', None),
        'experiment_name': metadata_dict.get('name', None),
        'model': metadata_dict.get('model', None)
    }
    return info


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
        'payu_control_dir': experiment.control_path,
        'payu_archive_dir': experiment.archive_path,
    }
    return info


def get_scheduler_run_info(scheduler: Scheduler) -> Dict[str, Any]:
    """Returns a dictionary of the scheduler job information"""
    scheduler_job_id = scheduler.get_job_id(short=False)
    scheduler_info = scheduler.get_job_info()

    info = {}
    if scheduler_info is not None:
        scheduler_info = {key.lower(): val
                          for key, val in scheduler_info.items()}
        info = {
            'scheduler_job_info': scheduler_info,
            # Storing a version pre-emptively incase scheduler_info dictionary
            # is modified in the future
            'scheduler_job_info_version': '1.0',
            'scheduler_type': scheduler.name,
            'scheduler_job_id': scheduler_job_id
        }
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


def post_telemetry_data(server_url: str,
                        extra_fields: Dict[str, Any],
                        service_name: str,
                        function_name: str,
                        request_timeout: int = API_HANDLER_REQUEST_TIMEOUT
                        ) -> None:
    """Posts telemetry data using the access-py-telemetry API.

    Parameters
    ----------
    server_url: str
        Endpoint for the telemetry
    extra_fields: Dict[str, Any]
        Extra fields to add to telemetry - this contains any extra metadata and
        payu run state info
    service_name: str
        This service name needs to match one configured in access_py_telemetry
    function_name: str
        Each telemetry record will store this function name
    request_timeout: int, default API_HANDLER_REQUEST_TIMEOUT
        Timeout while waiting for request
    """
    # Check if access_py_telemetry module is available
    try:
        from access_py_telemetry.api import ApiHandler
    except ImportError:
        warnings.warn(
            "access_py_telemetry module not found. Skipping posting telemetry."
        )
        return

    # Create telemetry handler
    api_handler = ApiHandler()
    api_handler.server_url = server_url
    api_handler.request_timeout = request_timeout

    # Add info to the telemetry server
    api_handler.add_extra_fields(service_name, extra_fields)
    api_handler.remove_fields(service_name, ["session_id"])

    # Send telemetry data
    api_handler.send_api_request(service_name=service_name,
                                 function_name=function_name,
                                 args={}, kwargs={})


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

        try:
            # Post telemetry data using the built run info fields
            # Using the payu run subcommand as the function name as the
            # telemetry covers the experiment run
            post_telemetry_data(
                server_url=external_config[SERVER_URL_FIELD],
                extra_fields=self.run_info,
                service_name=PAYU_RUN_SERVICE_NAME,
                function_name="payu.subcommands.run_cmd.runscript"
            )
        except Exception as e:
            warnings.warn(
                f"Error posting telemetry: {e}"
            )
