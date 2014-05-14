# coding: utf-8

# Local
import args
from payu.experiment import Experiment

# Configuration
title = 'init'
parameters = {'description': 'Initialize the model laboratory'}

arguments = [args.model, args.config, args.laboratory]

def runcmd(model_type, config_path, lab_name):

    expt = Experiment(lab_name)
    expt.init()
