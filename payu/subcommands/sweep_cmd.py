# coding: utf-8

import args

title = 'sweep'
parameters = {'description': 'Delete any temporary files from prior runs'}

arguments = [args.model, args.config, args.hard_sweep]

def runcmd(model_type, config_path, hard_sweep):
    print('welcome to sweep')
