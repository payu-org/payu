# coding: utf-8
"""
The payu implementation of GOLD
-------------------------------------------------------------------------------
Contact: Marshall Ward <marshall.ward@anu.edu.au>
-------------------------------------------------------------------------------
Distributed as part of Payu, Copyright 2011 Marshall Ward
Licensed under the Apache License, Version 2.0
http://www.apache.org/licenses/LICENSE-2.0
"""

# Standard library
import os

# Extensions
import f90nml

# Local
from payu.models.fms import Fms


class Gold(Fms):
    """Interface to GFDL's GOLD ocean model."""

    def __init__(self, expt, name, config):

        # FMS initialisation
        super(Gold, self).__init__(expt, name, config)

        self.model_type = 'gold'
        self.default_exec = 'GOLD'

        self.config_files = ['GOLD_input',
                             'GOLD_override',
                             'diag_table',
                             'fre_input.nml',
                             'input.nml']

    def setup(self):
        # FMS initialisation
        super(Gold, self).setup()

        self.init_config()

    def init_config(self):
        """Patch input.nml as a new or restart run."""

        input_fpath = os.path.join(self.work_path, 'input.nml')

        input_nml = f90nml.read(input_fpath)

        input_type = 'n' if self.expt.counter == 0 else 'r'
        input_nml['GOLD_input_nml']['input_filename'] = input_type

        f90nml.write(input_nml, input_fpath, force=True)
