"""Driver interface to the MOM ocean model.

:copyright: Copyright 2011 Marshall Ward, see AUTHORS for details
:license: Apache License, Version 2.0, see LICENSE for details
"""
import os
import shlex
import shutil
import subprocess

import f90nml

from payu.models.fms import Fms
from payu.models.mom_mixin import MomMixin
from payu.fsops import make_symlink


class Mom(MomMixin, Fms):

    def __init__(self, expt, name, config):

        # FMS initialisation
        super(Mom, self).__init__(expt, name, config)

        # Model-specific configuration
        self.model_type = 'mom'
        self.default_exec = 'fms_MOM_SIS.x'


        self.config_files = [
            'data_table',
            'diag_table',
            'field_table',
            'input.nml'
        ]

        self.optional_config_files = [
            'blob_diag_table',
            'mask_table',
            'ocean_mask_table'
        ]

    def set_model_pathnames(self):
        super(Mom, self).set_model_pathnames()



    def setup(self):
        # FMS initialisation
        super(Mom, self).setup()

        if not self.top_level_model:
            # Make log dir
            os.makedirs(os.path.join(self.work_path, 'log'), exist_ok=True)

        input_nml_path = os.path.join(self.work_path, 'input.nml')
        input_nml = f90nml.read(input_nml_path)

        # Set the runtime
        if self.expt.runtime:
            ocean_solo_nml = input_nml['ocean_solo_nml']

            ocean_solo_nml['years'] = self.expt.runtime['years']
            ocean_solo_nml['months'] = self.expt.runtime['months']
            ocean_solo_nml['days'] = self.expt.runtime['days']
            ocean_solo_nml['seconds'] = self.expt.runtime.get('seconds', 0)

            input_nml.write(input_nml_path, force=True)

        # NOTE: Don't expect this to be here forever...
        # Attempt to set a mask table from the input
        if self.config.get('mask', False):
            mask_path = os.path.join(self.work_input_path, 'ocean_mask_table')

            # Remove any existing mask
            # (If no reference mask is available, then we will not use one)
            if os.path.isfile(mask_path):
                os.remove(mask_path)

            # Reference mask table
            assert ('layout' in input_nml['ocean_model_nml'])
            nx, ny = input_nml['ocean_model_nml'].get('layout')
            n_masked_cpus = nx * ny - self.config.get('ncpus')

            mask_table_fname = 'mask_table.{nmask}.{nx}x{ny}'.format(
                nmask=n_masked_cpus,
                nx=nx,
                ny=ny
            )

            ref_mask_path = os.path.join(self.work_input_path,
                                         mask_table_fname)

            # Set (or replace) mask table if reference is available
            if os.path.isfile(ref_mask_path):
                make_symlink(ref_mask_path, mask_path)

    def set_timestep(self, timestep):

        input_nml_path = os.path.join(self.work_path, 'input.nml')
        input_nml = f90nml.read(input_nml_path)

        input_nml['ocean_model_nml']['dt_ocean'] = timestep

        input_nml.write(input_nml_path, force=True)
