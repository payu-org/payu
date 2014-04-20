# coding: utf-8

# Standard Library
import argparse
import errno
import os
import sys

# Extensions
import yaml

# Local
from modelindex import index as supported_models
from subcommands import list_cmd, init_cmd

# Default configuration
default_config_filename = 'config.yaml'

#---
def parse():

    subcmds = [list_cmd, init_cmd]

#    subcmd = {'list': list_cmd,
#              'init': payu_init,
#              'build': payu_build,
#              'setup': payu_setup,
#              'run': payu_run,
#              'archive': payu_archive,
#              'collate': payu_collate,
#              'sweep': payu_sweep,
#             }

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    for cmd in subcmds:
        cmd_parser = subparsers.add_parser(cmd.title, **cmd.parameters)
        cmd_parser.set_defaults(run_cmd=cmd.runcmd)

        for arg in cmd.arguments:
            cmd_parser.add_argument(*arg['flags'], **arg['parameters'])

        # Add subcommand arguments
        ## TODO: Organise this better
        #if not cmd_name == 'list':
        #    cmd_parser.add_argument('--model', '-m',
        #                            action='store',
        #                            dest='model_type',
        #                            default=None,
        #                            help='Select model type')

        #    cmd_parser.add_argument('--config', '-c',
        #                            action='store',
        #                            dest='config_path',
        #                            default=None,
        #                            help='Configuration file path')

        #if cmd_name in ('setup', 'run', 'archive', 'collate'):

        #    cmd_parser.add_argument('--initial', '-i',
        #                            action='store',
        #                            dest='init_run')

        #    cmd_parser.add_argument('--nruns', '-n',
        #                            action='store',
        #                            dest='n_runs')

        #if cmd_name == 'sweep':
        #    cmd_parser.add_argument('--hard',
        #                            action='store_true',
        #                            dest='hard_sweep')

    # Display help if no arguments are provided
    if len(sys.argv) == 1:
        parser.print_help()
    else:
        args = vars(parser.parse_args())
        run_cmd = args.pop('run_cmd')
        run_cmd(**args)


#---
def payu_build():
    pass


#---
def payu_setup():
    pass


#---
def payu_run():
    pass


#---
def payu_archive():
    pass


#---
def payu_collate():
    pass


#---
def payu_sweep():
    pass


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
