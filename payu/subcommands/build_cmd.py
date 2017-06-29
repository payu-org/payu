# coding: utf-8

# Local
from payu.experiment import Experiment
from payu.laboratory import Laboratory
import payu.subcommands.args as args

# Configuration
title = 'build'
parameters = {'description': 'Build the climate model executable'}

arguments = [args.model, args.config, args.laboratory]


def runcmd(model_type, config_path, lab_path):

    lab = Laboratory(model_type, config_path, lab_path)
    expt = Experiment(lab)

    expt.build_model()


runscript = runcmd
