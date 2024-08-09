"""payu.cli
   ========

   Command line interface tools

   :copyright: Copyright 2011 Marshall Ward, see AUTHORS for details.
   :license: Apache License, Version 2.0, see LICENSE for details
"""

import argparse
import sysconfig
import importlib
import os
import pkgutil
import shlex
import subprocess
import sys
import warnings

import payu
import payu.envmod as envmod
from payu.fsops import is_conda
from payu.models import index as supported_models
from payu.schedulers import index as scheduler_index
import payu.subcommands

# Default configuration
DEFAULT_CONFIG = 'config.yaml'

# Force warnings.warn() to omit the source code line in the message
formatwarning_orig = warnings.formatwarning
warnings.formatwarning = (
    lambda message, category, filename, lineno, line=None: (
        formatwarning_orig(message, category, filename, lineno, line='')
    )
)


def parse():
    """Parse the command line inputs and execute the subcommand."""
    parser = generate_parser()

    # Display help if no arguments are provided
    if len(sys.argv) == 1:
        parser.print_help()
    else:
        args = vars(parser.parse_args())
        run_cmd = args.pop('run_cmd')
        run_cmd(**args)


def generate_parser():
    """Parse the command line inputs generate and return parser."""

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

    return parser


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
                 reproduce=False, force=False, force_prune_restarts=False,
                 sync_restarts=False, sync_ignore_last=False):
    """Construct the environment variables used by payu for resubmissions."""
    payu_env_vars = {}

    if not is_conda():
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

    if force:
        payu_env_vars['PAYU_FORCE'] = force

    if sync_restarts:
        payu_env_vars['PAYU_SYNC_RESTARTS'] = sync_restarts

    if sync_ignore_last:
        payu_env_vars['PAYU_SYNC_IGNORE_LAST'] = sync_ignore_last

    if force_prune_restarts:
        payu_env_vars['PAYU_FORCE_PRUNE_RESTARTS'] = force_prune_restarts

    # Pass through important module related environment variables
    module_env_vars = ['MODULESHOME', 'MODULES_CMD', 'MODULEPATH', 'MODULEV']
    for var in module_env_vars:
        if var in os.environ:
            payu_env_vars[var] = os.environ[var]

    return payu_env_vars


def submit_job(script, config, vars=None):
    """Submit a userscript the scheduler."""

    # TODO: Temporary stub to replicate the old approach
    sched_name = config.get('scheduler', 'pbs')
    sched_type = scheduler_index[sched_name]
    sched = sched_type()
    cmd = sched.submit(script, config, vars)
    print(cmd)

    subprocess.check_call(shlex.split(cmd))
