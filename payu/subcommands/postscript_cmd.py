# coding: utf-8

# Standard Library
from pathlib import Path

# Local
from payu import cli
from payu import envmod
from payu.experiment import Experiment
from payu.laboratory import Laboratory
import payu.subcommands.args as args
from payu.fsops import read_config
from payu.telemetry import (
    read_job_file, 
    update_job_file,
)

title = 'postscript'
parameters = {'description': 'Run postscript commands provided by the user in config.yaml'}

arguments = [args.model, args.config, args.laboratory, args.initial, args.dry_run]

            
def submit_postscript(expt, depends_on=None):
    """ Submit postprocessing script if configured in config.yaml. Return the job id of the postscript job"""
    job_id = runcmd(
        model_type=expt.lab.model_type,
        config_path=expt.config_path,
        init_run=expt.counter,
        lab_path=expt.lab.basepath,
        dry_run=False,
        depends_on=depends_on
    )
    return job_id


def runcmd(model_type, config_path, init_run, lab_path, dry_run=False, depends_on=None):
    """Submit the postscript job via PBS/scheduler"""
    
    pbs_config = read_config(config_path)

    postscript = pbs_config.get('postscript', {})
    if not postscript:
        print("No postscript commands found in config.yaml. Skipping postscript submission.")
        return None

    # Initialise experiment to determine archive path and run number (which is needed to write job file)
    lab = Laboratory(model_type, config_path, lab_path)
    expt = Experiment(lab)

    expt.set_userscript_env_vars()
    envmod.setup()
    envmod.module('load', 'pbs')
    
    # Submit through HPCpy
    # Job name is set to "payu_postscript"
    postscript_job = cli.submit_job(
                        script = postscript, 
                        config={"scheduler": expt.scheduler_name},
                        expt=expt,
                        current_run=int(init_run) if init_run else None,
                        type="postscript",
                        dry_run=dry_run,
                        depends_on=depends_on,
                        postscript=True
                        )

    return postscript_job

runscript = runcmd