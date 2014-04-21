# coding: utf-8

# Standard Library
import argparse
import errno
import importlib
import os
import pkgutil
import sys

# Extensions
import yaml

# Local
from modelindex import index as supported_models
import subcommands

# Default configuration
default_config_filename = 'config.yaml'

#---
def parse():

    # Build the list of subcommand modules
    modnames = [mod for (_, mod, _)
                in pkgutil.iter_modules(subcommands.__path__,
                                        prefix=subcommands.__name__ + '.')
                if mod.endswith('_cmd')]

    subcmds = [importlib.import_module(mod) for mod in modnames]

    # Construct the subcommand parser
    parser = argparse.ArgumentParser()
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
def get_env_vars(init_run=None, n_runs=None):

    payu_modname = next(mod for mod in os.environ['LOADMODULES'].split(':')
                        if mod.startswith('payu'))
    payu_modpath = next(mod for mod in os.environ['_LMFILES_'].split(':')
                        if payu_modname in mod) 

    payu_env_vars = {'PYTHONPATH': os.environ['PYTHONPATH'],
                     'PAYU_MODULENAME': payu_modname,
                     'PAYU_MODULEPATH': payu_modpath,
                    }

    if init_run:
        payu_env_vars['PAYU_CURRENT_RUN'] = init_run

    if n_runs:
        payu_env_vars['PAYU_N_RUNS'] = n_runs

    return payu_env_vars


#---
def get_config(config_path):

    if not config_path and os.path.isfile(default_config_filename):
        config_path = default_config_filename
 
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
