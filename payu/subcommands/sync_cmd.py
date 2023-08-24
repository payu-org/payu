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

arguments = [args.model, args.config, args.initial, args.laboratory,
             args.dir_path, args.sync_path, args.sync_restarts]

def runcmd(model_type, config_path, init_run, lab_path, dir_path, sync_path, sync_restarts):

    pbs_config = fsops.read_config(config_path)

    #TODO: Setting script args as env variables vs appending them at the end of qsub call after payu-sync? 
    # Went with setting env variables as thats whats done elsewhere
    # Though with PBSPro can pass arguments after script name and then could be able to pass arguments directly to expt.sync()?
    pbs_vars = cli.set_env_vars(init_run=init_run,
                                lab_path=lab_path,
                                dir_path=dir_path,
                                sync_path=sync_path,
                                sync_restarts=sync_restarts)

    sync_config = pbs_config.get('sync', {})
    
    default_ncpus = 1
    default_queue = 'copyq'
    default_mem = '2GB'

    pbs_config['queue'] = sync_config.get('queue', default_queue)

    pbs_config['ncpus'] = sync_config.get('ncpus', default_ncpus)

    pbs_config['mem'] = sync_config.get('mem', default_mem)

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

    # Replace (or remove) walltime
    walltime = sync_config.get('walltime')
    if walltime:
        pbs_config['walltime'] = walltime
    else:
        # Remove the model walltime if set
        try:
            pbs_config.pop('walltime')
        except KeyError:
            pass

    # Disable hyperthreading
    qsub_flags = []
    iflags = iter(pbs_config.get('qsub_flags', '').split())
    for flag in iflags:
        if flag == '-l':
            try:
                flag += ' ' + next(iflags)
            except StopIteration:
                break

        if 'hyperthread' not in flag:
            qsub_flags.append(flag)

    pbs_config['qsub_flags'] = ' '.join(qsub_flags)

    cli.submit_job('payu-sync', pbs_config, pbs_vars)


def runscript():
    # Currently these run_args are only ever set running `payu-sync` with args directly rather than `payu sync`
    parser = argparse.ArgumentParser()
    for arg in arguments:
        parser.add_argument(*arg['flags'], **arg['parameters'])

    run_args = parser.parse_args()

    pbs_vars = cli.set_env_vars(init_run=run_args.init_run,
                                lab_path=run_args.lab_path,
                                dir_path=run_args.dir_path,
                                sync_path=run_args.sync_path,
                                sync_restarts=run_args.sync_restarts)

    for var in pbs_vars:
        os.environ[var] = str(pbs_vars[var])
    
    lab = Laboratory(run_args.model_type,
                     run_args.config_path,
                     run_args.lab_path)
    expt = Experiment(lab)

    expt.sync()
