# coding: utf-8
from contextlib import redirect_stdout
import os
from pathlib import Path
import warnings

import json

from payu.fsops import read_config
from payu.metadata import MetadataWarning, Metadata
from payu.laboratory import Laboratory
import payu.subcommands.args as args
from payu.status import (
    build_job_info,
    display_job_info,
    update_all_job_files
)
from payu.schedulers import index as scheduler_index, DEFAULT_SCHEDULER_CONFIG

title = 'status'
parameters = {'description': 'Display payu run information'}

arguments = [
    args.laboratory, args.config, args.json_output, args.update_jobs,
    args.all_runs, args.run_number
]

def runcmd(lab_path, config_path, json_output,
           update_jobs, all_runs, run_number):

    # Suppress output to os.devnull
    with redirect_stdout(open(os.devnull, 'w')):
        # Determine archive path
        lab = Laboratory(lab_path)
        warnings.filterwarnings("error", category=MetadataWarning)
        try:
            metadata = Metadata(Path(lab.archive_path),
                                config_path=config_path)
            metadata.setup()
        except MetadataWarning as e:
            raise RuntimeError(
                "Metadata is not setup - can't determine archive path"
            )
        archive_path = Path(lab.archive_path) / metadata.experiment_name

        # Determine control path
        config = read_config(config_path)
        control_path = Path(config['control_path'])

    run_number = int(run_number) if run_number is not None else None

    data = build_job_info(
        control_path=control_path,
        archive_path=archive_path,
        run_number=run_number,
        all_runs=all_runs
    )
    if update_jobs:
        # Get the scheduler
        scheduler_name = config.get('scheduler', DEFAULT_SCHEDULER_CONFIG)
        scheduler = scheduler_index[scheduler_name]()
        # Update the job files in data with the latest information
        # from the scheduler
        update_all_job_files(data, scheduler)
        # Rerun parsing job files to get the latest data
        data = build_job_info(
            archive_path=archive_path,
            control_path=control_path,
            run_number=run_number,
            all_runs=all_runs
        )

    if json_output:
        print(json.dumps(data, indent=4))
    else:
        display_job_info(data)

runscript = runcmd
