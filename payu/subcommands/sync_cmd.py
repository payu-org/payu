# coding: utf-8

# Standard Library
import argparse
import os

# Local
from payu import cli
from payu.experiment import Experiment
from payu.laboratory import Laboratory
import payu.subcommands.args as args
from payu import fsops

title = 'sync'
parameters = {'description': 'Sync model output to a remote directory'}

arguments = [args.model, args.config, args.laboratory, args.dir_path,
             args.sync_restarts, args.sync_ignore_last]


def runcmd(model_type, config_path, lab_path, dir_path, sync_restarts,
           sync_ignore_last):

    pbs_config = fsops.read_config(config_path)

    pbs_vars = cli.set_env_vars(lab_path=lab_path,
                                dir_path=dir_path,
                                sync_restarts=sync_restarts,
                                sync_ignore_last=sync_ignore_last)

    sync_config = pbs_config.get('sync', {})

    default_ncpus = 1
    default_queue = 'copyq'
    default_mem = '2GB'
    default_walltime = '10:00:00'

    pbs_config['queue'] = sync_config.get('queue', default_queue)

    pbs_config['ncpus'] = sync_config.get('ncpus', default_ncpus)

    pbs_config['mem'] = sync_config.get('mem', default_mem)

    pbs_config['walltime'] = sync_config.get('walltime', default_walltime)

    sync_jobname = sync_config.get('jobname')
    if not sync_jobname:
        pbs_jobname = pbs_config.get('jobname')
        if not pbs_jobname:
            if dir_path and os.path.isdir(dir_path):
                pbs_jobname = os.path.basename(dir_path)
            else:
                pbs_jobname = os.path.basename(os.getcwd())

        sync_jobname = pbs_jobname[:13] + '_s'

    pbs_config['jobname'] = sync_jobname[:15]

    pbs_config['qsub_flags'] = sync_config.get('qsub_flags', '')

    cli.submit_job('payu-sync', pbs_config, pbs_vars)


def runscript():
    parser = argparse.ArgumentParser()
    for arg in arguments:
        parser.add_argument(*arg['flags'], **arg['parameters'])

    run_args = parser.parse_args()

    pbs_vars = cli.set_env_vars(lab_path=run_args.lab_path,
                                dir_path=run_args.dir_path,
                                sync_restarts=run_args.sync_restarts,
                                sync_ignore_last=run_args.sync_ignore_last)

    for var in pbs_vars:
        os.environ[var] = str(pbs_vars[var])

    lab = Laboratory(run_args.model_type,
                     run_args.config_path,
                     run_args.lab_path)
    expt = Experiment(lab)

    expt.sync()
