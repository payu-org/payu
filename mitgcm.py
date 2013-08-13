#!/usr/bin/env python
# coding: utf-8
"""
MITgcm payu interface
-------------------------------------------------------------------------------
Contact: Marshall Ward <marshall.ward@anu.edu.au>
-------------------------------------------------------------------------------
Distributed as part of Payu, Copyright 2011-2012 Marshall Ward
Licensed under the Apache License, Version 2.0
http://www.apache.org/licenses/LICENSE-2.0
"""

# Standard Library
import os
import sys
import shutil as sh
import subprocess as sp

# Local
from fs import mkdir_p
from payu import Experiment

class mitgcm(Experiment):

    #---
    def __init__(self, **kwargs):

        # payu initalisation
        super(mitgcm, self).__init__(**kwargs)

        # Model-specific configuration
        self.model_name = 'mitgcm'
        self.default_exec = 'mitgcmuv'
        self.path_names(**kwargs)

        self.modules = ['pbs',
                        'openmpi',
                        'netcdf']

        # TODO: Get a definitive config file whitelist
        self.config_files = [f for f in os.listdir(self.config_path)
                             if f.startswith('data')]
        self.config_files.append('eedata')


    #---
    def build(self):
        raise NotImplementedError


    #---
    def setup(self, days=None, dt=None, use_symlinks=True, repeat_run=False):
        # payu setup
        super(mitgcm, self).setup()

        self.load_modules()

        # Link restart files to work directory
        if self.prior_res_path and not repeat_run:
            restart_files = [f for f in os.listdir(self.prior_res_path)
                             if f.startswith('pickup.')]

            for f in restart_files:
                f_res = os.path.join(self.prior_res_path, f)
                f_work = os.path.join(self.work_path, f)
                if use_symlinks:
                    os.symlink(f_res, f_work)
                else:
                    sh.copy(f_res, f_work)

            # Determine total number of timesteps since initialisation
            # NOTE: Use the most recent, in case of multiple restarts
            n_iter0 = max([int(f.split('.')[1]) for f in restart_files])
        else:
            n_iter0 = 0

        # Link any input data to work directory
        for f in os.listdir(self.input_path):
            f_input = os.path.join(self.input_path, f)
            f_work = os.path.join(self.work_path, f)
            # Do not use a input file if an identical restart file exists
            if not os.path.exists(f_work):
                if use_symlinks:
                    os.symlink(f_input, f_work)
                else:
                    sh.copy(f_input, f_work)

        # Update configuration file 'data'
        # TODO: Combine the deltat and ntimestep IO processes

        data_path = os.path.join(self.work_path, 'data')

        # Update timestep size

        data_file = open(data_path, 'r')
        if dt:
            temp_path = data_path + '~'
            temp_file = open(temp_path, 'w')
            for line in data_file:
                if line.lstrip().lower().startswith('deltat='):
                    temp_file.write(' deltaT=%i,\n' % dt)
                else:
                    temp_file.write(line)
            temp_file.close()
            sh.move(temp_path, data_path)
        else:
            for line in data_file:
                if line.lstrip().lower().startswith('deltat='):
                    dt = int(line.split('=')[1].rsplit(',')[0].strip())
        data_file.close()
        assert dt

        # Update time interval

        if days:
            secs_per_day = 86400
            n_timesteps = days * secs_per_day // dt
            p_chkpt_freq = days * secs_per_day
        else:
            n_timesteps = None
            p_chkpt_freq = None

        temp_path = data_path + '~'

        data_file = open(data_path, 'r')
        temp_file = open(temp_path, 'w')
        for line in data_file:
            line_lowercase = line.lstrip().lower()
            if line_lowercase.startswith('niter0='):
                temp_file.write(' nIter0=%i,\n' % n_iter0)
            elif n_timesteps and line_lowercase.startswith('ntimesteps='):
                temp_file.write(' nTimeSteps=%i,\n' % n_timesteps)
            elif p_chkpt_freq and line_lowercase.startswith('pchkptfreq='):
                temp_file.write(' pChkptFreq=%f,\n' % p_chkpt_freq)
            else:
                temp_file.write(line)
        temp_file.close()
        data_file.close()
        sh.move(temp_path, data_path)

        # Patch or create data.mnc
        mnc_header = os.path.join(self.work_path, 'mnc_')

        data_mnc_path = os.path.join(self.work_path, 'data.mnc')
        if os.path.exists(data_mnc_path):
            tmp_path = data_mnc_path + '~'
            tmp = open(tmp_path, 'w')

            for line in open(data_mnc_path):
                if line.lstrip().startswith('mnc_outdir_str'):
                    tmp.write(' mnc_outdir_str=\'%s\',\n' % mnc_header)
                else:
                    tmp.write(line)
            tmp.close()
            sh.move(tmp_path, data_mnc_path)
        else:
            data_mnc = open(data_mnc_path, 'w')

            data_mnc.write(' &MNC_01\n')
            data_mnc.write(' mnc_use_outdir=.TRUE.,\n')
            data_mnc.write(' mnc_use_name_ni0=.TRUE.,\n')
            data_mnc.write(' mnc_outdir_str=\'%s\',\n' % mnc_header)
            data_mnc.write(' mnc_outdir_date=.TRUE.,\n')
            data_mnc.write(' monitor_mnc=.TRUE.,\n')
            data_mnc.write(' &\n')

            data_mnc.close()

        # Patch data.flt (if present)
        data_flt_path = os.path.join(self.work_path, 'data.flt')
        if os.path.isfile(data_flt_path):

            tmp_path = data_flt_path + '~'
            tmp = open(tmp_path, 'w')

            for line in open(data_flt_path):
                if line.lstrip().lower().startswith('flt_iter0'):
                    tmp.write(' FLT_Iter0 = {0},\n'.format(n_iter0))
                else:
                    tmp.write(line)
            tmp.close()
            sh.move(tmp_path, data_flt_path)

        # TODO: Patch data.ptracers
        data_ptracers_path = os.path.join(self.work_path, 'data.ptracers')
        if os.path.isfile(data_ptracers_path):
            sys.exit('ptracers are not supported yet!!')


    #---
    def run(self, *flags):
        flags = flags + ('-mca mpi_affinity_alone 1',
                         '-wd %s' % self.work_path)
        super(mitgcm, self).run(*flags)

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


    #---
    def archive(self, **kwargs):
        mkdir_p(self.res_path)

        # Move pickups but don't include intermediate pickupts ('ckpt's)
        restart_files = [f for f in os.listdir(self.work_path)
                         if f.startswith('pickup')
                         and not f.split('.')[1].startswith('ckpt')]

        # Tar and compress the output files
        stdout_files = [f for f in os.listdir(self.work_path)
                        if f.startswith('STDOUT.')]
        cmd = ('tar -C %s -c -j -f %s' % (self.work_path,
                os.path.join(self.work_path, 'STDOUT.tar.bz2') )
                ).split() + stdout_files
        rc = sp.Popen(cmd).wait()
        assert rc == 0

        for f in stdout_files:
            os.remove(os.path.join(self.work_path, f))

        for f in restart_files:
            f_src = os.path.join(self.work_path, f)
            sh.move(f_src, self.res_path)

        super(mitgcm, self).archive(**kwargs)


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
