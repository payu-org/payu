# coding: utf-8
"""
Payu: A generic driver for numerical models on the NCI computing cluster (vayu)
-------------------------------------------------------------------------------
Contact:    Marshall Ward (marshall.ward@anu.edu.au)
"""

import os
import sys
import shutil as sh
import subprocess as sp
import grp
import getpass
import errno

# Environment module support on vayu
execfile('/opt/Modules/default/init/python')

# Counter environment variable names
counter_env = 'count'
max_counter_env = 'max'
archive_server = 'dc.nci.org.au'

#==============================================================================
class Experiment(object):
    
    #---
    def __init__(self, **kwargs):
        self.model_name = None
        self.modules = None
        self.config_files = None
        
        # Script names
        self.model_script = kwargs.pop('model_script', 'model.py')
        self.collation_script = kwargs.pop('collate_script', 'collate.py')
        
        # Update counter variables
        self.set_counters()
    
    
    #---
    def set_counters(self):
        self.counter = int(os.environ.get(counter_env, 1))
        self.max_counter = int(os.environ.get(max_counter_env, self.counter))
        
        assert 0 < self.max_counter
        assert 0 < self.counter <= self.max_counter
    
    
    #---
    def load_modules(self):
        module('purge')
        for mod in self.modules:
            module('load', mod)
    
    
    #---
    def path_names(self, **kwargs):
        # A model name must be assigned
        assert self.model_name
        
        # Experiment name (used for directories)
        default_name = os.path.basename(os.getcwd())
        self.name = kwargs.pop('name', default_name)
        
        # Configuration path (input, config)
        default_config_path = os.getcwd()
        self.config_path = kwargs.pop('config', default_config_path)
        
        # Laboratory path (output)
        default_user = getpass.getuser()
        self.user_name = kwargs.pop('user', default_user)
        
        # Project group
        default_project = os.environ.get('PROJECT')
        self.project_name = kwargs.pop('project', default_project)
        
        # Output path
        default_lab_path = os.path.join('/','short', self.project_name,
                                        self.user_name, self.model_name)
        self.lab_path = kwargs.pop('output', default_lab_path)
        
        # Experiment subdirectories
        self.archive_path = os.path.join(self.lab_path, 'archive', self.name)
        self.bin_path = os.path.join(self.lab_path, 'bin')
        self.work_path = os.path.join(self.lab_path, 'work', self.name)
        
        # Symbolic path to work
        self.work_sym_path = os.path.join(self.config_path, 'work')
        self.archive_sym_path = os.path.join(self.config_path, 'archive')
        
        # Set group identifier for output
        self.archive_group = kwargs.pop('archive_group', None)
        
        # Executable path
        exec_name = kwargs.pop('exe', self.default_exec)
        self.exec_path = os.path.join(self.bin_path, exec_name)
        
        # Stream output filenames
        self.stdout_fname = self.model_name + '.out'
        self.stderr_fname = self.model_name + '.err'
        
        # External forcing path
        forcing_dir = kwargs.pop('forcing', None)
        if forcing_dir:
            # Test for absolute path
            if os.path.exists(forcing_dir):
                self.forcing_path = forcing_dir
            else:
                # Test for path relative to /lab_path/forcing
                rel_path = os.path.join(self.lab_path, 'forcing', forcing_dir)
                if os.path.exists(rel_path):
                    self.forcing_path = rel_path
                else:
                    # Forcing does not exist; raise some exception
                    sys.exit('Forcing data not found; aborting.')
        else:
            self.forcing_path = None
        
        # Local archive paths
        self.run_dir = 'run%02i' % (self.counter,)
        self.run_path = os.path.join(self.archive_path, self.run_dir)
        
        prior_run_dir = 'run%02i' % (self.counter - 1,)
        prior_run_path = os.path.join(self.archive_path, prior_run_dir)
        if os.path.exists(prior_run_path):
            self.prior_run_path = prior_run_path
        else:
            self.prior_run_path = None
    
    
    #---
    def setup(self):
        mkdir_p(self.work_path)
        
        if not os.path.exists(self.work_sym_path):
            os.symlink(self.work_path, self.work_sym_path)
        
        for f in self.config_files:
            f_path = os.path.join(self.config_path, f)
            sh.copy(f_path, self.work_path)
    
    
    #---
    def run(self, *mpi_flags):
        
        f_out = open(self.stdout_fname, 'w')
        f_err = open(self.stderr_fname, 'w')
        
        mpi_cmd = 'mpirun'  # OpenMPI execute
        
        # Convert flags to list of arguments
        flags = [c for flag in mpi_flags for c in flag.split(' ')]
        cmd = [mpi_cmd] + flags + [self.exec_path]
        
        rc = sp.Popen(cmd, stdout=f_out, stderr=f_err).wait()
        f_out.close()
        f_err.close()
        
        # Remove any empty output files (e.g. logs)
        for fname in os.listdir(self.work_path):
            fpath = os.path.join(self.work_path, fname)
            if os.path.getsize(fpath) == 0:
                os.remove(fpath)
        
        # TODO: Need a model-specific cleanup method call here
        if rc != 0:
            sys.exit('Error %i; aborting.' % rc)
        
        # Move logs to archive (or delete if empty)
        if os.path.getsize(self.stdout_fname) == 0:
            os.remove(self.stdout_fname)
        else:
            sh.move(self.stdout_fname, self.work_path)
            
        if os.path.getsize(self.stderr_fname) == 0:
            os.remove(self.stderr_fname)
        else:
            sh.move(self.stderr_fname, self.work_path)
    
    
    #---
    def archive(self, collate=True, mdss=False):
        mkdir_p(self.archive_path)
        
        # Create archive symlink
        if not os.path.exists(self.archive_sym_path):
            os.symlink(self.archive_path, self.archive_sym_path)
        
        # Remove work symlink
        if os.path.islink(self.work_sym_path):
            os.remove(self.work_sym_path)
        
        # Check if archive path already exists
        # TODO: Check before running, rather than archiving
        if os.path.exists(self.run_path):
            sys.exit('Archived path already exists; aborting.')
        sh.move(self.work_path, self.run_path)
        
        if self.archive_group:
            self.regroup()
        
        if collate:
            job_name = os.environ.get('PBS_JOBNAME', self.name)
            cmd = ['qsub', self.collation_script, '-v', '%s=%i'
                    % (counter_env, self.counter)]
            rc = sp.Popen(cmd).wait()
    
    
    #---
    def remote_archive(self, config_name):
        archive_address = '%s@%s' % (getpass.getuser(), archive_server)
        
        ssh_key_path = os.path.join(os.getenv('HOME'), '.ssh',
                                    'id_rsa_file_transfer')
        
        # Top-level path is set by the SSH key
        # (Usually /projects/[group])
        
        # Remote mkdir is currently not possible, so any new subdirectories
        # must be created before auto-archival
        
        remote_path = os.path.join(self.model_name, config_name,
                                   self.name)
        
        # TODO: how to remove shell=True ?
        cmd = 'rsync -a --safe-links -e "ssh -i %s" %s %s:%s' % \
                (ssh_key_path, self.run_path, archive_address, remote_path)
        rc = sp.Popen(cmd, shell=True).wait()
        assert rc == 0
    
    
    #---
    def regroup(self):
        uid = os.getuid()
        gid = grp.getgrnam(self.archive_group).gr_gid
        
        os.lchown(self.archive_path, uid, gid)
        for root, dirs, files in os.walk(self.archive_path):
            for d in dirs:
                os.lchown(os.path.join(root, d), uid, gid)
            for f in files:
                os.lchown(os.path.join(root, f), uid, gid)
    
    
    #---
    def resubmit(self):
        assert self.counter < self.max_counter
        self.counter += 1
        cmd = ['qsub', self.model_script, '-v', '%s=%i,%s=%i'
                % (counter_env, self.counter, max_counter_env,
                   self.max_counter) ]
        sp.Popen(cmd).wait()


#==============================================================================
def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError, exc:
        if exc.errno != errno.EEXIST:
            raise
