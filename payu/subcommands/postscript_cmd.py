# coding: utf-8

# Standard Library
import os

# Local
from payu import cli
from payu.experiment import Experiment
from payu.laboratory import Laboratory
import payu.subcommands.args as args
from payu.fsops import read_config
import payu.errors as errors


title = 'postscript'
parameters = {'description': 'Run postscript commands provided by the user in config.yaml'}

arguments = [args.model, args.config, args.laboratory, args.initial, args.dry_run]

            
def submit_postscript(counter, depends_on=None, config=None):
    """ Submit postprocessing script if configured in config.yaml. Return the job id of the postscript job"""
    try:
        job_id = runcmd(
            init_run=counter,
            dry_run=False,
            depends_on=depends_on
            )
    except Exception as e:
        raise errors.PayuRuntimeError(f"Failed to submit postscript job: {e}")
    return job_id


def runcmd(model_type=None, config_path=None, init_run=None, lab_path=None, dry_run=False, depends_on=None):
    """Submit the postscript job via PBS/scheduler"""
    
    pbs_config = read_config(config_path)

    postscript = pbs_config.get('postscript', {})
    if not postscript:
        print("No postscript commands found in config.yaml. Skipping postscript submission.")
        return None

    # Initialise experiment to determine archive path and run number (which is needed to write job file)
    lab = Laboratory(model_type, config_path, lab_path)
    expt = Experiment(lab)
    expt.set_counters(keep_run_number=True)
    
    # Submit through HPCpy
    # Job name is set to "payu_postscript"
    postscript_job = cli.submit_job(
                        script = os.path.expandvars(postscript),  # Expand any environment variables in the postscript command
                        config={"scheduler": expt.scheduler_name},
                        vars=expt.set_userscript_env_vars(),
                        expt=expt,
                        current_run=int(init_run) if init_run else None,
                        type="postscript",
                        dry_run=dry_run,
                        depends_on=depends_on,
                        postscript=True,
                        )

    return postscript_job

runscript = runcmd