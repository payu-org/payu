# coding: utf-8

from payu import cli
from payu.experiment import Experiment
from payu.laboratory import Laboratory
import payu.subcommands.args as args

title = 'sweep'
parameters = {'description': 'Delete any temporary files from prior runs'}

arguments = [args.model, args.config, args.hard_sweep, args.laboratory,
             args.metadata_off, args.stacktrace]


def runcmd(model_type, config_path, hard_sweep, lab_path, metadata_off,
           stacktrace=None):

    # Configure stacktrace settings based on arguments
    cli.set_stacktrace_runscript(stacktrace)

    lab = Laboratory(model_type, config_path, lab_path)
    expt = Experiment(lab, metadata_off=metadata_off)

    expt.sweep(hard_sweep)


runscript = runcmd
