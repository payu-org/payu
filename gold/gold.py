# coding: utf-8
"""
The payu implementation of GOLD
===============================================================================
Comments:
    - The 'run_dir' stuff should probably be model-independent
"""

from payu import Model, mkdir_p
import os
import shutil as sh
import subprocess as sp

class _GOLD(Model):
    #----------------------------
    def __init__(self, **kwargs):
        self.name = 'GOLD'
        self.modules = ['pbs', 'openmpi','ipm']
        self.default_exec = 'GOLD'

    #---------------
    def build(self):
        # Not yet implemented
        pass
    
    #---------------------
    def setup(self, expt):
        # Copy configuration files to the experiment directory
        
        config_files = ['GOLD_input', 'GOLD_override', 'diag_table',
                        'input.nml']
        
        for f in config_files:
            f_path = os.path.join(expt.config_path, f)
            sh.copy(f_path, expt.work_path)
        
        if expt.counter == 1:
            self.init_config(expt.work_path)
        
        # Create experiment directory structure
        restart_path = os.path.join(expt.work_path, 'RESTART')    
        mkdir_p(restart_path)
        
        input_path = os.path.join(expt.work_path, 'INPUT')
        if expt.counter == 1:
            mkdir_p(input_path)
        else:
            last_run_dir = 'run%02i' % (expt.counter-1,)
            last_restart_path = os.path.join(expt.archive_path, last_run_dir,
                                             'RESTART')
            os.symlink(last_restart_path, input_path)
    
    #--------------------------------
    def init_config(self, path):
        input_filepath = os.path.join(path, 'input.nml')
        temp_filepath  = ''.join([input_filepath, '~'])
        
        input_file = open(input_filepath)
        temp_file  = open(temp_filepath, 'w')
        
        for line in input_file:
            temp_file.write(line.replace("input_filename = 'r'",
                                         "input_filename = 'n'"))
        
        input_file.close()
        temp_file.close()
        sh.move(temp_filepath, input_filepath)
    
    #-----------------------------------
    def run(self, expt_path, exec_path):
        cmd = ['mpirun', '-wd', expt_path, exec_path, '>', 'zz.out']
        rc = sp.Popen(cmd).wait()
    
    #-----------------
    def collate(self, expt):
        import resource as res

        # Set the stacksize to be unlimited
        res.setrlimit(res.RLIMIT_STACK, (res.RLIM_INFINITY, res.RLIM_INFINITY))
        
        run_dir = 'run%02i' % (expt.counter,)
        run_path = os.path.join(expt.archive_path, run_dir)
        nc_files = [os.path.join(run_path, f) for f in os.listdir(run_path) \
                    if f.endswith('.nc.0000')]

        mppnc_path = os.path.join(expt.bin_path, 'mppnccombine')
        
        for f in nc_files:
            cmd = [mppnc_path, '-r', f]
            sp.Popen(cmd).wait()

