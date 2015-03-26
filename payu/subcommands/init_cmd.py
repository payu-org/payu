# coding: utf-8

# Local
from payu.laboratory import Laboratory
import payu.subcommands.args as args

# Configuration
title = 'init'
parameters = {'description': 'Initialize the model laboratory'}

arguments = [args.model, args.config, args.laboratory]


def runcmd(model_type, config_path, lab_path):

    lab = Laboratory(model_type, config_path, lab_path)
    lab.initialize()
