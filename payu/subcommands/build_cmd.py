# coding: utf-8

# Local
import args
from payu.experiment import Experiment

# Configuration
title = 'build'
parameters = {'description': 'Build the climate model executable'}

arguments = [args.model, args.config, args.laboratory]

def runcmd(model_type, config_path, lab_name):

    expt = Experiment(lab_name)
    expt.build_model()
