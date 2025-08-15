# coding: utf-8
from contextlib import redirect_stdout
import os
from pathlib import Path

import json

from payu.experiment import Experiment
from payu.laboratory import Laboratory
import payu.subcommands.args as args
from payu.status import (
    query_job_info,
    display_job_info,
    update_all_job_files
)

title = 'status'
parameters = {'description': 'Display payu run information'}

arguments = [
    args.laboratory, args.json_output, args.update_jobs,
    args.all_runs, args.run_number
]

def runcmd(lab_path, json_output, update_jobs, all_runs, run_number):

    # Suppress output to os.devnull
    with redirect_stdout(open(os.devnull, 'w')):
        lab = Laboratory(lab_path)
        # Initialise experiment to determine configurations, experiment paths and
        # metadata
        expt = Experiment(lab)

    run_number = int(run_number) if run_number is not None else None

    data = query_job_info(
        control_path=Path(expt.control_path),
        archive_path=Path(expt.archive_path),
        run_number=run_number,
        all_runs=all_runs
    )
    if update_jobs:
        # Update the job files in data with the latest information
        # from the scheduler
        update_all_job_files(data, expt.scheduler)
        # Rerun parsing job files to get the latest data
        data = query_job_info(
            control_path=Path(expt.control_path),
            archive_path=Path(expt.archive_path),
            run_number=run_number,
            all_runs=all_runs
        )

    if json_output:
        print(json.dumps(data, indent=4))
    else:
        display_job_info(data)

runscript = runcmd
