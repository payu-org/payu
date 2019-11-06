"""Driver interface to the MOM ocean model.

:copyright: Copyright 2011 Marshall Ward, see AUTHORS for details
:license: Apache License, Version 2.0, see LICENSE for details
"""
import os
import shlex
import shutil
import subprocess

import f90nml
import payu.envmod
from payu.models.fms import Fms
from payu.fsops import mkdir_p, make_symlink


class Mom(Fms):

    def __init__(self, expt, name, config):

        # FMS initialisation
        super(Mom, self).__init__(expt, name, config)

        # Model-specific configuration
        self.model_type = 'mom'
        self.default_exec = 'fms_MOM_SIS.x'

        # Default repo and build details.
        self.repo_url = 'git://github.com/BreakawayLabs/mom.git'
        self.repo_tag = 'master'
        self.build_command = './MOM_compile.csh --platform nci --type MOM_SIS'

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

        self.build_exec_path = os.path.join(self.codebase_path, 'exec', 'nci',
                                            'MOM_SIS')
        self.build_path = os.path.join(self.codebase_path, 'exp')

    def build_model(self):
        super(Mom, self).build_model()

        # Model is built, now copy over mppnccombine.
        mppnc_exec = 'mppnccombine.nci'

        mppnc_src = os.path.join(self.codebase_path, 'bin', mppnc_exec)
        mppnc_dest = os.path.join(self.expt.lab.bin_path, 'mppnccombine')
        shutil.copy(mppnc_src, mppnc_dest)

    def setup(self):
        # FMS initialisation
        super(Mom, self).setup()

        if not self.top_level_model:
            # Make log dir
            mkdir_p(os.path.join(self.work_path, 'log'))

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

        # Construct the land CPU mask
        if self.expt.config.get('mask_table', False):
            # NOTE: This function actually creates a mask table using the
            #       `check_mask` command line tool.  But it is not very usable
            #       since you need to know the number of masked CPUs to submit
            #       the job.  It needs a rethink of the submission process.
            self.create_mask_table(input_nml)

        # NOTE: Don't expect this to be here forever...
        # Attempt to set a mask table from the input
        if self.config.get('mask', False):
            mask_path = os.path.join(self.work_input_path, 'ocean_mask_table')

            # Remove any existing mask
            # (If no reference mask is available, then we will not use one)
            if os.path.isfile(mask_path):
                os.remove(mask_path)

            # Reference mask table
            assert('layout' in input_nml['ocean_model_nml'])
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

    def create_mask_table(self, input_nml):
        import netCDF4

        # Disable E1136 which is tripped below when accessing grid_vars
        # pylint: disable=unsubscriptable-object

        # Get the grid spec path
        grid_spec_fname = 'grid_spec.nc'
        for input_dir in self.input_paths:
            if grid_spec_fname in os.listdir(input_dir):
                grid_spec_path = os.path.join(input_dir, grid_spec_fname)
                break
        assert grid_spec_path

        grid_spec_nc = netCDF4.Dataset(grid_spec_path)
        grid_vars = grid_spec_nc.variables

        # Get the ocean mosaic file
        # TODO: Do not assume mosaic format
        ocn_mosaic_fname = ''.join(grid_vars['ocn_mosaic_file'][:].data)
        for input_dir in self.input_paths:
            if ocn_mosaic_fname in os.listdir(input_dir):
                ocn_mosaic_path = os.path.join(input_dir, ocn_mosaic_fname)
                break

        # Get the topography file
        ocn_topog_fname = ''.join(grid_vars['ocn_topog_file'][:].data)
        for input_dir in self.input_paths:
            if ocn_topog_fname in os.listdir(input_dir):
                ocn_topog_path = os.path.join(input_dir, ocn_topog_fname)
                break

        # pylint: enable=unsubscriptable-object

        grid_spec_nc.close()

        check_mask = os.path.join(self.expt.lab.bin_path, 'check_mask')
        f_null = open(os.devnull, 'w')

        # Generate ocean mask_table
        ocn_layout = input_nml['ocean_model_nml']['layout']

        cmd = (
            '{check_mask} --grid_file {grid_file} '
            '--ocean_topog {ocean_topog} --layout {layout}'.format(
                check_mask=check_mask,
                grid_file=ocn_mosaic_path,
                ocean_topog=ocn_topog_path,
                layout=','.join([str(s) for s in ocn_layout])
            )
        )
        subprocess.call(shlex.split(cmd), stdout=f_null)
        ocn_mask_fname = [f for f in os.listdir(os.curdir)
                          if f.startswith('mask_table')][0]

        ocn_mask_path = os.path.join(self.work_input_path,
                                     'ocean_mask_table')
        shutil.copy(ocn_mask_fname, ocn_mask_path)

        # Generate the ice mask_table
        ice_layout = input_nml['ice_model_nml']['layout']

        if ice_layout == ocn_layout:
            ice_mask_fname = ocn_mask_fname
        else:
            cmd = (
                '{check_mask} --grid_file {grid_file} '
                '--ocean_topog {ocean_topog} --layout {layout}'.format(
                    check_mask=check_mask,
                    grid_file=ocn_mosaic_path,
                    ocean_topog=ocn_topog_path,
                    layout=','.join([str(s) for s in ice_layout])
                )
            )
            subprocess.call(shlex.split(cmd), stdout=f_null)
            ice_mask_fname = [f for f in os.listdir(os.curdir)
                              if f.startswith('mask_table')][0]

        ice_mask_path = os.path.join(self.work_input_path,
                                     'ice_mask_table')

        shutil.copy(ice_mask_fname, ice_mask_path)

        try:
            os.remove(ocn_mask_fname)
            os.remove(ice_mask_fname)
        except EnvironmentError:
            # TODO: Check this a little bit better
            pass

        f_null.close()

        # Read and return the number of land cells
        with open(ocn_mask_path) as fmask:
            land_cells = int(fmask.readline())

        return land_cells
