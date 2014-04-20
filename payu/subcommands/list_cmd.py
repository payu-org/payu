# coding: utf-8

# Local
from payu.modelindex import index as model_index


# Configuration
title = 'list'
parameters = {'description': 'Prints the list of supported climate models'}


# Command line arguments
arguments = []


# Subcommand action
def runcmd():
    print('Supported models: {}'.format(' '.join(model_index)))
