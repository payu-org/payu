# coding: utf-8
"""
MITgcm payu interface
===============================================================================
Primary Contact:    Marshall Ward (marshall.ward@anu.edu.au)
"""

from payu import Experiment, mkdir_p
import os
import sys
import shutil as sh
import subprocess as sp

import mnctools_dev as mnc

class mitgcm(Experiment):
    
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
        self.load_modules()
        
        # TODO: Get a definitive config file whitelist
        self.config_files = [f for f in os.listdir(self.config_path)
                             if f.startswith('data')]
        self.config_files.append('eedata')
    
    
    #---
    def build(self):
        raise NotImplementedError
    
    
    #---
    def setup(self, days, dt, use_symlinks=True, repeat_run=False):
        # TODO: The config file patches could be moved to separate methods
        
        # payu setup
        super(mitgcm, self).setup()
        
        # Calculate time intervals
        secs_per_day = 86400
        n_timesteps = days * secs_per_day // dt
        n_iter0 = (self.counter - 1) * n_timesteps
        p_chkpt_freq = days * secs_per_day
       
        # Patch data timestep variables
        data_path = os.path.join(self.work_path, 'data')
        tmp_path = data_path + '~'
        
        tmp = open(tmp_path, 'w')
        for line in open(data_path):
            if line.lstrip().startswith('nIter0='):
                tmp.write(' nIter0=%i,\n' % n_iter0)
            elif line.lstrip().startswith('nTimeSteps='):
                tmp.write(' nTimeSteps=%i,\n' % n_timesteps)
            elif line.lstrip().startswith('deltaT='):
                tmp.write(' deltaT=%i,\n' % dt)
            elif line.lstrip().startswith('pChkptFreq='):
                tmp.write(' pChkptFreq=%f,\n' % p_chkpt_freq)
            else:
                tmp.write(line)
        tmp.close()
        sh.move(tmp_path, data_path)
        
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
        
        # Link restart files to work directory
        if self.prior_run_path and not repeat_run:
            restart_files = [f for f in os.listdir(self.prior_run_path)
                             if f.startswith('pickup.')]
            
            for f in restart_files:
                f_res = os.path.join(self.prior_run_path, f)
                f_input = os.path.join(self.work_path, f)
                if use_symlinks:
                    os.symlink(f_res, f_input)
                else:
                    sh.copy(f_res, f_input)
        
        # Link any forcing data to INPUT
        for f in os.listdir(self.forcing_path):
            f_forcing = os.path.join(self.forcing_path, f)
            f_input = os.path.join(self.work_path, f)
            # Do not use forcing file if it is in RESTART
            if not os.path.exists(f_input):
                if use_symlinks:
                    os.symlink(f_forcing, f_input)
                else:
                    sh.copy(f_forcing, f_input)
    
    
    #---
    def run(self, *flags):
        flags = flags + ('-mca mpi_affinity_alone 1',
                         '-wd %s' % self.work_path)
        super(mitgcm, self).run(*flags)
        
        # Remove symbolic links to forcing or pickup files:
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
    def collate(self, clear_tiles=True):
        # Use leading tiles to construct a tile manifest
        # Don't collate the pickup files
        # Tiled format: <field>.t###.nc
        output_fnames = [f.replace('.t001.', '.')
                         for f in os.listdir(self.run_path)
                         if f.endswith('.t001.nc')
                         and not f.startswith('pickup.')]
        
        tile_fnames = {}
        for fname in output_fnames:
            f_header = fname.rsplit('.', 1)[0]
            
            tile_fnames[fname] = [os.path.join(self.run_path, f)
                                  for f in os.listdir(self.run_path)
                                  if f.startswith(f_header + '.')
                                  and f.split('.')[-2].startswith('t')
                                  and f.split('.')[-2].lstrip('t').isdigit()]
        
        for fname in tile_fnames:
            mnc.collate(tile_fnames[fname], os.path.join(self.run_path, fname))
        
        if clear_tiles:
            for fname in tile_fnames:
                for tile_fname in tile_fnames[fname]:
                    os.remove(tile_fname)
