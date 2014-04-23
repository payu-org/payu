# coding: utf-8

# Force Python version
from payu import reversion
reversion.repython('2.7.6', __file__)

# Standard Library
import os

# Local
import args
import payu
from payu import cli
from payu.experiment import Experiment

title = 'collate'
parameters = {'description': 'Collate tiled output into single output files'}

arguments = [args.model, args.config, args.initial, args.nruns]


#---
def runcmd(model_type, config_path, init_run, n_runs):

    pbs_config = cli.get_config(config_path)
    pbs_vars = cli.get_env_vars(init_run, n_runs)

    collate_queue = pbs_config.get('collate_queue', 'copyq')
    pbs_config['queue'] = collate_queue

    # Collation jobs are (currently) serial
    pbs_config['ncpus'] = 1

    # Modify jobname
    pbs_config['jobname'] = pbs_config['jobname'][:13] + '_c'

    # Replace (or remove) walltime
    collate_walltime = pbs_config.get('collate_walltime')
    if collate_walltime:
        pbs_config['walltime'] = collate_walltime
    else:
        # Remove the model walltime if set
        try:
            pbs_config.pop('walltime')
        except KeyError:
            pass

    # Replace (or remove) memory request
    collate_mem = pbs_config.get('collate_mem')
    if collate_mem:
        pbs_config['mem'] = collate_mem
    else:
        # Remove the model memory request if set
        try:
            pbs_config.pop('mem')
        except KeyError:
            pass

    payu_path = os.path.dirname(payu.__file__)
    collate_script = os.path.join(payu_path, 'bin', 'payu-collate')
    cli.submit_job(collate_script, pbs_config, pbs_vars)


#---
def runscript():
    expt = Experiment()
    expt.collate()

    if expt.postscript:
        expt.postprocess()
