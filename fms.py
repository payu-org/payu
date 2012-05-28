# coding: utf-8
"""
The payu interface for GFDL models based on FMS
===============================================================================
Primary Contact:    Marshall Ward (marshall.ward@anu.edu.au)
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
        
        # Model-specific configuration
        self.modules = ['pbs',
                        'openmpi']
    
    
    #---
    def build(self):
        raise NotImplementedError
    
    
    #---
    def setup(self, use_symlinks=True, repeat_run=False):
        
        # payu setup:
        #   work path and symlink, config file copy
        super(fms, self).setup()
        
        # Create experiment directory structure
        restart_path = os.path.join(self.work_path, 'RESTART')    
        mkdir_p(restart_path)
        
        # David Singleton's striping recommedation
        cmd = ['lfs', 'setstripe', '-c', '8', '-s','8m', restart_path]
        rc = sp.Popen(cmd).wait()
        assert rc == 0
        
        # Either create a new INPUT path or link a previous RESTART as INPUT
        input_path = os.path.join(self.work_path, 'INPUT')
        mkdir_p(input_path)
        
        if self.counter > 1 and not repeat_run:
            last_run_dir = 'run%02i' % (self.counter-1,)
            last_restart_path = os.path.join(self.archive_path, last_run_dir,
                                             'RESTART')
            restart_files = os.listdir(last_restart_path)
            for f in restart_files:
                f_res = os.path.join(last_restart_path, f)
                f_input = os.path.join(input_path, f)
                if use_symlinks:
                    os.symlink(f_res, f_input)
                else:
                    sh.copy(f_res, f_input)
        else:
            last_restart_path = None
        
        # Link any forcing data to INPUT
        if self.forcing_path:
            forcing_files = os.listdir(self.forcing_path)
            for f in forcing_files:
                f_forcing = os.path.join(self.forcing_path, f)
                f_input = os.path.join(input_path, f)
                # Do not use forcing file if it is in RESTART
                if not os.path.exists(f_input):
                    if use_symlinks:
                        os.symlink(f_forcing, f_input)
                    else:
                        sh.copy(f_forcing, f_input)
    
    
    #---
    def run(self, *flags):
        f_out = open('fms.out','w')
        f_err = open('fms.err','w')
        
        cmd = (['mpirun'] + list(flags) + ['-wd', self.work_path]
                + [self.exec_path])
        
        rc = sp.Popen(cmd, stdout=f_out, stderr=f_err).wait()
        f_out.close()
        f_err.close()
        
        if rc != 0:
            sys.exit('Error %i; aborting.' % rc)
        
        sh.move('fms.out', self.work_path)
        sh.move('fms.err', self.work_path)
    
    
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
