""" Functions to support PBS based schedulers

:copyright: Copyright 2011 Marshall Ward, see AUTHORS for details.
:license: Apache License, Version 2.0, see LICENSE for details.
"""

# Standard library
import os
import re
import sys
import shlex
import subprocess

import payu.envmod as envmod
from payu.fsops import check_exe_path
from payu.manifest import Manifest
from payu.schedulers.scheduler import Scheduler

from tenacity import retry, stop_after_delay


# TODO: This is a stub acting as a minimal port to a Scheduler class.
class PBS(Scheduler):
    # TODO: __init__

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

        # Check for storage paths that might need to be mounted in the
        # python and script paths
        extra_search_paths = [python_exe, payu_path, pbs_script]

        laboratory_path = pbs_config.get('laboratory', None)
        if laboratory_path is not None:
            extra_search_paths.append(laboratory_path)
        short_path = pbs_config.get('shortpath', None)
        if short_path is not None:
            extra_search_paths.append(short_path)

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

        # Construct job submission command
        cmd = 'qsub {flags} -- {python} {script}'.format(
            flags=' '.join(pbs_flags),
            python=python_exe,
            script=pbs_script
        )

        return cmd


# TODO: These support functions can probably be integrated into the class

def get_job_id(short=True):
    """
    Return PBS job id
    """

    jobid = os.environ.get('PBS_JOBID', '')

    if short:
        # Strip off '.rman2'
        jobid = jobid.split('.')[0]

    return(jobid)


def get_job_info():
    """
    Get information about the job from the PBS server
    """
    jobid = get_job_id()

    info = None

    if not jobid == '':
        info = get_qstat_info('-ft {0}'.format(jobid), 'Job Id:')

    if info is not None:
        # Select the dict for this job (there should only be one
        # entry in any case)
        info = info['Job Id: {}'.format(jobid)]

        # Add the jobid to the dict and then return
        info['Job_ID'] = jobid

    return info


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


# Wrap this in retry from tenancity. Keep trying for 10 seconds and
# even if still fails return None
@retry(stop=stop_after_delay(10), retry_error_callback=lambda a: None)
def get_qstat_info(qflag, header, projects=None, users=None):

    qstat = os.path.join(os.environ['PBS_EXEC'], 'bin', 'qstat')
    cmd = '{} {}'.format(qstat, qflag)

    cmd = shlex.split(cmd)
    output = subprocess.check_output(cmd)
    if sys.version_info.major >= 3:
        output = output.decode()

    entries = (e for e in output.split('{}: '.format(header)) if e)

    # Immediately remove any non-project entries
    if projects or users:
        entries = (e for e in entries
                   if any('project = {}'.format(p) in e for p in projects)
                   or any('Job_Owner = {}'.format(u) in e for u in users))

    attribs = ((k.split('.')[0], v.replace('\n\t', '').split('\n'))
               for k, v in (e.split('\n', 1) for e in entries))

    status = {k: dict((kk.strip(), vv.strip())
              for kk, vv in (att.split('=', 1) for att in v if att))
              for k, v in attribs}

    return status


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
    tmpmanifest.load()

    return tmpmanifest.get_all_fullpaths()


def generate_command(pbs_script, pbs_config, pbs_vars=None, python_exe=None):
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
            res_flags.append('{key}={val}'.format(key=res_key, val=res_val))

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

    # Check for storage paths that might need to be mounted in the
    # python and script paths
    extra_search_paths = [python_exe, payu_path, pbs_script]

    laboratory_path = pbs_config.get('laboratory', None)
    if laboratory_path is not None:
        extra_search_paths.append(laboratory_path)
    short_path = pbs_config.get('shortpath', None)
    if short_path is not None:
        extra_search_paths.append(short_path)

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

    # Construct job submission command
    cmd = 'qsub {flags} -- {python} {script}'.format(
        flags=' '.join(pbs_flags),
        python=python_exe,
        script=pbs_script
    )

    return cmd
