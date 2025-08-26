# coding: utf-8

import sys

from payu.experiment import Experiment
from payu.laboratory import Laboratory
from payu.git_utils import PayuBranchError
import payu.subcommands.args as args

title = 'sweep'
parameters = {'description': 'Delete any temporary files from prior runs'}

arguments = [args.model, args.config, args.hard_sweep, args.laboratory,
             args.metadata_off]


def runcmd(model_type, config_path, hard_sweep, lab_path, metadata_off):

    lab = Laboratory(model_type, config_path, lab_path)
    try:
        expt = Experiment(lab, metadata_off=metadata_off)
    except PayuBranchError as e:
        # Check it is a detached HEAD state error before offering remedy
        if "detached HEAD" in str(e):
            sys.exit(f'\npayu: error: {e}\n\n'
                     'Checkout a branch before running payu sweep again.\n')
        else:
            raise

    expt.sweep(hard_sweep)

runscript = runcmd
