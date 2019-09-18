# coding: utf-8
"""payu.scheduler.pbs
   ===============

   Functions to support PBS based schedulers

   :copyright: Copyright 2011 Marshall Ward, see AUTHORS for details.
   :license: Apache License, Version 2.0, see LICENSE for details.
"""

# Standard library
import os
import sys
import shlex
import subprocess

import tenacity

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
        # Select the dict for this job (there should only be one entry in any case)
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
