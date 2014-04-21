# coding: utf-8

# Local
import args

# Configuration
title = 'build'
parameters = {'description': 'Build the climate model executable'}

arguments = [args.model, args.config]

def runcmd(model_type, config_path):
    print('welcome to build')
