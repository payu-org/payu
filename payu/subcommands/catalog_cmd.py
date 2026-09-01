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
import payu.errors as errors

title = 'catalog'
parameters = {'description': 'Generate an intake-esm datastore for the '
                              'experiment output'}

arguments = [args.model, args.config, args.initial, args.laboratory,
             args.dir_path, args.dry_run]

def submit_catalog(counter, depends_on=None, config=None):
    """ Submit the catalog job by calling runcmd.
    Return the job id of the catalog job"""
    try:
        job_id = runcmd(
            init_run=counter,
            dry_run=False,
            depends_on=depends_on,
            )

    except Exception as e:
        raise errors.PayuRuntimeError(f"Failed to submit catalog job: {e}")
    return job_id


def runcmd(model_type=None, config_path=None, init_run=None, lab_path=None, dir_path=None, 
           dry_run=False, depends_on=None):

    pbs_config = fsops.read_config(config_path)

    pbs_vars = cli.set_env_vars(init_run=init_run,
                                lab_path=lab_path,
                                dir_path=dir_path)

    catalog_config = pbs_config.get('catalog', {})

    default_ncpus = 104
    default_queue = 'normalsr'
    default_mem = '500GB'
    default_walltime = '01:00:00'

    pbs_config['queue'] = catalog_config.get('queue', default_queue)

    pbs_config['ncpus'] = catalog_config.get('ncpus', default_ncpus)

    pbs_config['mem'] = catalog_config.get('mem', default_mem)

    pbs_config['walltime'] = catalog_config.get('walltime', default_walltime)

    catalog_jobname = catalog_config.get('jobname')
    if not catalog_jobname:
        pbs_jobname = pbs_config.get('jobname')
        if not pbs_jobname:
            if dir_path and os.path.isdir(dir_path):
                pbs_jobname = os.path.basename(dir_path)
            else:
                pbs_jobname = os.path.basename(os.getcwd())

        catalog_jobname = pbs_jobname[:13] + '_i'

    pbs_config['jobname'] = catalog_jobname[:15]

    pbs_config['qsub_flags'] = catalog_config.get('qsub_flags', '')

    # Submit PBS job with expt = None so no job file is written
    job_id = cli.submit_job('payu-catalog', pbs_config, pbs_vars, expt=None,
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

    expt.make_datastore()
