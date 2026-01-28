# Standard imports
import os
import argparse
from pathlib import Path

import sys
import logging

# Local imports
from payu import cli
from payu.experiment import Experiment
from payu.laboratory import Laboratory
import payu.subcommands.args as args
from payu import fsops
from payu.manifest import Manifest
from payu.telemetry import write_queued_job_file, record_run
from payu.schedulers.pbs import PBS

title = 'run'
parameters = {'description': 'Run the model experiment'}

arguments = [args.model, args.config, args.initial, args.nruns,
             args.laboratory, args.reproduce, args.force,
             args.force_prune_restarts]

logger = logging.getLogger(__name__)


def validate_platform_node(platform, queue, get_queue_node_shape):
    """
    Validate platform node setting against the queue node shape for the active scheduler.
    """
    if not platform:
        return

    cpu, mem = get_queue_node_shape(queue)

    if platform.get("nodesize") != cpu:
        raise ValueError(
            f"platform.nodesize must be {cpu} for queue '{queue}' in config.yaml"
        )
    if "nodemem" in platform and platform.get("nodemem") > mem:
        raise ValueError(
            f"platform.nodemem {platform.get('nodemem')}GB exceeds queue max {mem}GB for queue '{queue}' in config.yaml"
        )


def runcmd(model_type, config_path, init_run, n_runs, lab_path,
           reproduce=False, force=False, force_prune_restarts=False):
    # Get job submission configuration
    pbs_config = fsops.read_config(config_path)
    pbs_vars = cli.set_env_vars(init_run=init_run,
                                n_runs=n_runs,
                                lab_path=lab_path,
                                reproduce=reproduce,
                                force=force,
                                force_prune_restarts=force_prune_restarts)

    # Initialise Experiment early so we can detect scheduler
    # Run experiment initialisation to update metadata,
    # and determine the run counter and uuid before job submission
    lab = Laboratory(model_type, config_path, lab_path)
    expt = Experiment(lab, reproduce=reproduce, force=force)

    # Set the queue
    # NOTE: Maybe force all jobs on the normal queue
    # Is there a reason to force all jobs onto a specific queue?
    queue = pbs_config.get("queue", "normal")

    platform = pbs_config.get("platform", {})

    if expt.scheduler_name == 'pbs':
        cpu_q, mem_q = PBS.get_queue_node_shape(queue)

        if platform:
            validate_platform_node(platform, queue, PBS.get_queue_node_shape)

        max_cpus_per_node = platform.get("nodesize", cpu_q)
        max_ram_per_node = platform.get("nodemem", mem_q)

    elif expt.scheduler_name == 'slurm':
        # TODO for non-PBS schedulers, such as Sotonix slurm setup on Pawsey
        max_cpus_per_node = 64
        max_ram_per_node = 256  # GB
    else:
        max_cpus_per_node = platform.get("nodesize", 48)
        max_ram_per_node = platform.get("nodemem", 192)

    # Adjust the CPUs for any model-specific settings
    # TODO: Incorporate this into the Model driver
    mask_table = pbs_config.get('mask_table', False)
    if mask_table:

        # Check if a mask table exists
        # TODO: Is control_path defined at this stage?
        mask_table_fname = None
        for fname in os.listdir(os.curdir):
            if fname.startswith('mask_table'):
                mask_table_fname = fname

        # TODO TODO

    if 'ncpureq' in pbs_config:
        # Hard override of CPU request
        n_cpus_request = pbs_config.get('ncpureq')

    elif 'submodels' in pbs_config and 'ncpus' not in pbs_config:
        # Increase the cpu request to match a complete node

        n_cpus_request = 0
        submodel_configs = pbs_config['submodels']
        for model_config in submodel_configs:
            n_cpus_request += model_config.get('ncpus', 0)

    else:
        n_cpus_request = pbs_config.get('ncpus', 1)

    n_cpus = n_cpus_request
    n_cpus_per_node = pbs_config.get('npernode', max_cpus_per_node)

    assert n_cpus_per_node <= max_cpus_per_node

    node_misalignment = n_cpus % max_cpus_per_node != 0
    node_increase = n_cpus_per_node < max_cpus_per_node

    # Increase the CPUs to accommodate the cpu-per-node request
    if n_cpus > max_cpus_per_node and (node_increase or node_misalignment):

        # Number of requested nodes
        n_nodes = 1 + (n_cpus - 1) // n_cpus_per_node
        n_cpu_request = max_cpus_per_node * n_nodes
        n_inert_cpus = n_cpu_request - n_cpus

        print('payu: warning: Job request includes {n} unused CPUs.'
              ''.format(n=n_inert_cpus))

        # Increase CPU request to match the effective node request
        n_cpus = max_cpus_per_node * n_nodes

        # Update the ncpus field in the config
        if n_cpus != n_cpus_request:
            print('payu: warning: CPU request increased from {n_req} to {n}'
                  ''.format(n_req=n_cpus_request, n=n_cpus))

    # Update the (possibly unchanged) value of ncpus
    pbs_config['ncpus'] = n_cpus

    # Validate walltime against queue limits
    walltime = pbs_config.get('walltime')
    print(walltime)
    if walltime:
        requested_hours = PBS.parse_walltime(walltime)
        limit = PBS.get_queue_walltime_hours(queue, n_cpus)
        if limit is not None and requested_hours > limit:
            raise ValueError(
                f"Requested walltime of {requested_hours} hours exceeds "
                f"the limit of {limit} hours for queue '{queue}' with "
                f"{n_cpus} CPUs."
            )

    # Set memory to use the complete node if unspecified
    pbs_mem = pbs_config.get('mem')
    if not pbs_mem:
        if n_cpus > max_cpus_per_node:
            pbs_mem = (n_cpus // max_cpus_per_node) * max_ram_per_node
        else:
            pbs_mem = n_cpus * (max_ram_per_node // max_cpus_per_node)

        pbs_config['mem'] = '{0}GB'.format(pbs_mem)

    # Check if the work directory exists, then show warning to the user.
    if os.path.exists(expt.work_path) and not expt.force:
        logger.error('Work path already exists. Please use `payu sweep` or use `payu run -f`.')

        # Return error code.
        sys.exit(1)

    job_id = cli.submit_job('payu-run', pbs_config, pbs_vars)

    current_run = init_run if init_run is not None else expt.counter

    # This could be done as part of submit_job eventually, but for now
    # it's only used by the run command.
    write_queued_job_file(
        archive_path=Path(expt.archive_path),
        job_id=job_id,
        type='run',
        scheduler=expt.scheduler,
        metadata=expt.metadata,
        current_run=current_run,
    )


def runscript():
    parser = argparse.ArgumentParser()
    for arg in arguments:
        parser.add_argument(*arg['flags'], **arg['parameters'])

    run_args = parser.parse_args()

    lab = Laboratory(run_args.model_type, run_args.config_path,
                     run_args.lab_path)

    expt = Experiment(lab, reproduce=run_args.reproduce, force=run_args.force)

    n_runs_per_submit = expt.config.get('runspersub', 1)
    subrun = 1

    while True:

        print('nruns: {0} nruns_per_submit: {1} subrun: {2}'
              ''.format(expt.n_runs, n_runs_per_submit, subrun))
        # Set job filepath for the payu run
        expt.set_job_file(type='run')
        try:
            expt.setup()
            expt.run()
            expt.archive(force_prune_restarts=run_args.force_prune_restarts)
            run_status = 0
        except:
            run_status = 1
            raise
        finally:
            # Record job information for experiment run
            record_run(
                timings=expt.timings,
                scheduler=expt.scheduler,
                run_status=run_status,
                config=expt.config,
                file_path=expt.job_file,
                archive_path=Path(expt.archive_path),
            )

        # Finished runs
        if expt.n_runs == 0:
            break

        # Check if still looping
        if n_runs_per_submit > 1 and subrun < n_runs_per_submit:
            # Re-initialise the experiment method timings
            expt.init_timings()
            # Need to manually increment the run counter if still looping
            expt.counter += 1
            # Re-initialize manifest: important to clear out restart manifest
            # note no attempt to preserve reproduce flag, it makes no sense
            # to on subsequent runs
            expt.manifest = Manifest(expt.config.get('manifest', {}),
                                     reproduce=False)
            expt.set_output_paths()
            # Does not make sense to reproduce a multiple run.
            # Take care of this with argument processing?
            expt.reproduce = False
        else:
            break

        subrun += 1

    if expt.n_runs > 0:
        expt.resubmit()
