# coding: utf-8
from contextlib import redirect_stdout
import os
from pathlib import Path

import json

from payu.experiment import Experiment
from payu.laboratory import Laboratory
import payu.subcommands.args as args
from payu.telemetry import (
    query_job_info,
    display_job_info,
    update_all_job_files
)

title = 'status'
parameters = {'description': 'Display payu run information'}

arguments = [
    args.laboratory, args.json_output, args.update_jobs,
]


def runcmd(lab_path, json_output, update_jobs):
    
    # Suppress output to os.devnull
    with redirect_stdout(open(os.devnull, 'w')):
        lab = Laboratory(lab_path)
        # Initialise experiment to determine configurations, experiment paths and
        # metadata
        expt = Experiment(lab)

    data = query_job_info(
        control_path=Path(expt.control_path),
        work_path=Path(expt.work_path),
        archive_path=Path(expt.archive_path)
    )
    if update_jobs:
        # Update the job files with the latest data from the scheduler
        data = update_all_job_files(data, expt.scheduler)
        # Rerun querying job files to get the latest data
        data = query_job_info(
            control_path=Path(expt.control_path),
            work_path=Path(expt.work_path),
            archive_path=Path(expt.archive_path)
        )

    if json_output:
        print(json.dumps(data, indent=4))
    else:
        display_job_info(data)

runscript = runcmd
