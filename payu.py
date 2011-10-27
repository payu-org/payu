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

# Global macros
default_script = 'model.py'

short_path = '/short'

archive_dir = 'archive'
work_dir = 'work'
bin_dir = 'bin'

counter_envar = 'count'
max_counter_envar = 'max'

#==============================================================================
class Experiment(object):
    """Abstraction of a particular experiment on vayu"""
    
    #------------------------------------------
    def __init__(self, model, **kwargs):
        self.model = model
        self.driver_script = kwargs.pop('driver', default_script)
        
        # Experiment name (used for directories)
        default_name = os.path.basename(os.getcwd())
        self.name = kwargs.pop('name', default_name)
        
        # Configuration path (input, config)
        default_config_path = os.getcwd()
        self.config_path = kwargs.pop('config', default_config_path)
        
        # Laboratory path (output)
        user_name = os.environ.get('USER')
        project_name = os.environ.get('PROJECT')
        default_lab_path = os.path.join(short_path, project_name, user_name,
                                        model.name)
        self.lab_path = kwargs.pop('output', default_lab_path)
        
        # Executable path
        default_bin_path = os.path.join(self.lab_path, bin_dir)
        self.bin_path = kwargs.pop('bin', default_bin_path)
        
        exec_name = kwargs.pop('exec', model.default_exec)
        self.exec_path = os.path.join(self.bin_path, exec_name)
        
        # Experiment subdirectories
        self.archive_path = os.path.join(self.lab_path, archive_dir, self.name)
        self.work_path = os.path.join(self.lab_path, work_dir, self.name)
       
        #--------------------------
        # Initialize the experiment
        self.load_modules()
        self.set_counters()
    
    
    #----------------------
    def load_modules(self):
        module('purge')
        for mod in self.model.modules:
            module('load', mod)
    
    
    #----------------------
    def set_counters(self):
    # May want to force max to equal counter if only the latter is specified
        
        self.max_counter = int(os.environ.get(max_counter_envar, 1))
        self.counter = int(os.environ.get(counter_envar, 1))
        
        assert 0 < self.max_counter
        assert 0 < self.counter <= self.max_counter
    
    
    #----------------------------
    def setup(self):
        
        # Create workspace directory
        mkdir_p(self.work_path)
        
        self.model.setup(self)
    
    
    #-------------
    def run(self):
        self.setup()
        self.model.run(self.work_path, self.exec_path)
        self.archive()
        if self.counter < self.max_counter:
            self.resubmit()
    
    #-----------------
    def archive(self):
        mkdir_p(self.archive_path)
        
        # run directory name could be less restrictive
        run_dir = 'run%02i' % (self.counter,)
        run_path = os.path.join(self.archive_path, run_dir)
        sh.move(self.work_path, run_path)
         
        # Collate the tiled results (optional? e.g. if model.do_collate)
        qsub_vars = ''.join([counter_envar, '=', str(self.counter), ',',
                             'collate=True'])
        cmd = ['qsub', self.driver_script, '-q', 'copyq', '-l', 'ncpus=1',
               '-N', ''.join([self.name, '_coll']), '-v', qsub_vars]
        rc = sp.Popen(cmd).wait()
    
    
    #-----------------
    def collate(self):
        self.model.collate(self)
    
    
    #------------------
    def resubmit(self):
        assert self.counter < self.max_counter
        self.counter += 1
        cmd = ['qsub', self.driver_script, '-v', '%s=%i,%s=%i'
                % (counter_envar, self.counter, max_counter_envar,
                   self.max_counter) ]
        sp.Popen(cmd).wait()


#==============================================================================
class Model(object):
    """Abstraction of numerical models on vayu"""
    # Most of these methods are defined by individual models (i.e. polymorphism)
    
    def __init__(self, *args, **kwargs):
        self.model_name = None
        self.default_exec = None
    
    def build(self):
        raise NotImplementedError('Subclass must implement build automation.')
    
    def setup(self):
        raise NotImplementedError('Subclass must implement experiment setup.')

    def run(self):
        raise NotImplementedError('Subclass much implement model execution.')

#==============================================================================
def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError, exc:
        if exc.errno != errno.EEXIST:
            raise


