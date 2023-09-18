# coding: utf-8
"""payu.models.mom6
   ================

   Driver interface to the MOM6 ocean model.

   :copyright: Copyright 2011 Marshall Ward, see AUTHORS for details
   :license: Apache License, Version 2.0, see LICENSE for details
"""

# Standard library
import os
import shutil

# Extensions
import f90nml

# Local
from payu.models.fms import Fms


class Mom6(Fms):
    """Interface to GFDL's MOM6 ocean model."""

    def __init__(self, expt, name, config):

        # FMS initialisation
        super(Mom6, self).__init__(expt, name, config)

        self.model_type = 'mom6'
        self.default_exec = 'MOM6'

        self.config_files = [
            'input.nml',
            'MOM_input',
            'diag_table',
        ]

        # TODO: Need to figure out what's going on here with MOM6
        self.optional_config_files = [
            'data_table',
            'data_table.MOM6',
            'data_table.OM4',
            'data_table.SIS',
            'data_table.icebergs',

            'field_table',

            'MOM_override',
            'MOM_layout',
            'MOM_saltrestore',

            'SIS_input',
            'SIS_override',
            'SIS_layout',
        ]

    def setup(self):
        # FMS initialisation
        super(Mom6, self).setup()

        self.init_config()
        self.add_parameter_config_files()

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

    def add_parameter_config_files(self):
        """Check that the parameter files listed in input.nml are in the
        model's configuration files"""
        input_nml = f90nml.read(os.path.join(self.work_path, 'input.nml'))

        # Set of all configuration files
        config_files = set(self.config_files).union(self.optional_config_files)

        for input in ['MOM_input_nml', 'SIS_input_nml']:
            input_namelist = input_nml.get(input, {})
            parameter_files = input_namelist.get('parameter_filename', [])

            if isinstance(parameter_files, str):
                parameter_files = [parameter_files]

            for filename in parameter_files:
                if filename not in config_files:
                    print(f"payu: warning: parameter file {filename} "
                          f"listed under {input} in input.nml is not in "
                          "mom6's configuration files")

                    # Extend config files
                    self.config_files.append(filename)

                    # Copy parameter file from control path to work path
                    file_path = os.path.join(self.control_path, filename)
                    shutil.copy(file_path, self.work_path)
