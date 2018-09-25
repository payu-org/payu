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
             args.laboratory, args.dir_path]


def runcmd(model_type, config_path, init_run, n_runs, lab_path, dir_path):

    pbs_config = cli.get_config(config_path)
    pbs_vars = cli.set_env_vars(init_run, n_runs, lab_path, dir_path)

    collate_conf = pbs_config.get('collate',{})

    # Cycle through old collate config and convert to newer dict format
    if type(collate_conf) is bool:
        collate_conf = {'run' : collate_conf}
        for key in ['queue','ncpus','walltime','mem']:
            oldkey = "collate_{}".format(key)
            print("Use of this key is deprecated: {}. Use collate dictionary and subkey {}".format(oldkey,key))
            if oldkey in pbs_config:
                collate_conf[key] = pbs_config[oldkey]

    # The mpi flag implies using mppnccombine-fast
    mpi = collate_conf.get('mpi',False)

    default_ncpus = 1
    default_queue = 'copyq'
    if mpi:
        default_ncpus = 2
        default_queue = 'express'

    collate_queue = collate_conf.get('queue', default_queue)
    pbs_config['queue'] = collate_queue

    n_cpus_request = collate_conf.get('ncpus', default_ncpus)
    pbs_config['ncpus'] = n_cpus_request

    # Modify jobname
    if 'jobname' in pbs_config:
        pbs_config['jobname'] = pbs_config['jobname'][:13] + '_c'
    else:
        if not dir_path:
            dpath = os.path.basename(os.getcwd())
        else:
            dpath = dir_path

        pbs_config['jobname'] = os.path.normpath(dpath[:13]) + '_c'

    # Replace (or remove) walltime
    collate_walltime = collate_conf.get('walltime')
    if collate_walltime:
        pbs_config['walltime'] = collate_walltime
    else:
        # Remove the model walltime if set
        try:
            pbs_config.pop('walltime')
        except KeyError:
            pass

    # TODO: calcualte default memory request based on ncpus and platform
    pbs_config['mem'] = collate_conf.get('mem','2GB')

    # Disable hyperthreading
    qsub_flags = []
    iflags = iter(pbs_config.get('qsub_flags', '').split())
    for flag in iflags:
        if flag == '-l':
            try:
                flag += ' ' + next(iflags)
            except StopIteration:
                break

        # TODO: Test the sequence, not just existence of characters in string
        if 'hyperthread' not in flag:
            qsub_flags.append(flag)

    pbs_config['qsub_flags'] = ' '.join(qsub_flags)

    cli.submit_job('payu-collate', pbs_config, pbs_vars)


def runscript():

    parser = argparse.ArgumentParser()
    for arg in arguments:
        parser.add_argument(*arg['flags'], **arg['parameters'])

    run_args = parser.parse_args()

    pbs_vars = cli.set_env_vars(run_args.init_run, run_args.n_runs,
                                run_args.lab_path, run_args.dir_path)

    for var in pbs_vars:
        os.environ[var] = str(pbs_vars[var])

    lab = Laboratory(run_args.model_type, run_args.config_path,
                     run_args.lab_path)
    expt = Experiment(lab)
    expt.collate()
    if expt.postscript:
        expt.postprocess()
