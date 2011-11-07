# coding: utf-8
"""
The payu implementation of GOLD
===============================================================================
Comments:
    - This is undergoing a major rewrite:
        GOLD() is now a subclass of Experiment
    - The 'run_dir' stuff should probably be model-independent
"""

from payu import Experiment, mkdir_p
import os
import shutil as sh
import subprocess as sp

class GOLD(Experiment):
    #----------------------------
    def __init__(self, **kwargs):
        
        # Model-specific configuration
        self.model_name = 'GOLD'
        self.default_exec = 'GOLD'
        self.modules = ['pbs', 'openmpi','ipm']
        
        self.load_modules()
        self.set_counters()
        self.path_names(**kwargs)
    
    #---------------
    def build(self):
        # Not yet implemented
        pass
    
    #---------------
    def setup(self):
        mkdir_p(self.work_path)
        
        # Copy configuration files to the experiment directory
        config_files = ['GOLD_input', 'GOLD_override', 'diag_table',
                        'input.nml']
        
        for f in config_files:
            f_path = os.path.join(self.config_path, f)
            sh.copy(f_path, self.work_path)
        
        if self.counter == 1:
            self.init_config()
        
        # Create experiment directory structure
        restart_path = os.path.join(self.work_path, 'RESTART')    
        mkdir_p(restart_path)
        
        input_path = os.path.join(self.work_path, 'INPUT')
        if self.counter == 1:
            mkdir_p(input_path)
        else:
            last_run_dir = 'run%02i' % (self.counter-1,)
            last_restart_path = os.path.join(self.archive_path, last_run_dir,
                                             'RESTART')
            os.symlink(last_restart_path, input_path)
    
    #---------------------
    def init_config(self):
        input_filepath = os.path.join(self.work_path, 'input.nml')
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
    def run(self):
        cmd = ['mpirun', '-wd', self.work_path, self.exec_path]
        rc = sp.Popen(cmd).wait()
    
    #-----------------
    def collate(self):
        import resource as res
        
        # Set the stacksize to be unlimited
        res.setrlimit(res.RLIMIT_STACK, (res.RLIM_INFINITY, res.RLIM_INFINITY))
        
        run_dir = 'run%02i' % (self.counter,)
        run_path = os.path.join(self.archive_path, run_dir)
        nc_files = [os.path.join(run_path, f) for f in os.listdir(run_path) \
                    if f.endswith('.nc.0000')]
        
        mppnc_path = os.path.join(self.bin_path, 'mppnccombine')
        
        for f in nc_files:
            cmd = [mppnc_path, '-r', f]
            sp.Popen(cmd).wait()

