# coding: utf-8

# Model type selection
model = {
    'flags': ('--model', '-m'),
    'parameters': {
        'action':   'store',
        'dest':     'model_type',
        'default':  None,
        'help':     'Model type'
    }
}


# Configuration file
config = {
    'flags': ('--config', '-c'),
    'parameters': {
        'action':   'store',
        'dest':     'config_path',
        'default':  None,
        'help':     'Configuration file path',
    }
}


# Initial run counter
initial = {
    'flags': ('--initial', '-i'),
    'parameters': {
        'action':   'store',
        'dest':     'init_run',
        'default':  None,
        'help':     'Starting run counter',
    }
}


# Number of runs.
nruns = {
    'flags': ('--nruns', '-n'),
    'parameters': {
        'action':   'store',
        'dest':     'n_runs',
        'default':  None,
        'help':     'Number of successive experiments ro run',
    }
}


# Laboratory path
laboratory = {
    'flags': ('--laboratory', '--lab', '-l'),
    'parameters': {
        'action':   'store',
        'dest':     'lab_path',
        'default':  None,
        'help':     'The laboratory, this will over-ride the \
                     value given in config.yaml',
    }
}


force_archive = {
    'flags': ('--archive',),
    'parameters': {
        'action':   'store_true',
        'dest':     'force_archive',
        'help':     'Create archive directory during setup',
    }
}


hard_sweep = {
    'flags': ('--hard',),
    'parameters': {
        'action':   'store_true',
        'dest':     'hard_sweep',
        'help':     'Delete archived output',
    }
}

# Explicitly set output_path
dir_path = {
    'flags': ('--directory', '--dir', '-d'),
    'parameters': {
        'action':   'store',
        'dest':     'dir_path',
        'default':  None,
        'help':     'The output directory, this will over-ride the \
                     directory determined from current run number',
    }
}

# Specify a reproducible run
reproduce = {
    'flags': ('--reproduce', '--repro', '-r'),
    'parameters': {
        'action':   'store_true',
        'dest':     'reproduce',
        'default':  False,
        'help':     'Only run if manifests are correct',
    }
}


# Force run to proceed despite existing directories
force = {
    'flags': ('--force', '-f'),
    'parameters': {
        'action':   'store_true',
        'dest':     'force',
        'default':  False,
        'help':     'Force run to proceed, overwriting existing directories',
    }
}

# Force restarts to be pruned despite changes to configuration
force_prune_restarts = {
    'flags': ('--force-prune-restarts', '-F'),
    'parameters': {
        'action':   'store_true',
        'dest':     'force_prune_restarts',
        'default':  False,
        'help':     'Force outdated restart directories to be pruned during \
                    archive, ignoring changes made to configuration.',
    }
}

# Flag for syncing all restarts
sync_restarts = {
    'flags': {'--sync-restarts'},
    'parameters': {
        'action':   'store_true',
        'dest':     'sync_restarts',
        'default':  False,
        'help':     'Sync all restarts in archive to remote directory.',
    }
}

# Flag for ignoring the latest outputs during syncing
sync_ignore_last = {
    'flags': {'--sync-ignore-last'},
    'parameters': {
        'action':   'store_true',
        'dest':     'sync_ignore_last',
        'default':  False,
        'help':     'Ignore the latest outputs and restarts in archive during \
                     syncing.',
    }
}
