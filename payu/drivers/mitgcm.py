#!/usr/bin/env python
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
import re
import sys
import shutil as sh
import subprocess as sp

# Local
from ..fsops import mkdir_p, patch_nml
from ..modeldriver import Model

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
    def setup(self, use_symlinks=True, repeat_run=False):

        # TODO: Find a better place to generate this list
        self.config_files = [f for f in os.listdir(self.control_path)
                             if f.startswith('data')]
        self.config_files.append('eedata')

        # Generic model setup
        super(Mitgcm, self).setup()

        # Link restart files to work directory
        if self.prior_restart_path and not repeat_run:
        #    restart_files = [f for f in os.listdir(self.prior_restart_path)
        #                     if f.startswith('pickup')]

        #    for f in restart_files:
        #        f_restart = os.path.join(self.prior_restart_path, f)
        #        f_work = os.path.join(self.work_path, f)
        #        if use_symlinks:
        #            os.symlink(f_restart, f_work)
        #        else:
        #            sh.copy(f_restart, f_work)

        #    # Determine total number of timesteps since initialisation
            core_restarts = [f for f in os.listdir(self.prior_restart_path)
                                if f.startswith('pickup.')]
            try:
                # NOTE: Use the most recent, in case of multiple restarts
                n_iter0 = max([int(f.split('.')[1]) for f in core_restarts])
            except ValueError:
                sys.exit("payu: error: no restart files found.")
        else:
            n_iter0 = 0

        ## Link any input data to work directory
        #for input_path in self.input_paths:
        #    for f in os.listdir(input_path):
        #        f_input = os.path.join(input_path, f)
        #        f_work = os.path.join(self.work_path, f)
        #        # Do not use a input file if an identical restart file exists
        #        if not os.path.exists(f_work):
        #            if use_symlinks:
        #                os.symlink(f_input, f_work)
        #            else:
        #                sh.copy(f_input, f_work)

        # Update configuration file 'data'

        data_path = os.path.join(self.work_path, 'data')
        data_file = open(data_path, 'r')

        # First scan the file for the necessary parameters
        dt = None
        n_timesteps = None

        p_dt = re.compile('^ *deltat *=', re.IGNORECASE)
        p_nt = re.compile('^ *ntimesteps *=', re.IGNORECASE)
        for line in data_file:
            if p_dt.match(line):
                dt = float(re.sub('[^\d]', '', line.split('=')[1]))
            elif p_nt.match(line):
                n_timesteps = int(re.sub('[^\d]', '', line.split('=')[1]))

        # Update checkpoint intervals
        # NOTE: Consider permitting pchkpt_freq < dt * n_timesteps
        # NOTE: May re-enable chkpt_freq in the future
        pchkpt_freq = dt * n_timesteps
        chkpt_freq = 0.

        # Next, patch data with updated values
        temp_path = data_path + '~'
        temp_file = open(temp_path, 'w')

        # "Rewind" data file
        data_file.seek(0)

        p_niter0 = re.compile('^ *niter0 *=', re.IGNORECASE)
        p_pchkpt_freq = re.compile('^ *pchkptfreq *=', re.IGNORECASE)
        p_chkpt_freq = re.compile('^ *chkptfreq *=', re.IGNORECASE)

        for line in data_file:
            if p_niter0.match(line):
                temp_file.write(' nIter0={},\n'.format(n_iter0))
            elif p_pchkpt_freq.match(line):
                temp_file.write(' pChkptFreq={},\n'.format(pchkpt_freq))
            elif p_chkpt_freq.match(line):
                temp_file.write(' chkptFreq={},\n'.format(chkpt_freq))
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

            p_mnc_outdir = re.compile('^ *mnc_outdir_str *=', re.IGNORECASE)

            data_mnc_file = open(data_mnc_path, 'r')
            for line in data_mnc_file:
                if p_mnc_outdir.match(line):
                    tmp.write(" mnc_outdir_str='{}',\n".format(mnc_header))
                else:
                    tmp.write(line)
            data_mnc_file.close()
            tmp.close()
            sh.move(tmp_path, data_mnc_path)
        else:
            with open(data_mnc_path, 'w') as data_mnc:
                data_mnc.write(' &MNC_01\n')
                data_mnc.write(' mnc_use_outdir=.TRUE.,\n')
                data_mnc.write(' mnc_use_name_ni0=.TRUE.,\n')
                data_mnc.write(" mnc_outdir_str='{}',\n".format(mnc_header))
                data_mnc.write(' mnc_outdir_date=.TRUE.,\n')
                data_mnc.write(' monitor_mnc=.TRUE.,\n')
                data_mnc.write(' &\n')

        # XXX: These iter0's are only necessary on first submission
        # If you update them to nIter0 it will re-initialize everything and
        # break the process.
        # I need to fix this stuff up; for now just comment it out

        # Patch data.flt (if present)
        #data_flt_path = os.path.join(self.work_path, 'data.flt')
        #flt_iter0_pattern = '^ *flt_iter0 *='
        #flt_iter0_replace = ' FLT_Iter0 = {0},\n'.format(n_iter0)

        #patch_nml(data_flt_path, flt_iter0_pattern, flt_iter0_replace)

        # Patch data.ptracers (if present)
        #data_ptracers_path = os.path.join(self.work_path, 'data.ptracers')
        #ptrc_iter0_pattern = '^ *ptracers_iter0 *='
        #ptrc_iter0_replace = ' PTRACERS_Iter0 = {0},\n'.format(n_iter0)

        #patch_nml(data_ptracers_path, ptrc_iter0_pattern, ptrc_iter0_replace)


    #---
    # XXX: Dud function; delete it
    def run(self, *flags):
        flags = flags + ('-mca mpi_affinity_alone 1',
                         '-wd %s' % self.work_path)
        super(Mitgcm, self).run(*flags)

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
        cmd = ('tar -C %s -c -j -f %s' % (self.work_path,
                os.path.join(self.work_path, 'STDOUT.tar.bz2') )
                ).split() + stdout_files
        rc = sp.Popen(cmd).wait()
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
