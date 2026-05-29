# coding: utf-8

from payu.experiment import Experiment
from payu.laboratory import Laboratory
import payu.subcommands.args as args
from payu import cli

title = 'push'
parameters = {'description': 'Push configuration to GitHub'}

arguments = [args.model, args.config, args.laboratory, args.stacktrace]


def runcmd(model_type, config_path, lab_path, stacktrace=None):

    # Configure stacktrace settings based on arguments
    cli.set_stacktrace_runscript(stacktrace)

    lab = Laboratory(model_type, config_path, lab_path)
    expt = Experiment(lab)

    if expt.runlog.enabled:
        expt.runlog.push()
    else:
        print('payu: Runlog must be enabled to push repositories.')


runscript = runcmd
