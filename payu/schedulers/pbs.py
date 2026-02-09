""" Functions to support PBS based schedulers

:copyright: Copyright 2011 Marshall Ward, see AUTHORS for details.
:license: Apache License, Version 2.0, see LICENSE for details.
"""

# Standard library
import os
from pathlib import Path
import re
import sys
import shlex
import subprocess
from typing import Any, Dict, Optional
import warnings
from collections import Counter

import json
from tenacity import retry, stop_after_delay

import payu.envmod as envmod
from payu.fsops import check_exe_path
from payu.manifest import Manifest
from payu.schedulers.scheduler import Scheduler
from payu.telemetry import REQUEST_TIMEOUT


def _run_pbsnodes_json(timeout: int) -> Dict[str, Any]:
    """Run pbsnodes -a -F json and return parsed Json output."""
    cmd = ["pbsnodes", "-a", "-F", "json"]
    try:
        pbsnodes_output = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(
            f"Unable to collect pbs node info: command timed out after {timeout} seconds"
        ) from e

    try:
        return json.loads(pbsnodes_output.stdout)
    except json.JSONDecodeError as e:
        error_msg = (pbsnodes_output.stdout or "")
        raise RuntimeError(
            f"Failed to decode JSON output from pbsnodes command: {' '.join(cmd)}"
            f"\n Output: {error_msg}"
        ) from e


# TODO: This is a stub acting as a minimal port to a Scheduler class.
class PBS(Scheduler):
    name = "pbs"

    # Define walltime maps in (cpus, hours) for different queues
    WALLTIME_MAPS = {
        "normal": [
            (672, 48),
            (1440, 24),
            (2976, 10),
            (20736, 5),
        ],
        "express": [
            (480, 24),
            (3168, 5),
        ],
        "normalsr": [
            (1040, 48),
            (2080, 24),
            (4160, 10),
            (10400, 5),
        ],
        "expresssr": [
            (1040, 24),
            (2080, 5),
        ],
        "normalbw": [
            (336, 48),
            (840, 24),
            (1736, 10),
            (10080, 5),
        ],
        "expressbw": [
            (280, 24),
            (1848, 5),
        ],
        "normalsl": [
            (288, 48),
            (608, 24),
            (1984, 10),
            (3200, 5),
        ],
    }

    # Map payu queue names to pbsnode topology tags
    QUEUE_MAPS = {
        "normal":   "cpu-clx",
        "normalsr": "cpu-spr",
        "normalbw": "cpu-bdw",
        "normalsl": "cpu-skl",
        "express":   "cpu-clx",
        "expresssr": "cpu-spr",
        "expressbw": "cpu-bdw",
    }

    @classmethod
    def get_queue_walltime_hours(cls, queue: str, ncpus) -> int:
        """
        Get the queue walltime (in hours) for a given queue.
        """
        limits = cls.WALLTIME_MAPS.get(queue)
        if not limits:
            raise ValueError(f"Unknown queue: {queue}")

        # Check maximum cpu limit
        max_cpus = limits[-1][0]
        if ncpus > max_cpus:
            raise ValueError(
                f"Requested CPUs ({ncpus}) exceed maximum "
                f"for queue '{queue}' ({max_cpus})"
            )

        for cpu_limit, hours in limits:
            if ncpus <= cpu_limit:
                return hours

    @staticmethod
    def parse_walltime(walltime: int | str) -> float:
        # For time like inputs, yaml has auto-parsed correct time format (non-zero-padded formats) to int values
        # such as 1:30:00, 1:00, rather than 01:30:00 or 01:00
        # yaml also parse unquoted numeric values such as 05 as int(5)
        if isinstance(walltime, int):
            return walltime / 3600

        # for zero-padded formats
        s = walltime.strip()

        # covers numeric string like "05"
        if s.isdigit():
            return int(s) / 3600

        parts = s.split(":")

        if len(parts) == 2:
            # covers 01:00 format
            m, s = map(int, parts)
            h = 0
        elif len(parts) == 3:
            # covers 01:30:00 format
            h, m, s = map(int, parts)
        else:
            raise ValueError(f"Invalid walltime format: {walltime!r}")
        return (h*3600 + m*60 + s) / 3600

    @classmethod
    def validate_walltime_with_queue_limits(cls, walltime: int | str, queue: str, ncpus: int):
        requested_hours = cls.parse_walltime(walltime)
        limit = cls.get_queue_walltime_hours(queue, ncpus)
        if limit is not None and requested_hours > limit:
            raise ValueError(
                f"Requested walltime of {requested_hours} hours exceeds "
                f"the limit of {limit} hours for queue '{queue}' with "
                f"{ncpus} CPUs."
            )

    @staticmethod
    def _mem_convert_kb_to_gb(mem_kb: str) -> int:
        s = str(mem_kb).strip().lower()
        if not s.endswith("kb"):
            raise ValueError(f"Memory string '{mem_kb}' is not in kb format")
        return int(s.replace("kb", "")) // (1024 * 1024)

    @classmethod
    def get_queue_node_shape(cls, queue: str) -> tuple[int, int]:
        """
        Get the node shape (cpu count and memory) for a given queue.
        """
        tag = cls.QUEUE_MAPS.get(queue)
        # collect all node information from pbsnodes
        data = _run_pbsnodes_json(timeout=REQUEST_TIMEOUT)

        ncpus, mem = [], []
        for node in data["nodes"].values():
            ra = node["resources_available"]
            if tag not in ra.get("topology", ""):
                continue
            ncpus.append(int(ra["ncpus"]))
            mem.append(cls._mem_convert_kb_to_gb(ra["mem"]))

        if not ncpus or not mem:
            raise ValueError(f"No nodes matched queue '{queue}' (tag '{tag}')")

        return Counter(ncpus).most_common(1)[0][0], Counter(mem).most_common(1)[0][0]

    def submit(self, pbs_script, pbs_config, pbs_vars=None, python_exe=None):
        """Prepare a correct PBS command string"""

        pbs_env_init()

        # Initialisation
        if pbs_vars is None:
            pbs_vars = {}

        # Necessary for testing
        if python_exe is None:
            python_exe = sys.executable

        pbs_flags = []

        pbs_queue = pbs_config.get('queue', 'normal')
        pbs_flags.append('-q {queue}'.format(queue=pbs_queue))

        pbs_project = pbs_config.get('project', os.environ['PROJECT'])
        pbs_flags.append('-P {project}'.format(project=pbs_project))

        pbs_resources = ['walltime', 'ncpus', 'mem', 'jobfs']

        for res_key in pbs_resources:
            res_flags = []
            res_val = pbs_config.get(res_key)
            if res_val:
                res_flags.append(
                    '{key}={val}'.format(key=res_key, val=res_val)
                )
            if res_flags:
                pbs_flags.append('-l {res}'.format(res=','.join(res_flags)))

        # TODO: Need to pass lab.config_path somehow...
        pbs_jobname = pbs_config.get('jobname', os.path.basename(os.getcwd()))
        if pbs_jobname:
            # PBSPro has a 15-character jobname limit
            pbs_flags.append('-N {name}'.format(name=pbs_jobname[:15]))

        pbs_priority = pbs_config.get('priority')
        if pbs_priority:
            pbs_flags.append('-p {priority}'.format(priority=pbs_priority))

        pbs_flags.append('-l wd')

        pbs_join = pbs_config.get('join', 'n')
        if pbs_join not in ('oe', 'eo', 'n'):
            print('payu: error: unknown qsub IO stream join setting.')
            sys.exit(-1)
        else:
            pbs_flags.append('-j {join}'.format(join=pbs_join))

        # Append environment variables to qsub command
        # TODO: Support full export of environment variables: `qsub -V`
        pbs_vstring = ','.join('{0}={1}'.format(k, v)
                               for k, v in pbs_vars.items())
        pbs_flags.append('-v ' + pbs_vstring)

        storages = set()
        storage_config = pbs_config.get('storage', {})
        mounts = set(['/scratch', '/g/data'])
        for mount in storage_config:
            mounts.add(mount)
            for project in storage_config[mount]:
                storages.add(make_mount_string(encode_mount(mount), project))

        # Append any additional qsub flags here
        pbs_flags_extend = pbs_config.get('qsub_flags')
        if pbs_flags_extend:
            pbs_flags.append(pbs_flags_extend)

        payu_path = pbs_vars.get('PAYU_PATH', os.path.dirname(sys.argv[0]))
        pbs_script = check_exe_path(payu_path, pbs_script)
        ctrl_path = pbs_config.get('control_path')

        # Check for storage paths that might need to be mounted in the
        # python and script paths
        extra_search_paths = [python_exe, payu_path, pbs_script, ctrl_path]

        laboratory_path = pbs_config.get('laboratory', None)
        if laboratory_path is not None:
            extra_search_paths.append(laboratory_path)
        short_path = pbs_config.get('shortpath', None)
        if short_path is not None:
            extra_search_paths.append(short_path)

        module_use_paths = pbs_config.get('modules', {}).get('use', [])
        extra_search_paths.extend(module_use_paths)

        remote_sync_directory = pbs_config.get('sync', {}).get('path', None)
        if remote_sync_directory is not None:
            extra_search_paths.append(remote_sync_directory)
        storages.update(find_mounts(extra_search_paths, mounts))
        storages.update(find_mounts(get_manifest_paths(), mounts))

        # Add storage flags. Note that these are sorted to get predictable
        # behaviour for testing
        pbs_flags_extend = '+'.join(sorted(storages))
        if pbs_flags_extend:
            pbs_flags.append("-l storage={}".format(pbs_flags_extend))

        # Set up environment modules here for PBS.
        envmod.setup()
        envmod.module('load', 'pbs')

        # Check for custom container launcher script environment variable
        launcher_script = os.environ.get('ENV_LAUNCHER_SCRIPT_PATH')
        if (
            launcher_script
            and Path(launcher_script).is_file()
            and os.access(launcher_script, os.X_OK)
        ):
            # Prepend the container launcher script to the python command
            # so the python executable is accessible in the container
            python_exe = f'{launcher_script} {python_exe}'

        # Construct job submission command
        cmd = 'qsub {flags} -- {python} {script}'.format(
            flags=' '.join(pbs_flags),
            python=python_exe,
            script=pbs_script
        )

        return cmd

    def get_job_id(self, short: bool = True) -> Optional[str]:
        """Get PBS job ID

        Parameters
        ----------
        short: bool, default True
            Return shortened form of the job ID

        Returns
        ----------
        Optional[str]
            Job id if defined, None otherwise
        """

        jobid = os.environ.get('PBS_JOBID', '')

        if short:
            # Strip off '.rman2'
            jobid = jobid.split('.')[0]

        return jobid

    def get_job_info(self) -> Optional[Dict[str, Any]]:
        """
        Get information about the job from the PBS server

        Returns
        ----------
        Optional[Dict[str, Any]]
            Dictionary of information extracted from qstat output
        """
        jobid = self.get_job_id()

        info = None

        if not jobid == '' and jobid is not None:
            info = get_job_info_json(jobid)

        return info


    def get_all_jobs_status(self) -> Optional[Dict[str, Any]]:
        """
        Get information about all jobs from the PBS server

        Returns
        ----------
        Optional[Dict[str, Any]]
            Dictionary of information extracted from qstat output
        """
        info = get_job_info_json()
        if info is None:
            return None
        job_statuses = {}
        jobs = info.get('Jobs', {})
        for job_id, job_info in jobs.items():
            job_statuses[job_id] = {
                'job_state': job_info.get('job_state'),
                'exit_status': job_info.get('Exit_status'),
            }
        return job_statuses


@retry(stop=stop_after_delay(10), retry_error_callback=lambda a: None)
def get_job_info_json(
            job_id: Optional[str] = None
        ) -> Optional[Dict[str, Any]]:
    """
    Get full job information in JSON format from qstat. It is wrapped in retry
    with timeout to allow for PBS server to be slow to respond.
    If job_id is provided, get info for that job; otherwise, get info for
    all jobs.
    If timeout occurs or invalid json, return None
    """
    cmd = ["qstat", "-f", "-F", "json"]
    if job_id:
        cmd.append(job_id)

    # Parse the JSON output
    try:
        qstat_output = subprocess.run(
            cmd, capture_output=True, text=True, check=True,
        )
        return json.loads(qstat_output.stdout)
    except json.JSONDecodeError as e:
        warnings.warn(
            f"Failed to decode JSON output from qstat command: {' '.join(cmd)}"
            f"\n Error: {e}"
        )
        raise
    except subprocess.CalledProcessError as e:
        warnings.warn(
            f"Failed to run qstat command: {' '.join(cmd)}"
            f"\n Error: {e}"
        )
        raise


def pbs_env_init():

    # Initialise against PBS_CONF_FILE
    if sys.platform == 'win32':
        pbs_conf_fpath = r'C:\Program Files\PBS Pro\pbs.conf'
    else:
        pbs_conf_fpath = '/etc/pbs.conf'
    os.environ['PBS_CONF_FILE'] = pbs_conf_fpath

    try:
        with open(pbs_conf_fpath) as pbs_conf:
            for line in pbs_conf:
                try:
                    key, value = line.split('=')
                    os.environ[key] = value.rstrip()
                except ValueError:
                    pass
    except IOError as ec:
        print('Unable to find PBS_CONF_FILE ... ' + pbs_conf_fpath)
        sys.exit(1)


def encode_mount(mount):
    """
    Turn a mount point point into the keyword used to specify storages,
    i.e. remove path separators
    """
    return re.sub(os.path.sep, '', mount)


def make_mount_string(mount, project):
    """
    Return mount and project string used to specify storages
    """
    return "{mount}/{project}".format(mount=mount, project=project)


def find_mounts(paths, mounts):
    """
    Search a path for a matching mount point and return a set of unique
    NCI compatible strings to add to the qsub command
    """
    if not isinstance(paths, list):
        paths = [paths, ]
    if not isinstance(mounts, set):
        mounts = set(mounts)

    storages = set()

    for p in paths:
        for m in mounts:
            if p.startswith(m):
                # Find the number of path elements in the mount string
                offset = len(m.split(os.path.sep))
                # Relevant project code is the next element of the path
                # after the mount point. DO NOT USE os.path.split as it
                # is not consistent with trailing slash
                proj = p.split(os.path.sep)[offset]
                storages.add(make_mount_string(encode_mount(m), proj))
                break

    return storages


def get_manifest_paths():
    """
    Return a list of paths from manifest files to use to check for
    storage paths
    """
    tmpmanifest = Manifest(config={}, reproduce=False)
    tmpmanifest.load_manifests()

    return tmpmanifest.get_all_previous_fullpaths()
