# coding: utf-8

# Local
from payu.modelindex import index as model_index


# Configuration
title = 'init'
parameters = {'description': 'Initialize the model laboratory'}


# Command line arguments
model_arg = {'flags':
                ('--model', '-m'),
             'parameters':
                {'action':  'store',
                 'dest':    'model_type',
                 'default': None,
                 'help':    'Model type'}
            }

config_arg = {'flags':
                ('--config', '-c'),
             'parameters':
                {'action':  'store',
                 'dest':    'config_path',
                 'default': None,
                 'help':    'Configuration file path'}
            }

arguments = [model_arg, config_arg]


# Subcommand action
def runcmd(model_type, config_path):
    print('welcome to init')
