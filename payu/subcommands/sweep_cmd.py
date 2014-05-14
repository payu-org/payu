# coding: utf-8

import args
from ..experiment import Experiment

title = 'sweep'
parameters = {'description': 'Delete any temporary files from prior runs'}

arguments = [args.model, args.config, args.hard_sweep, args.laboratory]

def runcmd(model_type, config_path, hard_sweep, laboratory):

    expt = Experiment(laboratory)
    expt.sweep(hard_sweep)

runscript = runcmd
