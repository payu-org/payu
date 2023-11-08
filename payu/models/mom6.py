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
from payu.models.mom_mixin import MomMixin


def mom6_add_parameter_files(model):
    """Add parameter files defined in input.nml to model configuration files.
    Broken out of mom6 class so can be used in other models"""
    input_nml = f90nml.read(os.path.join(model.control_path, 'input.nml'))

    input_namelists = ['MOM_input_nml']
    if 'SIS_input_nml' in input_nml:
        input_namelists.append('SIS_input_nml')

    for input in input_namelists:
        input_namelist = input_nml.get(input, {})
        filenames = input_namelist.get('parameter_filename', [])

        if filenames == []:
            print("payu: warning: MOM6: There are no parameter files "
                  f"listed under {input} in input.nml")

        if isinstance(filenames, str):
            model.config_files.append(filenames)
        else:
            model.config_files.extend(filenames)


class Mom6(MomMixin, Fms):
    """Interface to GFDL's MOM6 ocean model."""

    def __init__(self, expt, name, config):

        # FMS initialisation
        super(Mom6, self).__init__(expt, name, config)

        self.model_type = 'mom6'
        self.default_exec = 'MOM6'

        self.config_files = [
            'input.nml',
            'diag_table',
        ]

        self.optional_config_files = [
            'data_table',
            'field_table'
        ]

    def setup(self):
        # FMS initialisation
        super(Mom6, self).setup()

        # Add parameter files to config files
        mom6_add_parameter_files(self)

        # Copy configuration files over to work path
        self.setup_configuration_files()

        self.init_config()

    def init_config(self):
        """Patch input.nml as a new or restart run."""

        input_fpath = os.path.join(self.work_path, 'input.nml')

        input_nml = f90nml.read(input_fpath)

        if ((self.expt.counter == 0 or self.expt.repeat_run) and
                self.prior_restart_path is None):
            input_type = 'n'
        else:
            input_type = 'r'
        input_nml['MOM_input_nml']['input_filename'] = input_type

        if 'SIS_input_nml' in input_nml:
            input_nml['SIS_input_nml']['input_filename'] = input_type

        f90nml.write(input_nml, input_fpath, force=True)
