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

class mitgcm(Experiment):
    
    def __init__(self, **kwargs):
        
        # payu initalisation
        super(mitgcm, self).__init__(**kwargs)
        
        # Model-specific configuration
        self.model_name = 'mitgcm'
        self.default_exec = 'mitgcmuv'
        self.modules = ['pbs',
                        'openmpi',
                        'netcdf']
       
        # TODO: List is dynamic, need optional file list?
        self.config_files = ['data',
                             'data.mnc',
                             'data.pkg',
                             'data.diagnostics',
                             'data_cadj',
                             'eedata']
        
        self.path_names(**kwargs)
    
    
    #---
    def build(self):
        raise NotImplementedError
    
    
    #---
    def setup(self, use_symlinks=True, repeat_run=False):
        
        # payu setup
        super(mitgcm, self).setup()
        
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
    # TODO: Move this to payu, generalise flag arguments
    def run(self, *flags):
        stdout_fname = 'std.out'
        stderr_fname = 'std.err'
        
        f_out = open(stdout_fname, 'w')
        f_err = open(stderr_fname, 'w')
        
        cmd = (['mpirun'] + list(flags)
                + ['-mca', 'mpi_affinity_alone', '1']
                + ['-wd', self.work_path]
                + [self.exec_path])
        
        rc = sp.Popen(cmd, stdout=f_out, stderr=f_err).wait()
        f_out.close()
        f_err.close()
        
        if rc != 0:
            sys.exit('Error %i; aborting.' % rc)
        
        sh.move(stdout_fname, self.work_path)
        sh.move(stderr_fname, self.work_path)
   

    #---
    def collate(self):
        raise NotImplementedError
