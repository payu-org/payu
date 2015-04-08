# coding: utf-8
"""payu.models.mom6
   ================

   Driver interface to the MOM6 ocean model.

   :copyright: Copyright 2011 Marshall Ward, see AUTHORS for details
   :license: Apache License, Version 2.0, see LICENSE for details
"""

# Standard library
import os

# Extensions
import f90nml

# Local
from payu.models.fms import Fms


class Mom6(Fms):
    """Interface to GFDL's MOM6 ocean model."""

    def __init__(self, expt, name, config):

        # FMS initalisation
        super(Mom6, self).__init__(expt, name, config)

        self.model_type = 'mom6'
        self.default_exec = 'MOM6'

        self.config_files = ['MOM_input',
                             'MOM_override',
                             'diag_table',
                             'input.nml']

    def setup(self):
        # FMS initialisation
        super(Mom6, self).setup()

        self.init_config()

    def init_config(self):
        """Patch input.nml as a new or restart run."""

        input_fpath = os.path.join(self.work_path, 'input.nml')

        input_nml = f90nml.read(input_fpath)

        input_type = 'n' if self.expt.counter == 0 else 'r'
        input_nml['MOM_input_nml']['input_filename'] = input_type

        f90nml.write(input_nml, input_fpath, force=True)
