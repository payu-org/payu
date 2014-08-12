# coding: utf-8

# Standard Library
import argparse
import os

# Local
import payu
from payu import cli
from payu.experiment import Experiment
from payu.laboratory import Laboratory
import payu.subcommands.args as args

title = 'collate'
parameters = {'description': 'Collate tiled output into single output files'}

arguments = [args.model, args.config, args.initial, args.nruns,
             args.laboratory]

#---
def runcmd(model_type, config_path, init_run, n_runs, lab_path):

    pbs_config = cli.get_config(config_path)
    pbs_vars = cli.set_env_vars(init_run, n_runs, lab_path)

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

    cli.submit_job('payu-collate', pbs_config, pbs_vars)


#---
def runscript():

    parser = argparse.ArgumentParser()
    for arg in arguments:
        parser.add_argument(*arg['flags'], **arg['parameters'])

    run_args = parser.parse_args()

    pbs_vars = cli.set_env_vars(run_args.init_run, run_args.n_runs,
                                run_args.lab_path)
    for var in pbs_vars:
        os.environ[var] = str(pbs_vars[var])

    lab = Laboratory(run_args.model_type, run_args.config_path,
                     run_args.lab_path)
    expt = Experiment(lab)

    expt.collate()
    if expt.postscript:
        expt.postprocess()
