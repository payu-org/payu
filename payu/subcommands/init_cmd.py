# coding: utf-8

# Local
from payu.laboratory import Laboratory
import payu.subcommands.args as args
from payu import cli

# Configuration
title = 'init'
parameters = {'description': 'Initialize the model laboratory'}

arguments = [args.model, args.config, args.laboratory, args.stacktrace]


def runcmd(model_type, config_path, lab_path, stacktrace=None):
    # Configure stacktrace settings based on arguments
    cli.set_stacktrace_runscript(stacktrace)

    lab = Laboratory(model_type, config_path, lab_path)
    lab.initialize()
