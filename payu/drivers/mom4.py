#!/usr/bin/env python
# coding: utf-8
"""
Payu MOM4 wrapper for MOM

Provides compatibility with the older MOM4-specific wrapper
-------------------------------------------------------------------------------
Primary Contact: Marshall Ward <marshall.ward@anu.edu.au>
-------------------------------------------------------------------------------
Distributed as part of Payu, Copyright 2011-2012 Marshall Ward
Licensed under the Apache License, Version 2.0
http://www.apache.org/licenses/LICENSE-2.0
"""

from mom import Mom

class mom4(Mom):
    #---
    def __init__(self, **kwargs):

        # Model-specific configuration
        self.model_name = 'mom4'
        self.default_exec = 'mom4'

        self.modules = ['pbs',
                        'openmpi',
                        'nco']

        self.config_files = ['data_table',
                             'diag_table',
                             'field_table',
                             'input.nml']

        # FMS initalisation
        super(Mom, self).__init__(**kwargs)
