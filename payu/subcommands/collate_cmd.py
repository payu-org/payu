# coding: utf-8

# Standard Library
import argparse
import os
from pathlib import Path
import json

# Local
from payu import cli
from payu.experiment import Experiment
from payu.laboratory import Laboratory
import payu.subcommands.args as args
from payu.telemetry import record_run
from payu.fsops import read_config
import payu.errors as errors

from payu.workflow import Workflow

title = 'collate'
parameters = {'description': 'Collate tiled output into single output files'}

arguments = [args.model, args.config, args.initial, args.laboratory,
             args.dir_path, args.dry_run]

def submit_collate(counter, depends_on=None, config=None):
    """ Submit the collate job by calling runcmd.
    Return the job id of the collate job"""
    try:
        job_id = runcmd(
                init_run=counter,
                depends_on=depends_on,
                exist_workflow=True,
                )
    except Exception as e:
        raise errors.PayuRuntimeError(f"Failed to submit collate job: {e}")
    return job_id


def runcmd(model_type=None, config_path=None, init_run=None, 
           lab_path=None, dir_path=None, dry_run=False, depends_on=None, 
           exist_workflow=False):

    pbs_config = read_config(config_path)
    pbs_vars = cli.set_env_vars(init_run=init_run,
                                lab_path=lab_path,
                                dir_path=dir_path,
                                exist_workflow=exist_workflow)

    collate_config = pbs_config.get('collate', {})

    # The mpi flag implies using mppnccombine-fast
    mpi = collate_config.get('mpi', False)

    default_ncpus = 1
    default_queue = 'copyq'
    if mpi:
        default_ncpus = 2
        default_queue = 'express'

    collate_queue = collate_config.get('queue', default_queue)
    pbs_config['queue'] = collate_queue

    n_cpus_request = collate_config.get('ncpus', default_ncpus)
    pbs_config['ncpus'] = n_cpus_request

    collate_jobname = collate_config.get('jobname')
    if not collate_jobname:
        pbs_jobname = pbs_config.get('jobname')
        if not pbs_jobname:
            if dir_path and os.path.isdir(dir_path):
                pbs_jobname = os.path.basename(dir_path)
            else:
                pbs_jobname = os.path.basename(os.getcwd())

        collate_jobname = pbs_jobname[:13] + '_c'

    # NOTE: Better to construct `collate_config` to pass to `submit_job`
    pbs_config['jobname'] = collate_jobname[:15]

    # Replace (or remove) walltime
    collate_walltime = collate_config.get('walltime')
    if collate_walltime:
        pbs_config['walltime'] = collate_walltime
    else:
        # Remove the model walltime if set
        try:
            pbs_config.pop('walltime')
        except KeyError:
            pass

    # TODO: calcualte default memory request based on ncpus and platform
    pbs_config['mem'] = collate_config.get('mem', '2GB')

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

    # Initialise experiment to determine archive path and run number (which is needed to write job file)
    lab = Laboratory(model_type, config_path, lab_path)
    expt = Experiment(lab)

    # Submit the collation job and write queue job file
    job_id = cli.submit_job('payu-collate', pbs_config, pbs_vars, expt=expt, 
                current_run = int(init_run) if init_run else None, type='collate', 
                dry_run=dry_run, depends_on=depends_on)
    return job_id
    


def runscript(**run_args):
    run_args = argparse.Namespace(**run_args)

    pbs_vars = cli.set_env_vars(init_run=run_args.init_run,
                                lab_path=run_args.lab_path,
                                dir_path=run_args.dir_path)

    for var in pbs_vars:
        os.environ[var] = str(pbs_vars[var])

    lab = Laboratory(run_args.model_type,
                     run_args.config_path,
                     run_args.lab_path)
    expt = Experiment(lab)

    # Initialise the Workflow class to manage the workflow
    workflow = Workflow(expt.config,
                        run_number=expt.counter)
    
    try:
        # Collate the model output
        expt.collate()

        # If collation succeeds, then collate_status is set to 0
        collate_status = 0
        
    except:
        # If collation fails, then collate_status is set to 1
        collate_status = 1

        raise
    
    finally:
        # Record collation job information into job file
        job_file_path = expt.get_job_file(type='collate')

        # Record the collation status (duration time and success/failure) in the job file
        record_run(
            timings=expt.timings,
            scheduler=expt.scheduler,
            status=collate_status,
            config=expt.config,
            file_path=job_file_path,
            archive_path=Path(expt.archive_path),
            type="collate",
            stage="exited"
        )

        # Submit follow-up jobs in the workflow, if payu-collate succeed and not called by payu-run
        exist_workflow = os.environ.get('PAYU_EXIST_WORKFLOW', 'false').lower() == 'true'

        if collate_status == 0 and not exist_workflow:
            workflow.build_workflow()
            workflow.workflow_steps.pop('collate', None)
            workflow.submit_workflow(depends_on=expt.scheduler.get_job_id(short=False))
