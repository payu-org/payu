"""payu.cli
   ========

   Command line interface tools

   :copyright: Copyright 2011-2014 Marshall Ward, see AUTHORS for details.
   :license: Apache License, Version 2.0, see LICENSE for details
"""

import argparse
import errno
import importlib
import os
import pkgutil
import shlex
import subprocess
import sys

import yaml

import payu
import payu.envmod as envmod
from payu.modelindex import index as supported_models
import payu.subcommands

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
                        version='payu {}'.format(payu.__version__))

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


#---
def get_config(config_path):
    """Open the configuration file and construct the configuration data. """

    if not config_path and os.path.isfile(DEFAULT_CONFIG):
        config_path = DEFAULT_CONFIG

    try:
        with open(config_path, 'r') as config_file:
            config = yaml.load(config_file)
    except (TypeError, IOError) as exc:
        if config_path == None:
            config = {}
        elif type(exc) == IOError and exc.errno == errno.ENOENT:
            print('payu: error: Configuration file {} not found.'
                  ''.format(config_path))
            sys.exit(errno.ENOENT)
        else:
            raise

    return config


#---
def get_model_type(model_type, config):
    """Determine and validate the active model type."""

    # If no model type is given, then check the config file
    if not model_type:
        model_type = config.get('model')

    # If there is still no model type, try the parent directory
    if not model_type:
        model_type = os.path.basename(os.path.abspath(os.pardir))
        print('payu: warning: Assuming model is {} based on parent directory '
              'name.'.format(model_type))

    if not model_type in supported_models:
        print('payu: error: Unknown model {}'.format(model_type))
        sys.exit(-1)


#---
def set_env_vars(init_run=None, n_runs=None, lab_path=None):
    """Construct the environment variables used by payu for resubmissions."""

    payu_env_vars = {}

    # Pass along the current PYTHONPATH, and append payu's path if necessary
    payu_path, _ = os.path.split(payu.__path__[0])

    try:
        py_paths = os.environ['PYTHONPATH'].split(':')
        py_abspaths = [os.path.abspath(p) for p in py_paths]

        if not os.path.abspath(payu_path) in py_abspaths:
            py_paths.insert(0, payu_path)

        payu_env_vars['PYTHONPATH'] = ':'.join(py_paths)

    except KeyError:
        payu_env_vars['PYTHONPATH'] = payu_path

    payu_modnames = [mod for mod in os.environ['LOADEDMODULES'].split(':')
                     if mod.startswith('payu')]
    if payu_modnames:
        payu_mname = payu_modnames[0]

        payu_modpaths = [mod for mod in os.environ['_LMFILES_'].split(':')
                         if payu_mname in mod]

        payu_mpath = payu_modpaths[0].rstrip(payu_mname)

        payu_env_vars['PAYU_MODULENAME'] = payu_mname
        payu_env_vars['PAYU_MODULEPATH'] = payu_mpath

    else:
        # Explicitly set and pass the executable paths
        for path in os.environ['PATH'].split(':'):
            if 'payu' in os.listdir(path):
                payu_binpath = path
                break
            payu_binpath = None

        if payu_binpath:
            payu_env_vars['PAYU_PATH'] = payu_binpath

    if init_run:
        init_run = int(init_run)
        assert init_run >= 0

        payu_env_vars['PAYU_CURRENT_RUN'] = init_run

    if n_runs:
        n_runs = int(n_runs)
        assert n_runs > 0

        payu_env_vars['PAYU_N_RUNS'] = n_runs

    if lab_path:
        payu_env_vars['PAYU_LAB_PATH'] = lab_path

    return payu_env_vars


#---
def submit_job(pbs_script, pbs_config, pbs_vars=None):
    """Submit a userscript the scheduler."""

    pbs_flags = []

    pbs_queue = pbs_config.get('queue', 'normal')
    pbs_flags.append('-q {}'.format(pbs_queue))

    pbs_project = pbs_config.get('project', os.environ['PROJECT'])
    pbs_flags.append('-P {}'.format(pbs_project))

    pbs_resources = ['walltime', 'ncpus', 'mem', 'jobfs']

    for res_key in pbs_resources:
        res_flags = []
        res_val = pbs_config.get(res_key)
        if res_val:
            res_flags.append('{}={}'.format(res_key, res_val))

        if res_flags:
            pbs_flags.append('-l {}'.format(','.join(res_flags)))

    pbs_jobname = pbs_config.get('jobname')
    if pbs_jobname:
        # PBSPro has a 15-character jobname limit
        pbs_flags.append('-N {}'.format(pbs_jobname[:15]))

    pbs_priority = pbs_config.get('priority')
    if pbs_priority:
        pbs_flags.append('-p {}'.format(pbs_priority))

    pbs_flags.append('-l wd')

    pbs_join = pbs_config.get('join', 'oe')
    if not pbs_join in ('oe', 'eo', 'n'):
        print('payu: error: unknown qsub IO stream join setting.')
        sys.exit(-1)
    else:
        pbs_flags.append('-j {}'.format(pbs_join))

    if pbs_vars:
        pbs_vstring = ','.join('{}={}'.format(k, v)
                               for k, v in pbs_vars.iteritems())
        pbs_flags.append('-v ' + pbs_vstring)

    # Append any additional qsub flags here
    pbs_flags_extend = pbs_config.get('qsub_flags')
    if pbs_flags_extend:
        pbs_flags.append(pbs_flags_extend)

    # Enable PBS, in case it's not available
    envmod.setup()
    envmod.module('load', 'pbs')

    # If script path does not exist, then check the PATH directories
    if not os.path.isabs(pbs_script):
        for path in os.environ['PATH'].split(':'):
            if os.path.isdir(path) and pbs_script in os.listdir(path):
                pbs_script = os.path.join(path, pbs_script)
                break

    # Construct full command
    cmd = 'qsub {} {}'.format(' '.join(pbs_flags), pbs_script)

    subprocess.check_call(shlex.split(cmd))
