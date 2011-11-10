# coding: utf-8
"""
Payu: A generic driver for numerical models on the NCI computing cluster (vayu)
-------------------------------------------------------------------------------
Primary Contact:    Marshall Ward (marshall.ward@anu.edu.au)
"""

import os
import sys
import shutil as sh
import subprocess as sp
import errno

# Environment module support on vayu
execfile('/opt/Modules/default/init/python')

# Counter environment variable names
counter_envar = 'count'
max_counter_envar = 'max'

#==============================================================================
class Experiment(object):
    """Abstraction of a generic experiment on vayu"""
    
    #------------------------------------------
    def __init__(self, **kwargs):
        self.model_name = None
        self.modules = None
    
    
    #----------------------
    def set_counters(self):
        self.counter = int(os.environ.get(counter_envar, 1))
        self.max_counter = int(os.environ.get(max_counter_envar, self.counter))
        
        assert 0 < self.max_counter
        assert 0 < self.counter <= self.max_counter
    
    
    #----------------------
    def load_modules(self):
        module('purge')
        for mod in self.modules:
            module('load', mod)
    
    
    #----------------------
    def path_names(self, **kwargs):
        # A model name must be assigned
        assert self.model_name
        
        # Submission script name
        default_script_name = 'model.py'
        self.driver_script = kwargs.pop('script_name', default_script_name)
        
        # Experiment name (used for directories)
        default_name = os.path.basename(os.getcwd())
        self.name = kwargs.pop('name', default_name)
        
        # Configuration path (input, config)
        default_config_path = os.getcwd()
        self.config_path = kwargs.pop('config', default_config_path)
        
        # Laboratory path (output)
        user_name = os.environ.get('USER')
        project_name = os.environ.get('PROJECT')
        default_lab_path = os.path.join('/','short', project_name, user_name,
                                        self.model_name)
        self.lab_path = kwargs.pop('output', default_lab_path)
        
        # Experiment subdirectories
        self.archive_path = os.path.join(self.lab_path, 'archive', self.name)
        self.bin_path = os.path.join(self.lab_path, 'bin')
        self.work_path = os.path.join(self.lab_path, 'work', self.name)
        
        # Executable path
        exec_name = kwargs.pop('exe', self.default_exec)
        self.exec_path = os.path.join(self.bin_path, exec_name)
        
        # Driver path
        self.driver_path = kwargs.pop('forcing', None)
    
    
    #-----------------
    def archive(self):
        mkdir_p(self.archive_path)
        
        run_dir = 'run%02i' % (self.counter,)
        run_path = os.path.join(self.archive_path, run_dir)
        
        sh.move(self.work_path, run_path)
        
        # Collate the tiled results
        job_name = os.environ.get('PBS_JOBNAME', self.name)
        collate_job_name = ''.join([job_name, '_coll'])
        qsub_vars = ''.join([counter_envar, '=', str(self.counter), ',',
                             'collate','=','True'])
        cmd = ['qsub', self.driver_script,
                 '-q', 'copyq',
                 '-l', 'ncpus=1',
                 '-l', 'vmem=6GB',
                 '-l', 'walltime=2:00:00',
                 '-N', collate_job_name,
                 '-v', qsub_vars]
        rc = sp.Popen(cmd).wait()
    
    
    #------------------
    def resubmit(self):
        assert self.counter < self.max_counter
        self.counter += 1
        cmd = ['qsub', self.driver_script, '-v', '%s=%i,%s=%i'
                % (counter_envar, self.counter, max_counter_envar,
                   self.max_counter) ]
        sp.Popen(cmd).wait()


    #----------------------
    def do_collation(self):
        return ( os.environ.get('collate', False) == 'True' )

#==============================================================================
def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError, exc:
        if exc.errno != errno.EEXIST:
            raise


