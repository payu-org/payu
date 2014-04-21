# coding: utf-8

import args

title = 'run'
parameters = {'description': 'Run the model experiment'}

arguments = [args.model, args.config, args.initial, args.nruns]

def runcmd(model_type, config_path, init_run, n_runs):
    print('welcome to run')
