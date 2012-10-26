#!/usr/bin/env python
# coding: utf-8
"""
The payu interface for GFDL models based on FMS
-------------------------------------------------------------------------------
Contact: Marshall Ward <marshall.ward@anu.edu.au>
-------------------------------------------------------------------------------
Distributed as part of Payu, Copyright 2011-2012 Marshall Ward
Licensed under the Apache License, Version 2.0
http://www.apache.org/licenses/LICENSE-2.0
"""

from payu import Experiment, mkdir_p
import os
import sys
import shutil as sh
import subprocess as sp

class fms(Experiment):
    
    #---
    def __init__(self, **kwargs):
        
        # payu initalisation
        super(fms, self).__init__(**kwargs)
    
    
    #---
    def path_names(self, **kwargs):
        super(fms, self).path_names(**kwargs)
        
        # Define local FMS directories
        self.work_res_path = os.path.join(self.work_path, 'RESTART')
        self.input_path = os.path.join(self.work_path, 'INPUT')
    
    
    #---
    def build(self):
        raise NotImplementedError
    
    
    #---
    def setup(self, use_symlinks=True, repeat_run=False):
        
        # payu setup:
        #   work path and symlink, config file copy
        super(fms, self).setup()
        
        # Create experiment directory structure
        mkdir_p(self.work_res_path)
        
        # Either create a new INPUT path or link a previous RESTART as INPUT
        mkdir_p(self.input_path)
        
        if self.counter > 1 and not repeat_run:
            restart_files = os.listdir(self.prior_res_path)
            for f in restart_files:
                f_res = os.path.join(self.prior_res_path, f)
                f_input = os.path.join(self.input_path, f)
                if use_symlinks:
                    os.symlink(f_res, f_input)
                else:
                    sh.copy(f_res, f_input)
        
        # Link any forcing data to INPUT
        if self.forcing_path:
            forcing_files = os.listdir(self.forcing_path)
            for f in forcing_files:
                f_forcing = os.path.join(self.forcing_path, f)
                f_input = os.path.join(self.input_path, f)
                # Do not use forcing file if it is in RESTART
                if not os.path.exists(f_input):
                    if use_symlinks:
                        os.symlink(f_forcing, f_input)
                    else:
                        sh.copy(f_forcing, f_input)
    
    
    #---
    def run(self, *flags):
        flags = flags + ('-wd %s' % self.work_path, )
        super(fms, self).run(*flags)
    
    
    #--
    def archive(self, **kwargs):
        
        # Remove the 'INPUT' path
        cmd = 'rm -rf {path}'.format(path=self.input_path).split()
        rc = sp.Popen(cmd).wait()
        assert rc == 0
        
        # Archive restart files before processing model output
        mkdir_p(self.archive_path)
        cmd = 'mv {src} {dst}'.format(src=self.work_res_path,
                                      dst=self.res_path).split()
        rc = sp.Popen(cmd).wait()
        assert rc == 0
        
        super(fms, self).archive(**kwargs)
    
    
    #---
    def collate(self, restart=False):
        import resource as res
        
        # Set the stacksize to be unlimited
        res.setrlimit(res.RLIMIT_STACK, (res.RLIM_INFINITY, res.RLIM_INFINITY))
        
        restart_path = os.path.join(self.run_path, 'RESTART')
        
        nc_files = [os.path.join(self.run_path, f)
                    for f in os.listdir(self.run_path)
                    if f.endswith('.nc.0000')]
        
        if restart:
            restart_files = [os.path.join(restart_path, f)
                             for f in os.listdir(restart_path)
                             if f.endswith('.nc.0000')]
            nc_files.extend(restart_files)
        
        mppnc_path = os.path.join(self.bin_path, 'mppnccombine')
        
        for f in nc_files:
            cmd = [mppnc_path, '-r', '-64', f]
            sp.Popen(cmd).wait()
        
        if self.archive_group:
            self.regroup()
