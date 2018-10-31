# coding: utf-8

# Local
from payu.models import index as model_index

# Configuration
title = 'list'
parameters = {'description': 'Prints the list of supported climate models'}

arguments = []


def runcmd():
    print('Supported models: {0}'.format(' '.join(model_index)))


runscript = runcmd
