# coding: utf-8

import args

title = 'collate'
parameters = {'description': 'Collate tiled output into single output files'}

arguments = [args.model, args.config, args.initial, args.nruns]

def runcmd(model_type, config_path, init_run, n_runs):
    print('welcome to collate')
