# coding: utf-8

# Standard Library
import argparse
import os
from pathlib import Path
import shutil

# Local
from payu import cli
from payu.experiment import Experiment
from payu.laboratory import Laboratory
import payu.subcommands.args as args
from payu.telemetry import record_run
from payu import fsops
from payu.schedulers.pbs import get_job_info_json

title = 'collate'
parameters = {'description': 'Collate tiled output into single output files'}

arguments = [args.model, args.config, args.initial, args.laboratory,
             args.dir_path]


def runcmd(model_type, config_path, init_run, lab_path, dir_path):

    pbs_config = fsops.read_config(config_path)
    pbs_vars = cli.set_env_vars(init_run=init_run,
                                lab_path=lab_path,
                                dir_path=dir_path)

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
    if init_run is None:
        # Get the latest run number from the restart/output folder numbering
        # and set it as the run number to write job file
        expt.set_counters(keep_run_number=True)
        init_run = expt.counter

    print(f"init_run: {init_run}")
    # Submit the collation job and write queue job file
    cli.submit_job('payu-collate', pbs_config, pbs_vars, expt=expt, current_run = init_run, type='collate')

    


def runscript():

    parser = argparse.ArgumentParser()
    for arg in arguments:
        parser.add_argument(*arg['flags'], **arg['parameters'])

    run_args = parser.parse_args()

    pbs_vars = cli.set_env_vars(init_run=run_args.init_run,
                                lab_path=run_args.lab_path,
                                dir_path=run_args.dir_path)

    for var in pbs_vars:
        os.environ[var] = str(pbs_vars[var])

    lab = Laboratory(run_args.model_type,
                     run_args.config_path,
                     run_args.lab_path)
    expt = Experiment(lab)
    try:
        # Collate the model output
        # If collation succeeds, then collate_status is set to 0
        expt.collate()
        expt.postprocess()
        collate_status = 0
    except:
        # If collation fails, then collate_status is set to 1
        collate_status = 1
        raise
    finally:
        # Record collation job information into job file
        job_file_path = expt.set_job_file(type='collate')

        # Record the collation status (duration time and success/failure) in the job file
        record_run(
            timings=expt.timings,
            scheduler=expt.scheduler,
            run_status=collate_status,
            config=expt.config,
            file_path=job_file_path,
            archive_path=Path(expt.archive_path),
            type="collate",
            run_info_label = "payu_collate_status",
            stage="exited"
        )
