# coding: utf-8

# Model type selection
model = {'flags':
            ('--model', '-m'),
         'parameters':
            {'action':  'store',
             'dest':    'model_type',
             'default': None,
             'help':    'Model type',
            }
        }


# Configuration file
config = {'flags':
            ('--config', '-c'),
          'parameters':
            {'action':  'store',
             'dest':    'config_path',
             'default': None,
             'help':    'Configuration file path',
            }
         }


# Intial run counter
initial = {'flags':
            ('--initial', '-i'),
          'parameters':
            {'action':  'store',
             'dest':    'init_run',
             'default': None,
             'help':    'Starting run counter',
            }
         }


# Number of runs.
nruns = {'flags':
            ('--nruns', '-n'),
          'parameters':
            {'action':  'store',
             'dest':    'n_runs',
             'default': None,
             'help':    'Number of successive experiments ro run',
            }
         }


# Laboratory path
laboratory = {'flags':
                ('--laboratory', '--lab', '-l'),
                'parameters':
                    {'action':  'store',
                     'dest':    'lab_path',
                     'default': None,
                     'help':    'The laboratory, this will over-ride the \
                                 value given in config.yaml',
                    }
             }

hard_sweep = {'flags':
                ('--hard',),
              'parameters':
                {'action':  'store_true',
                 'dest':    'hard_sweep',
                 'help':    'Delete archived output',
                }
             }
