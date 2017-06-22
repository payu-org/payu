# coding: utf-8

from payu.experiment import Experiment
from payu.laboratory import Laboratory
import payu.subcommands.args as args

title = 'sweep'
parameters = {'description': 'Delete any temporary files from prior runs'}

arguments = [args.model, args.config, args.hard_sweep, args.laboratory]


def runcmd(model_type, config_path, hard_sweep, lab_path):

    lab = Laboratory(model_type, config_path, lab_path)
    expt = Experiment(lab)

    expt.sweep(hard_sweep)


runscript = runcmd
