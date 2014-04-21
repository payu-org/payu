# coding: utf-8

import args

title = 'archive'
parameters = {'description': 'Store a completed run in the local archive'}

arguments = [args.model, args.config, args.initial, args.nruns]

def runcmd(model_type, config_path, init_run, n_runs):
    print('welcome to archive')
