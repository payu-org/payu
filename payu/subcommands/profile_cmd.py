# coding: utf-8

# Standard Library
import argparse
import os

# Local
from payu import cli
from payu.experiment import Experiment
from payu.laboratory import Laboratory
from payu import fsops
import payu.subcommands.args as args

title = 'profile'
parameters = {'description': 'Postprocess any profiling output'}

arguments = [args.model, args.config, args.initial, args.nruns,
             args.laboratory]


def runcmd(model_type, config_path, init_run, n_runs, lab_path):

    pbs_config = fsops.read_config(config_path)
    pbs_vars = cli.set_env_vars(init_run=init_run,
                                n_runs=n_runs,
                                lab_path=lab_path)

    pbs_config['queue'] = pbs_config.get('profile_queue', 'normal')

    # Collation jobs are (currently) serial
    pbs_config['ncpus'] = 1

    # Modify jobname
    pbs_config['jobname'] = pbs_config['jobname'][:13] + '_p'

    # Replace (or remove) walltime
    profile_walltime = pbs_config.get('profile_walltime')
    if profile_walltime:
        pbs_config['walltime'] = profile_walltime
    else:
        # Remove the model walltime if set
        try:
            pbs_config.pop('walltime')
        except KeyError:
            pass

    # Replace (or remove) memory request
    profile_mem = pbs_config.get('profile_mem')
    if profile_mem:
        pbs_config['mem'] = profile_mem
    else:
        # Remove the model memory request if set
        try:
            pbs_config.pop('mem')
        except KeyError:
            pass

    # Disable hyperthreading
    qsub_flags = []
    for flag in pbs_config.get('qsub_flags', '').split():
        if 'hyperthread' not in flag:
            qsub_flags.append(flag)
    pbs_config['qsub_flags'] = ' '.join(qsub_flags)

    cli.submit_job('payu-profile', pbs_config, pbs_vars)


def runscript():

    parser = argparse.ArgumentParser()
    for arg in arguments:
        parser.add_argument(*arg['flags'], **arg['parameters'])

    run_args = parser.parse_args()

    pbs_vars = cli.set_env_vars(init_run=run_args.init_run,
                                n_runs=run_args.n_runs)
    for var in pbs_vars:
        os.environ[var] = str(pbs_vars[var])

    lab = Laboratory(run_args.model_type, run_args.config_path,
                     run_args.lab_path)
    expt = Experiment(lab)

    expt.profile()
