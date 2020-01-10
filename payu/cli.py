"""payu.cli
   ========

   Command line interface tools

   :copyright: Copyright 2011 Marshall Ward, see AUTHORS for details.
   :license: Apache License, Version 2.0, see LICENSE for details
"""

import argparse
from distutils import sysconfig
import importlib
import os
import pkgutil
import re
import shlex
import subprocess
import sys

import payu
import payu.envmod as envmod
from payu.models import index as supported_models
import payu.subcommands
from payu.scheduler.pbs import pbs_env_init

# Default configuration
DEFAULT_CONFIG = 'config.yaml'


def parse():
    """Parse the command line inputs and execute the subcommand."""

    # Build the list of subcommand modules
    modnames = [mod for (_, mod, _)
                in pkgutil.iter_modules(payu.subcommands.__path__,
                                        prefix=payu.subcommands.__name__ + '.')
                if mod.endswith('_cmd')]

    subcmds = [importlib.import_module(mod) for mod in modnames]

    # Construct the subcommand parser
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', action='version',
                        version='payu {0}'.format(payu.__version__))

    subparsers = parser.add_subparsers()

    for cmd in subcmds:
        cmd_parser = subparsers.add_parser(cmd.title, **cmd.parameters)
        cmd_parser.set_defaults(run_cmd=cmd.runcmd)

        for arg in cmd.arguments:
            cmd_parser.add_argument(*arg['flags'], **arg['parameters'])

    # Display help if no arguments are provided
    if len(sys.argv) == 1:
        parser.print_help()
    else:
        args = vars(parser.parse_args())
        run_cmd = args.pop('run_cmd')
        run_cmd(**args)


def get_model_type(model_type, config):
    """Determine and validate the active model type."""

    # If no model type is given, then check the config file
    if not model_type:
        model_type = config.get('model')

    # If there is still no model type, try the parent directory
    if not model_type:
        model_type = os.path.basename(os.path.abspath(os.pardir))
        print('payu: warning: Assuming model is {0} based on parent directory '
              'name.'.format(model_type))

    if model_type not in supported_models:
        print('payu: error: Unknown model {0}'.format(model_type))
        sys.exit(-1)


def set_env_vars(init_run=None, n_runs=None, lab_path=None, dir_path=None,
                 reproduce=None):
    """Construct the environment variables used by payu for resubmissions."""
    payu_env_vars = {}

    # Setup Python dynamic library link
    lib_paths = sysconfig.get_config_vars('LIBDIR')
    payu_env_vars['LD_LIBRARY_PATH'] = ':'.join(lib_paths)
    if 'PYTHONPATH' in os.environ:
        payu_env_vars['PYTHONPATH'] = os.environ['PYTHONPATH']

    # Set (or import) the path to the PAYU scripts (PAYU_PATH)
    # NOTE: We may be able to use sys.path[0] here.
    payu_binpath = os.environ.get('PAYU_PATH')

    if not payu_binpath or not os.path.isdir(payu_binpath):
        payu_binpath = os.path.dirname(sys.argv[0])

    payu_env_vars['PAYU_PATH'] = payu_binpath

    # Set the run counters
    if init_run:
        init_run = int(init_run)
        assert init_run >= 0
        payu_env_vars['PAYU_CURRENT_RUN'] = init_run

    if n_runs:
        n_runs = int(n_runs)
        assert n_runs > 0
        payu_env_vars['PAYU_N_RUNS'] = n_runs

    # Import explicit project paths
    if lab_path:
        payu_env_vars['PAYU_LAB_PATH'] = os.path.normpath(lab_path)

    if dir_path:
        payu_env_vars['PAYU_DIR_PATH'] = os.path.normpath(dir_path)

    if reproduce:
        payu_env_vars['PAYU_REPRODUCE'] = reproduce

    # Pass through important module related environment variables
    module_env_vars = ['MODULESHOME', 'MODULES_CMD', 'MODULEPATH', 'MODULEV']
    for var in module_env_vars:
        if var in os.environ:
            payu_env_vars[var] = os.environ[var]

    return payu_env_vars


def find_mounts(paths, mounts):
    """
    Search a path for a matching mount point and return a set of unique
    NCI compatible strings to add to the qsub command
    """
    if not isinstance(paths, list):
        paths = [paths, ]
    if not isinstance(mounts, list):
        mounts = [mounts, ]

    storages = set()

    for p in paths:
        for m in mounts:
            if p.startswith(m):
                # Relevant project code is the next element of the path
                # after the mount point
                proj_code = os.path.relpath(p, m).split(os.path.sep)[0]
                storages.add("/".join([re.sub(os.path.sep, '', m), proj_code]))
                break

    return storages


def submit_job(pbs_script, pbs_config, pbs_vars=None):
    """Submit a userscript the scheduler."""

    pbs_env_init()

    # Initialisation
    if pbs_vars is None:
        pbs_vars = {}

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

    # Append any additional qsub flags here
    pbs_flags_extend = pbs_config.get('qsub_flags')
    if pbs_flags_extend:
        pbs_flags.append(pbs_flags_extend)

    if not os.path.isabs(pbs_script):
        # NOTE: PAYU_PATH is always set if `set_env_vars` was always called.
        #       This is currently always true, but is not explicitly enforced.
        #       So this conditional check is a bit redundant.
        payu_bin = pbs_vars.get('PAYU_PATH', os.path.dirname(sys.argv[0]))
        pbs_script = os.path.join(payu_bin, pbs_script)
        assert os.path.isfile(pbs_script)

    # Set up environment modules here for PBS.
    envmod.setup()
    envmod.module('load', 'pbs')

    # Construct job submission command
    cmd = 'qsub {flags} -- {python} {script}'.format(
        flags=' '.join(pbs_flags),
        python=sys.executable,
        script=pbs_script
    )
    print(cmd)

    subprocess.check_call(shlex.split(cmd))
