# coding: utf-8
"""
MITgcm payu interface
-------------------------------------------------------------------------------
Contact: Marshall Ward <marshall.ward@anu.edu.au>
-------------------------------------------------------------------------------
Distributed as part of Payu, Copyright 2011 Marshall Ward
Licensed under the Apache License, Version 2.0
http://www.apache.org/licenses/LICENSE-2.0
"""

# Standard Library
import errno
import os
import sys
import shlex
import shutil as sh
import subprocess as sp

# Extensions
import f90nml

# Local
from payu.fsops import mkdir_p
from payu.modeldriver import Model

class Mitgcm(Model):

    #---
    def __init__(self, expt, name, config):
        super(Mitgcm, self).__init__(expt, name, config)

        # Model-specific configuration
        self.model_type = 'mitgcm'
        self.default_exec = 'mitgcmuv'

        self.modules = ['pbs',
                        'openmpi',
                        'netcdf']

        # NOTE: We use a subroutine to generate the MITgcm configuration list
        self.config_files = None


    #---
    def setup(self):

        # TODO: Find a better place to generate this list
        self.config_files = [f for f in os.listdir(self.control_path)
                             if f.startswith('data')]
        self.config_files.append('eedata')

        # Generic model setup
        super(Mitgcm, self).setup()

        # Link restart files to work directory
        if self.prior_restart_path and not self.expt.repeat_run:

            # Determine total number of timesteps since initialisation
            core_restarts = [f for f in os.listdir(self.prior_restart_path)
                                if f.startswith('pickup.')]
            try:
                # NOTE: Use the most recent, in case of multiple restarts
                n_iter0 = max([int(f.split('.')[1]) for f in core_restarts])
            except ValueError:
                sys.exit("payu: error: no restart files found.")
        else:
            n_iter0 = 0

        # Update configuration file 'data'

        data_path = os.path.join(self.work_path, 'data')
        data_nml = f90nml.read(data_path)

        # NOTE: Assumes that these are always present
        dt = data_nml['parm03']['deltat']
        n_timesteps = data_nml['parm03']['ntimesteps']

        # NOTE: Consider permitting pchkpt_freq < dt * n_timesteps
        # NOTE: May re-enable chkpt_freq in the future
        data_nml['parm03']['niter0'] = n_iter0
        data_nml['parm03']['pchkptfreq'] = dt * n_timesteps
        data_nml['parm03']['chkptfreq'] = 0

        data_nml.write(data_path, force=True)

        # Patch or create data.mnc
        mnc_header = os.path.join(self.work_path, 'mnc_')

        data_mnc_path = os.path.join(self.work_path, 'data.mnc')
        try:
            data_mnc_nml = f90nml.read(data_mnc_path)
            data_mnc_nml['mnc_01']['mnc_outdir_str'] = mnc_header
            data_mnc_nml.write(data_mnc_path, force=True)

        except IOError as exc:
            if exc.errno == errno.ENOENT:

                mnc_01_grp = {'mnc_use_outdir': True,
                              'mnc_use_name_ni0': True,
                              'mnc_outdir_str': mnc_header,
                              'mnc_outdir_date': True,
                              'monitor_mnc': True
                             }
                data_mnc_nml = {'mnc_01': mnc_01_grp}

                f90nml.write(data_mnc_nml, data_mnc_path)
            else:
                raise


    #---
    def archive(self):

        # Remove symbolic links to input or pickup files:
        for f in os.listdir(self.work_path):
            f_path = os.path.join(self.work_path, f)
            if os.path.islink(f_path):
                os.remove(f_path)

        # Move files outside of mnc_* directories
        mnc_paths = [os.path.join(self.work_path, d)
                     for d in os.listdir(self.work_path)
                     if d.startswith('mnc_')]

        for path in mnc_paths:
            for f in os.listdir(path):
                f_path = os.path.join(path, f)
                sh.move(f_path, self.work_path)
            os.rmdir(path)

        mkdir_p(self.restart_path)

        # Move pickups but don't include intermediate pickupts ('ckpt's)
        restart_files = [f for f in os.listdir(self.work_path)
                         if f.startswith('pickup')
                         and not f.split('.')[1].startswith('ckpt')]

        # Tar and compress the output files
        stdout_files = [f for f in os.listdir(self.work_path)
                        if f.startswith('STDOUT.')]
        cmd = 'tar -C {} -c -j -f {}'.format(self.work_path,
                    os.path.join(self.work_path, 'STDOUT.tar.bz2'))

        rc = sp.Popen(shlex.split(cmd) + stdout_files).wait()
        assert rc == 0

        for f in stdout_files:
            os.remove(os.path.join(self.work_path, f))

        for f in restart_files:
            f_src = os.path.join(self.work_path, f)
            sh.move(f_src, self.restart_path)


    #---
    def collate(self, clear_tiles=True, partition=None):
        import mnctools as mnc

        # Use leading tiles to construct a tile manifest
        # Don't collate the pickup files
        # Tiled format: <field>.t###.nc
        output_fnames = [f.replace('.t001.', '.')
                         for f in os.listdir(self.output_path)
                         if f.endswith('.t001.nc')
                         and not f.startswith('pickup')]

        tile_fnames = {}
        for fname in output_fnames:
            f_header = fname.rsplit('.', 1)[0]

            tile_fnames[fname] = [os.path.join(self.output_path, f)
                                  for f in os.listdir(self.output_path)
                                  if f.startswith(f_header + '.')
                                  and f.split('.')[-2].startswith('t')
                                  and f.split('.')[-2].lstrip('t').isdigit()]

        for fname in tile_fnames:
            mnc.collate(tile_fnames[fname],
                        os.path.join(self.output_path, fname),
                        partition)

        if clear_tiles:
            for fname in tile_fnames:
                for tile_fname in tile_fnames[fname]:
                    os.remove(tile_fname)
