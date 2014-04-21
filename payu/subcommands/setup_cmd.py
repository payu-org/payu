# coding: utf-8

# Local
import args

# Configuration
title ='setup'
parameters = {'description': 'Transfer input and configuration files'}

arguments = [args.model, args.config, args.initial, args.nruns]

def runcmd(model_type, config_path):
    print('welcome to setup')
