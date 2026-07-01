"""payu.cli
   ========

   Command line interface tools

   :copyright: Copyright 2011 Marshall Ward, see AUTHORS for details.
   :license: Apache License, Version 2.0, see LICENSE for details
"""
# Standard imports
import argparse
import sysconfig
import importlib
import os
import pkgutil
import shlex
import subprocess
import sys
import warnings
import logging
from pathlib import Path

# Local imports
import payu
import payu.envmod as envmod
from payu.fsops import is_conda
from payu.models import index as supported_models
from payu.schedulers import index as scheduler_index, DEFAULT_SCHEDULER_CONFIG
import payu.subcommands
from payu.logger import setup_logger
import payu.subcommands.args as arg_templates
from payu.telemetry import write_queued_job_file
import payu.errors as errors

# Default configuration
DEFAULT_CONFIG = 'config.yaml'

def parse():
    """Parse the command line inputs and execute the subcommand."""
    # Pass the warning through the logger
    logging.captureWarnings(True)
    parser = generate_parser(is_interactive = True)

    arg_count = len(sys.argv)
    # filter out --stacktrace when counting argument numbers
    if '--stacktrace' in sys.argv:
        arg_count = arg_count - 1

    # filter out --log-level {CHOICE} when counting argument numbers
    if '--log-level' in sys.argv:
        arg_count = arg_count - 2
    
    # filter out --log-level={CHOICE} when counting argument numbers
    elif any(arg.startswith('--log-level=') for arg in sys.argv):
        arg_count = arg_count - 1

    # Display help if no arguments are provided
    if arg_count == 1:
        parser.print_help()
        return
    if arg_count > 2:
        parser = generate_parser()
    args = vars(parser.parse_args())
    run_cmd = args.pop('run_cmd')

    # We pop --stacktrace and --log_level here so they will not be propagated to runcmd() in subcommands
    stacktrace = args.pop('stacktrace', False)
    log_level = args.pop('log_level', None)

    # Override the STACKTRACE and LOG_LEVEL environment variables if flags are provided
    if log_level:
        os.environ['PAYU_LOG_LEVEL'] = str(log_level)
    if stacktrace:
        os.environ['PAYU_STACKTRACE'] = str(stacktrace)
    
        
    _execute_command(run_cmd, stacktrace=stacktrace, log_level=log_level, **args)


def generate_parser(is_interactive=False):
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
        # Add the stacktrace option to all subcommands for consitent CLI UX.
        # It will be extracted in the parse() and not propagated to subcommand's runcmd()
        cmd_parser.add_argument(*arg_templates.stacktrace['flags'], **arg_templates.stacktrace['parameters'])
        cmd_parser.add_argument(*arg_templates.log_level['flags'], **arg_templates.log_level['parameters'])

        for arg in cmd.arguments:
            if '--stacktrace' in arg['flags'] or '--log-level' in arg['flags']:
                continue
            cmd_parser.add_argument(*arg['flags'], **arg['parameters'])

        # If in interactive mode, make all required arguments no longer required
        if is_interactive:
            for action in cmd_parser._actions:
                if action.required:
                    action.required = False
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
        raise errors.PayuConfigError(f'Unknown model {model_type}')


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
    
    # Pass through the PBS nodes cache path if it exists
    if 'PAYU_PBSNODES_CACHE' in os.environ:
        payu_env_vars['PAYU_PBSNODES_CACHE'] = os.environ['PAYU_PBSNODES_CACHE']
    elif 'XDG_CACHE_HOME' in os.environ:
        payu_env_vars['XDG_CACHE_HOME'] = os.environ["XDG_CACHE_HOME"]

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

    # Pass on stacktrace and log level to PBS as environment variables
    if os.environ.get('PAYU_STACKTRACE'):
        payu_env_vars['PAYU_STACKTRACE'] = os.environ.get('PAYU_STACKTRACE')
    if os.environ.get('PAYU_LOG_LEVEL'):
        payu_env_vars['PAYU_LOG_LEVEL'] = os.environ.get('PAYU_LOG_LEVEL')

    return payu_env_vars


def submit_job(script, config, vars=None, expt=None, current_run=None, type=None):
    """Submit a userscript the scheduler and return the job ID"""

    # TODO: Temporary stub to replicate the old approach
    sched_name = config.get('scheduler', DEFAULT_SCHEDULER_CONFIG)
    sched_type = scheduler_index[sched_name]
    sched = sched_type()
    cmd = sched.submit(script, config, vars)
    print(cmd)

    try:
        result = subprocess.run(shlex.split(cmd), capture_output=True, check=True, text=True)

    except subprocess.CalledProcessError as e:
        error_msg = ("Error occurred while submitting job.\n")

        if e.returncode:
            error_msg += f"Exit code: {e.returncode}\n"
        if e.stdout:
            error_msg += f"STDOUT: {e.stdout}\n"
        if e.stderr:
            error_msg += f"STDERR: {e.stderr}"

        raise RuntimeError(error_msg)

    # Decode stdout and extract the job ID which is last for both PBS and Slurm
    result = result.stdout.strip()
    print(result)
    job_id = result.split()[-1]

    if expt is not None:

        if current_run is None:
            # Get the latest run number from the restart/output folder numbering
            # and set it as the run number to write job file
            expt.set_counters(keep_run_number=True)
            current_run = expt.counter
            
        write_queued_job_file(
            archive_path=Path(expt.archive_path),
            job_id=job_id,
            type=type,
            scheduler=expt.scheduler,
            metadata=expt.metadata,
            current_run=current_run,
        )


    return job_id

def set_logger_runscript(log_level=None):
    """Configure logging settings based on arguments and environment variables."""
    logging.captureWarnings(True)
    log_level_env = os.environ.get('PAYU_LOG_LEVEL')

    # If log_level is changed from default, update setup_logger
    # Priority: command line argument > environment variable > 'INFO' default
    if log_level is not None:
        active_level = log_level
    elif log_level_env:
        active_level = str(log_level_env).upper()
    else:
        active_level = 'INFO'

    setup_logger(active_level)

def set_stacktrace_runscript(stacktrace=None):
    """
    Configure stacktrace settings based on arguments and environment variables.
    Return True if stacktrace is enabled, False otherwise.
    """

    if stacktrace is True or str(os.environ.get('PAYU_STACKTRACE', 'False')).lower() == 'true':
        return True
    else:
        # Force warnings.warn() to omit the source code line in the message
        warnings.formatwarning = (
            lambda message, category, filename, lineno, line=None: f"{message}"
        )
        return False

def _execute_command(func, stacktrace=None, log_level=None, **args):
    """Execute a payu command with error handling and logging.
    Sets up logging, captures warnings through the logging system,
    and catches exceptions to provide clean error messages.
    """
    set_logger_runscript(log_level)
    stacktrace = set_stacktrace_runscript(stacktrace)

    try: 
        # Pass arguments to the command as dictionary
        func(**args)
    except errors.PayuError as e:
        # Show stacktrace when enabled.
        logging.exception(e, exc_info=stacktrace)
        sys.exit(1)
    except Exception as e:
        # Always show stacktrace for unknown bugs
        logging.exception(e)
        sys.exit(1)
        

# Add wrappers for runscript commands (entry points configured in pyproject.toml)
def parse_run():
    _parse_runscript("run")

def parse_collate():
    _parse_runscript("collate")

def parse_profile():
    _parse_runscript("profile")

def parse_sync():
    _parse_runscript("sync")


def _parse_runscript(cmd_name):
    """
    Parse the command line inputs (e.g., payu run) and pass it onto _execute_command.
    """
    # Attempt to import the requested runscript command module
    try:
        cmd = importlib.import_module(f'payu.subcommands.{cmd_name}_cmd')
    except ImportError:
        sys.exit(f"Unknown runscript command payu-{cmd_name}")
    
    # Construct the subcommand parser
    parser = argparse.ArgumentParser(**cmd.parameters)

    # Add global flags to each command
    for arg in [arg_templates.stacktrace, arg_templates.log_level]:
        parser.add_argument(*arg['flags'], **arg['parameters'])

    for arg in cmd.arguments:
        parser.add_argument(*arg['flags'], **arg['parameters'])

    args = vars(parser.parse_args())
    log_level = args.pop('log_level', 'INFO')
    stacktrace = args.pop('stacktrace', False)

    _execute_command(cmd.runscript, stacktrace=stacktrace, log_level=log_level, **args)