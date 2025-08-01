"""Functions to support Slurm scheduling.

:copyright: Copyright 2011 Marshall Ward, see AUTHORS for details.
:license: Apache License, Version 2.0, see LICENSE for details.
"""

# Standard library
import os
import re
import sys
import shlex
import subprocess

from hpcpy import SlurmClient

from payu.fsops import check_exe_path
from payu.schedulers.scheduler import Scheduler, JOB_SCRIPT_TEMPLATE

class Slurm(Scheduler):
    # TODO: __init__

    def submit(self, pbs_script, pbs_config, pbs_vars=None, python_exe=None,
              storages=None, dry_run=False):
        """Prepare a correct PBS command string"""

        if python_exe is None:
            python_exe = sys.executable

        if pbs_vars is None:
            pbs_vars = {}

        payu_path = pbs_vars.get('PAYU_PATH', os.path.dirname(sys.argv[0]))
        pbs_script = check_exe_path(payu_path, pbs_script)

        pbs_flags = []
        pbs_flags.append('--time={}'.format(pbs_config.get('walltime')))
        pbs_flags.append('--ntasks={}'.format(pbs_config.get('ncpus')))

        # Flags which need to be addressed
        pbs_flags.append('--qos=debug')
        pbs_flags.append('--cluster=c4')

        client = SlurmClient()
        job = client.submit(
            dry_run=dry_run,
            directives=pbs_flags,
            job_script=JOB_SCRIPT_TEMPLATE,
            render=True,
            python_exe=python_exe,
            payu_exe=pbs_script,
        )
        return job
