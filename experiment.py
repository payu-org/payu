#!/usr/bin/env python
# coding: utf-8
"""
Payu: A generic driver for numerical models on the NCI computing clusters
-------------------------------------------------------------------------------
Contact: Marshall Ward <marshall.ward@anu.edu.au>
-------------------------------------------------------------------------------
Distributed as part of Payu, Copyright 2011 Marshall Ward
Licensed under the Apache License, Version 2.0
http://www.apache.org/licenses/LICENSE-2.0
"""

# Python3 preparation
from __future__ import print_function

# Standard Library
import errno
import grp
import getpass
import os
import pwd
import resource
import sys
import shlex
import shutil as sh
import subprocess as sp

# Extensions
import yaml

# Local
from fsops import mkdir_p, make_symlink
from modelindex import index as model_index

# Environment module support on vayu
execfile('/opt/Modules/default/init/python')
module_path = '/projects/v45/modules'
core_modules = ['python', 'payu']

# Default payu parameters
default_archive_url = 'dc.nci.org.au'
default_config_fname = 'config.yaml'
default_restart_freq = 5

#==============================================================================
class Experiment(object):

    #---
    def __init__(self, **kwargs):

        # Disable group write access and all public access
        perms = 0o0027
        os.umask(perms)

        # TODO: __init__ should not be a config dumping ground!
        self.read_config()

        # Initialize the submodels
        self.init_models()

        # TODO: Move to run/collate/sweep?
        self.set_pbs_config()
        self.set_lab_pathnames()
        self.set_run_pathnames()
        self.set_counters()

        self.set_input_paths()
        self.set_output_paths()

        stacksize = self.config.get('stacksize')
        if stacksize:
            self.set_stacksize(stacksize)

        # TODO: Move this somewhere else
        self.postscript = self.config.get('postscript')


    #---
    def read_config(self):
        # TODO: Parse the PAYU_CONFIGPATH envar
        config_fname = default_config_fname

        try:
            with open(config_fname, 'r') as config_file:
                self.config = yaml.load(config_file)
        except IOError as ec:
            if ec.errno == errno.ENOENT:
                self.config = {}
            else:
                raise


    #---
    def init_models(self):

        # TODO: Dict or list? Do I need the mapping?
        self.models = []

        submodels = self.config.get('submodels', {})
        if not submodels:

            solo_model = self.config.get('model')
            if not solo_model:
                sys.exit('payu: error: Missing model configuration.')

            model_fields = {'model', 'exe', 'input', 'ncpus'}
            submodels['solo'] = {f: self.config[f] for f in model_fields}

        # TODO: Warn the user if 'submodels' and 'model' are set
        #       Or append it to submodels?

        for m_name, m_config in submodels.iteritems():

            ModelType = model_index[m_config['model']]
            self.models.append(ModelType(m_config))


    #---
    def set_counters(self):
        # Assume that ``set_paths`` has already been called
        assert self.archive_path

        current_counter = os.environ.get('PAYU_CURRENT_RUN')
        if current_counter:
            self.counter = int(current_counter)
        else:
            self.counter = None

        self.n_runs = int(os.environ.get('PAYU_N_RUNS', 1))

        # Initialize counter if unset
        if self.counter is None:
            # TODO: this logic can probably be streamlined
            try:
                restart_dirs = [d for d in os.listdir(self.archive_path)
                                if d.startswith('restart')]
            except OSError as ec:
                if ec.errno == errno.ENOENT:
                    restart_dirs = None
                else:
                    raise

            if restart_dirs:
                self.counter = 1 + max([int(d.lstrip('restart'))
                                        for d in restart_dirs
                                        if d.startswith('restart')])
            else:
                self.counter = 0


    #---
    def set_stacksize(self, stacksize):

        if stacksize == 'unlimited':
            stacksize = resource.RLIM_INFINITY
        else:
            # TODO: User-friendly explanation
            assert type(stacksize) is int

        resource.setrlimit(resource.RLIMIT_STACK,
                           (stacksize, resource.RLIM_INFINITY))


    #---
    def load_modules(self):
        # TODO: ``reversion`` makes a lot of this redundant

        # Unload non-essential modules
        loaded_mods = os.environ.get('LOADEDMODULES', '').split(':')

        for mod in loaded_mods:
            mod_base = mod.split('/')[0]
            if not mod_base in core_modules:
                module('unload', mod)

        # Now load model-dependent modules
        for mod in self.modules:
            module('load', mod)

        # TODO: Improved ipm support
        if 'ipm' in self.modules:
            os.environ['IPM_LOGDIR'] = self.work_path


    #---
    def set_pbs_config(self):

        default_n_cpus = os.environ.get('PBS_NCPUS', 1)
        self.n_cpus = self.config.get('ncpus', default_n_cpus)

        self.n_cpus_per_node = self.config.get('npernode')

        default_job_name = os.path.basename(os.getcwd())
        self.job_name = self.config.get('jobname', default_job_name)

        # Set group identifier for output
        # TODO: Do we even use this anymore? It's too slow
        #       Use the qsub flag?
        self.archive_group = self.config.get('archive_group')


    #---
    def set_lab_pathnames(self):

        # Local "control" path
        self.control_path = self.config.get('control', os.getcwd())

        # Top-level "short term storage" path
        default_short_path = os.path.join('/short', os.environ.get('PROJECT'))
        self.short_path = self.config.get('shortpath', default_short_path)

        default_user = pwd.getpwuid(os.getuid()).pw_name
        self.user_name = self.config.get('user', default_user)

        # Identify the laboratory
        lab_name = self.config.get('laboratory')

        # If there is only one model, then use the model laboratory
        if not lab_name:
            if len(self.models) == 1:
                lab_name = self.models[0].model_name
            else:
                sys.exit('payu: error: Laboratory could not be determined.')

        # Lab name should be defined at this point
        assert lab_name

        # Construct the laboratory absolute path if necessary
        if os.path.isabs(lab_name):
                self.lab_path = lab_name
        else:
            # Check under the default root path
            self.lab_path = os.path.join(self.short_path, self.user_name,
                                         lab_name)
        # Validate the path
        if not os.path.isdir(self.lab_path):
            sys.exit('payu: error: Laboratory path {} not found.'
                     ''.format(self.lab_path))

        # Executable directory path ("bin")
        self.bin_path = os.path.join(self.lab_path, 'bin')

        # Experiment input path
        self.input_basepath = os.path.join(self.lab_path, 'input')


    #---
    def set_run_pathnames(self):

        # Experiment name
        assert self.control_path
        default_experiment = os.path.basename(self.control_path)
        self.experiment = self.config.get('experiment', default_experiment)

        # Experiment subdirectories
        assert self.lab_path
        self.archive_path = os.path.join(self.lab_path, 'archive',
                                         self.experiment)
        self.work_path = os.path.join(self.lab_path, 'work', self.experiment)

        # Symbolic paths to output
        self.work_sym_path = os.path.join(self.control_path, 'work')
        self.archive_sym_path = os.path.join(self.control_path, 'archive')

        # Executable path
        assert self.bin_path
        assert self.default_exec
        assert self.model_name
        exec_name = self.config.get('exe', self.default_exec)
        self.exec_path = os.path.join(self.bin_path, exec_name)

        # Stream output filenames
        self.stdout_fname = self.model_name + '.out'
        self.stderr_fname = self.model_name + '.err'


    #---
    def set_input_paths(self):
        # TODO: Replace old self.input_path references in payu

        input_dirs = self.config.get('input')
        if input_dirs is None:
            input_dirs = []
        elif type(input_dirs) == str:
            input_dirs = [input_dirs]

        self.input_paths = []
        for input_dir in input_dirs:

            # First test for absolute path
            if os.path.exists(input_dir):
                self.input_paths.append(input_dir)
            else:
                # Test for path relative to /${lab_path}/input
                assert self.input_basepath
                rel_path = os.path.join(self.input_basepath, input_dir)
                if os.path.exists(rel_path):
                    self.input_paths.append(rel_path)
                else:
                    sys.exit('payu: error: Input directory {} not found; '
                             'aborting.'.format(rel_path))


    #---
    def set_output_paths(self):
        # Local archive paths
        output_dir = 'output{:03}'.format(self.counter)
        self.output_path = os.path.join(self.archive_path, output_dir)

        # TODO: check case counter == 0
        prior_output_dir = 'output{:03}'.format(self.counter - 1)
        prior_output_path = os.path.join(self.archive_path, prior_output_dir)
        if os.path.exists(prior_output_path):
            self.prior_output_path = prior_output_path
        else:
            self.prior_output_path = None

        # Local restart paths
        res_dir = 'restart{:03}'.format(self.counter)
        self.res_path = os.path.join(self.archive_path, res_dir)

        prior_res_dir = 'restart{:03}'.format(self.counter - 1)
        prior_res_path = os.path.join(self.archive_path, prior_res_dir)
        if os.path.exists(prior_res_path):
            self.prior_res_path = prior_res_path
        else:
            self.prior_res_path = None
            if self.counter > 0:
                # TODO: This warning should be replaced with an abort in setup
                print('Warning: no restart files found.')


    #---
    def init(self):

        assert self.lab_path
        mkdir_p(self.lab_path)

        assert self.input_basepath
        mkdir_p(self.input_basepath)

        # Check out source code
        self.get_codebase()
        self.build_model()


    #---
    def get_codebase():
        raise NotImplementedError


    #---
    def build_model():
        raise NotImplementedError


    #---
    def setup(self, do_stripe=False):

        # Confirm that no output path already exists
        if os.path.exists(self.output_path):
            sys.exit('Archived path already exists; aborting.')

        mkdir_p(self.work_path)

        # Stripe directory in Lustre
        if do_stripe:
            cmd = 'lfs setstripe -c 8 -s 8m {}'.format(self.work_path)
            cmd = shlex.split(cmd)
            rc = sp.call(cmd)
            assert rc == 0

        make_symlink(self.work_path, self.work_sym_path)

        for f in self.config_files:
            f_path = os.path.join(self.control_path, f)
            sh.copy(f_path, self.work_path)


    #---
    def run(self, *user_flags):
        f_out = open(self.stdout_fname, 'w')
        f_err = open(self.stderr_fname, 'w')

        mpirun_cmd = 'mpirun'

        mpi_flags = self.config.get('mpirun', [])
        if type(mpi_flags) != list:
            mpi_flags = [mpi_flags]
        # TODO: Assert that np and npernode are not in the mpirun flags

        if self.n_cpus:
            mpi_flags.append('-np {}'.format(self.n_cpus))

        if self.n_cpus_per_node:
            mpi_flags.append('-npernode {}'.format(self.n_cpus_per_node))

        # XXX: I think this may be broken
        if user_flags:
            mpi_flags.extend(list(user_flags))

        cmd = ' '.join([mpirun_cmd, ' '.join(mpi_flags), self.exec_path])
        cmd = shlex.split(cmd)

        rc = sp.call(cmd, stdout=f_out, stderr=f_err)
        f_out.close()
        f_err.close()

        # Remove any empty output files (e.g. logs)
        for fname in os.listdir(self.work_path):
            fpath = os.path.join(self.work_path, fname)
            if os.path.getsize(fpath) == 0:
                os.remove(fpath)

        # TODO: Need a model-specific cleanup method call here
        if rc != 0:
            sys.exit('Error {}; aborting.'.format(rc))

        # Decrement run counter on successful run

        # TODO: Create a stop_file subcommand
        stop_file_path = os.path.join(self.control_path, 'stop_run')
        if os.path.isfile(stop_file_path):
            assert os.stat(stop_file_path).st_size == 0
            os.remove(stop_file_path)
            print('payu: Stop file detected; terminating resubmission.')
            self.n_runs = 0
        else:
            self.n_runs -= 1

        # Move logs to archive (or delete if empty)
        for f in (self.stdout_fname, self.stderr_fname):
            if os.path.getsize(f) == 0:
                os.remove(f)
            else:
                sh.move(f, self.work_path)


    #---
    def archive(self, collate=True):
        mkdir_p(self.archive_path)

        make_symlink(self.archive_path, self.archive_sym_path)

        # Remove work symlink
        if os.path.islink(self.work_sym_path):
            os.remove(self.work_sym_path)

        # Double-check that the run path does not exist
        if os.path.exists(self.output_path):
            sys.exit('Archived path already exists; aborting.')

        cmd = 'mv {} {}'.format(self.work_path, self.output_path)
        rc = sp.call(cmd.split())
        assert rc == 0

        if self.archive_group:
            self.regroup()

        # TODO: restart archival is handled by each model. Abstract this!

        # TODO: delete old restarts
        restart_freq = self.config.get("restart_freq", default_restart_freq)

        if (self.counter >= restart_freq and self.counter % restart_freq == 0):
            i_s = self.counter - restart_freq
            i_e = self.counter - 1
            prior_res_dirs = ('restart{:03}'.format(i)
                              for i in range(i_s, i_e))

            for res_dirname in prior_res_dirs:
                res_path = os.path.join(self.archive_path, res_dirname)
                cmd = 'rm -rf {}'.format(res_path)
                cmd = shlex.split(cmd)
                try: sp.check_call(cmd)
                except CalledProcessError:
                    print('payu: warning: Could not delete directories {}'
                          ''.format(' '.join(prior_res_dirs)))

        if collate:
            cmd = 'payu collate -i {}'.format(self.counter)

            cmd = shlex.split(cmd)
            rc = sp.Popen(cmd).wait()
            assert rc == 0


    #---
    def postprocess(self):
        """Submit a postprocessing script after collation"""
        assert self.postscript

        cmd = 'qsub {}'.format(self.postscript)

        cmd = shlex.split(cmd)
        rc = sp.call(cmd)
        assert rc == 0, 'Postprocessing script submission failed.'


    #---
    def remote_archive(self, config_name, archive_url=None,
                       max_rsync_attempts=1, rsync_protocol=None):

        if not archive_url:
            archive_url = default_archive_url

        archive_address = '{usr}@{url}'.format(usr=getpass.getuser(),
                                               url=archive_url)

        ssh_key_path = os.path.join(os.getenv('HOME'), '.ssh',
                                    'id_rsa_file_transfer')

        # Top-level path is implicitly set by the SSH key
        # (Usually /projects/[group])

        # Remote mkdir is currently not possible, so any new subdirectories
        # must be created before auto-archival

        remote_path = os.path.join(self.model_name, config_name, self.name)
        remote_url = '{addr}:{path}'.format(addr=archive_address,
                                            path=remote_path)

        # Rsync ouput and restart files
        rsync_cmd = 'rsync -a --safe-links -e "ssh -i {key}" '.format(
                        key=ssh_key_path)

        if rsync_protocol:
            rsync_cmd += '--protocol={p} '.format(p=rsync_protocol)

        run_cmd = rsync_cmd + '{src} {dst}'.format(src=self.output_path,
                                                   dst=remote_url)
        rsync_calls = [run_cmd]

        if (self.counter % 5) == 0 and os.path.isdir(self.res_path):
            # Tar restart files before rsyncing
            res_tar_path = self.res_path + '.tar.gz'

            cmd = 'tar -C {path} -czf {fpath} {res}'.format(
                        path=self.archive_path,
                        fpath=res_tar_path,
                        res=os.path.basename(self.res_path)
                        ).split()
            rc = sp.Popen(cmd).wait()

            restart_cmd = rsync_cmd + '{src} {dst}'.format(src=res_tar_path,
                                                           dst=remote_url)
            rsync_calls.append(restart_cmd)
        else:
            res_tar_path = None

        for input_path in self.input_paths:
            # Using explicit path separators to rename the input directory
            input_cmd = rsync_cmd + '{src} {dst}'.format(
                            src = input_path + os.path.sep,
                            dst = os.path.join(remote_url, 'input')
                                    + os.path.sep)
            rsync_calls.append(input_cmd)

        for cmd in rsync_calls:
            cmd = shlex.split(cmd)

            for rsync_attempt in range(max_rsync_attempts):
                rc = sp.Popen(cmd).wait()
                if rc == 0:
                    break
                else:
                    print('rsync failed, reattempting')
            assert rc == 0

        # TODO: Temporary; this should be integrated with the rsync call
        if res_tar_path and os.path.exists(res_tar_path):
            os.remove(res_tar_path)


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
        next_run = self.counter + 1
        cmd = 'payu run -i {} -n {}'.format(next_run, self.n_runs)
        cmd = shlex.split(cmd)
        sp.call(cmd)


    #---
    def sweep(self, hard_sweep=False):
        # TODO: Fix the IO race conditions!

        if hard_sweep:
            if os.path.isdir(self.archive_path):
                print('Removing archive path {}'.format(self.archive_path))
                #sh.rmtree(self.archive_path)
                cmd = 'rm -rf {}'.format(self.archive_path)
                cmd = shlex.split(cmd)
                rc = sp.call(cmd)
                assert rc == 0

            if os.path.islink(self.archive_sym_path):
                print('Removing symlink {}'.format(self.archive_sym_path))
                os.remove(self.archive_sym_path)

        if os.path.isdir(self.work_path):
            print('Removing work path {}'.format(self.work_path))
            #sh.rmtree(self.work_path)
            cmd = 'rm -rf {}'.format(self.work_path)
            cmd = shlex.split(cmd)
            rc = sp.call(cmd)
            assert rc == 0

        if os.path.islink(self.work_sym_path):
            print('Removing symlink {}'.format(self.work_sym_path))
            os.remove(self.work_sym_path)

        # TODO: model outstreams and pbs logs need to be handled separately
        logs = [f for f in os.listdir(os.curdir) if os.path.isfile(f) and
                (f == self.stdout_fname or
                 f == self.stderr_fname or
                 f.startswith(self.job_name + '.o') or
                 f.startswith(self.job_name + '.e') or
                 f.startswith(self.job_name + '_c.o') or
                 f.startswith(self.job_name + '_c.e')
                 )
                ]

        pbs_log_path = os.path.join(os.curdir, 'pbs_logs')
        mkdir_p(pbs_log_path)

        for f in logs:
            print('Moving log {}'.format(f))
            os.rename(f, os.path.join(pbs_log_path, f))
