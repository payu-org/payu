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

title = 'addmeta'
parameters = {'description': 'Add metadata to model output files'}

arguments = [args.model, args.config, args.initial, args.laboratory, args.dir_path]

def submit_addmeta(counter, depends_on=None, config=None):
    """ Submit the addmeta job by calling runcmd.
    Return the job id of the addmeta job"""
    try:
        job_id = runcmd(
            init_run=counter,
            depends_on=depends_on,
            )

    except Exception as e:
        raise errors.PayuRuntimeError(f"Failed to submit sync job: {e}")
    return job_id


def runcmd(model_type=None, config_path=None, init_run=None, lab_path=None, dir_path=None, 
           depends_on=None):

    pbs_config = read_config(config_path)

    pbs_vars = cli.set_env_vars(init_run=init_run,
                                lab_path=lab_path,
                                dir_path=dir_path)

    base_dir = os.path.basename(dir_path if dir_path else os.getcwd())

    addmeta_config = pbs_config.get('addmeta', {})

    pbs_config.update({
        'ncpus': 1,
        'queue': 'copyq',
        'mem': '2GB',
        'walltime': '0:30:00',
        'qsub_flags': '',
        'jobname': f'{base_dir[:13]}_a' if dir_path else "addmeta_job",
    })
    pbs_config = pbs_config | addmeta_config.get('pbs', {})

    # Initialise experiment to determine archive path and run number (which is needed to write job file)
    lab = Laboratory(model_type, config_path, lab_path)
    expt = Experiment(lab)

    # Submit PBS job
    job_id = cli.submit_job('payu-addmeta', pbs_config, pbs_vars, expt=expt, 
                   current_run=int(init_run) if init_run is not None else None, type='addmeta',
                   depends_on=depends_on)
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

    # Set the counters to keep the run number for addmeta job file
    expt.set_counters(keep_run_number=True)

    try:
        expt.add_file_metadata()
        status = 0
    except:
        status = 1
        raise
    finally:
        # Record sync job information into job file
        job_file_path = expt.get_job_file(type='addmeta')

        # Record the sync status (duration time and success/failure) in the job file
        record_run(
            timings=expt.timings,
            scheduler=expt.scheduler,
            status=status,
            config=expt.config,
            file_path=job_file_path,
            archive_path=Path(expt.archive_path),
            type="addmeta",
            stage="exited"
        )
