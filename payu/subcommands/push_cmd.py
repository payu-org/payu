# coding: utf-8

from payu.experiment import Experiment
from payu.laboratory import Laboratory
import payu.subcommands.args as args

title = 'push'
parameters = {'description': 'Push configuration to GitHub'}

arguments = [args.model, args.config, args.laboratory]


def runcmd(model_type, config_path, lab_path):

    lab = Laboratory(model_type, config_path, lab_path)
    expt = Experiment(lab)

    if expt.runlog.enabled:
        expt.runlog.push()
    else:
        print('payu: Runlog must be enabled to push repositories.')


runscript = runcmd
