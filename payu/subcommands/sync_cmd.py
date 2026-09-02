# coding: utf-8

# Standard Library
import argparse
import os
from pathlib import Path

# Local
from payu import cli
from payu.experiment import Experiment
from payu.laboratory import Laboratory
import payu.subcommands.args as args
from payu.fsops import read_config
from payu.telemetry import record_run
import payu.errors as errors

title = 'sync'
parameters = {'description': 'Sync model output to a remote directory'}

arguments = [args.model, args.config, args.initial, args.laboratory, args.dir_path,
             args.sync_restarts, args.sync_ignore_last, args.dry_run]

def submit_sync(counter, depends_on=None, config=None):
    """ Submit the sync job by calling runcmd.
    Return the job id of the sync job"""
    sync_config = config.get('sync', {})
    try:
        job_id = runcmd(
            init_run=counter,
            sync_restarts = sync_config.get('restarts', False),
            sync_ignore_last = sync_config.get('ignore_last', False),
            depends_on=depends_on,
            )

    except Exception as e:
        raise errors.PayuRuntimeError(f"Failed to submit sync job: {e}")
    return job_id


def runcmd(model_type=None, config_path=None, init_run=None, lab_path=None, dir_path=None, 
           sync_restarts=None, sync_ignore_last=None, dry_run=False, depends_on=None):

    pbs_config = read_config(config_path)

    pbs_vars = cli.set_env_vars(init_run=init_run,
                                lab_path=lab_path,
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

    # Initialise experiment to determine archive path and run number (which is needed to write job file)
    lab = Laboratory(model_type, config_path, lab_path)
    expt = Experiment(lab)

    # Submit PBS job with expt = None so no job file is written
    job_id = cli.submit_job('payu-sync', pbs_config, pbs_vars, expt=expt, 
                   current_run=int(init_run) if init_run is not None else None, type='sync',
                   dry_run=dry_run, depends_on=depends_on)
    return job_id


def runscript(**run_args):
    run_args = argparse.Namespace(**run_args)
    
    pbs_vars = cli.set_env_vars(init_run=run_args.init_run,
                                lab_path=run_args.lab_path,
                                dir_path=run_args.dir_path,
                                sync_restarts=run_args.sync_restarts,
                                sync_ignore_last=run_args.sync_ignore_last)

    for var in pbs_vars:
        os.environ[var] = str(pbs_vars[var])

    lab = Laboratory(run_args.model_type,
                     run_args.config_path,
                     run_args.lab_path)
    expt = Experiment(lab)
    # Set the counters to keep the run number for sync job file
    expt.set_counters(keep_run_number=True)

    try:
        expt.sync()
        sync_status = 0
    except:
        sync_status = 1
        raise
    finally:
        # Record sync job information into job file
        job_file_path = expt.get_job_file(type='sync')

        # Record the sync status (duration time and success/failure) in the job file
        record_run(
            timings=expt.timings,
            scheduler=expt.scheduler,
            status=sync_status,
            config=expt.config,
            file_path=job_file_path,
            archive_path=Path(expt.archive_path),
            type="sync",
            stage="exited"
        )
