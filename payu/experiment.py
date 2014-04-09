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

        # TODO: replace with dict, check versions via key-value pairs
        self.modules = set()

        # TODO: __init__ should not be a config dumping ground!
        self.read_config()

        # Set stacksize
        # NOTE: Possible PBS issue in setting non-unlimited stacksizes
        stacksize = self.config.get('stacksize')
        if stacksize:
            self.set_stacksize(stacksize)

        # Initialize the submodels
        self.init_models()

        # TODO: Move to run/collate/sweep?
        self.set_pbs_config()
        self.set_lab_pathnames()
        self.set_expt_pathnames()
        self.set_counters()

        for model in self.models:
            model.set_input_paths()

        self.set_output_paths()

        # Miscellaneous configurations
        # TODO: Move this stuff somewhere else
        self.userscripts = self.config.get('userscripts', {})

        self.debug = self.config.get('debug', False)
        self.postscript = self.config.get('postscript')
        self.repeat_run = self.config.get('repeat', False)

        init_script = self.userscripts.get('init')
        if init_script:
            self.run_userscript(init_script)


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

        self.model_name = self.config.get('model')
        assert self.model_name

        model_fields = ['model', 'exe', 'input', 'ncpus', 'npernode']

        # TODO: Rename this to self.submodels
        self.models = []

        submodels = self.config.get('submodels', {})

        # --- TODO: Delete this block
        if not submodels:

            solo_model = self.config.get('model')
            if not solo_model:
                sys.exit('payu: error: Unknown model configuration.')

            submodels[solo_model] = {f: self.config[f] for f in model_fields
                                     if f in self.config}
        # --- TODO: end delete

        for m_name, m_config in submodels.iteritems():

            ModelType = model_index[m_config['model']]
            self.models.append(ModelType(self, m_name, m_config))

        # Load the top-level model
        if self.model_name:
            ModelType = model_index[self.model_name]
            model_config = {f: self.config[f] for f in model_fields
                               if f in self.config}
            self.model = ModelType(self, self.model_name, model_config)
        else:
            self.model = None


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

        for model in self.models:
            self.modules.update(model.modules)

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

        if self.debug:
            module('load', 'totalview')


    #---
    def set_pbs_config(self):

        default_n_cpus = os.environ.get('PBS_NCPUS', 1)
        self.n_cpus = self.config.get('ncpus', default_n_cpus)

        self.n_cpus_per_node = self.config.get('npernode')

        default_job_name = os.path.basename(os.getcwd())
        self.job_name = self.config.get('jobname', default_job_name)


    #---
    def set_lab_pathnames(self):

        # Local "control" path
        self.control_path = self.config.get('control', os.getcwd())

        # Top-level "short term storage" path
        default_short_path = os.path.join('/short', os.environ.get('PROJECT'))
        self.short_path = self.config.get('shortpath', default_short_path)

        default_user = pwd.getpwuid(os.getuid()).pw_name

        # Laboratory path

        # Determine laboratory name
        lab_name = self.config.get('laboratory', self.model_name)
        self.lab_name = lab_name

        # Construct the laboratory absolute path if necessary
        if os.path.isabs(lab_name):
                self.lab_path = lab_name
        else:
            # Check under the default root path
            user_name = self.config.get('user', default_user)
            self.lab_path = os.path.join(self.short_path, user_name, lab_name)

        # Validate the path
        if not os.path.isdir(self.lab_path):
            sys.exit('payu: error: Laboratory path {} not found.'
                     ''.format(self.lab_path))

        # Executable "binary" path
        self.bin_path = os.path.join(self.lab_path, 'bin')

        # Laboratory input path
        self.input_basepath = os.path.join(self.lab_path, 'input')

        # Source code base path
        self.codebase_path = os.path.join(self.lab_path, 'codebase')


    #---
    def set_expt_pathnames(self):

        # Experiment name
        assert self.control_path
        default_experiment = os.path.basename(self.control_path)
        self.experiment = self.config.get('experiment', default_experiment)

        # Experiment subdirectories
        assert self.lab_path
        self.archive_path = os.path.join(self.lab_path, 'archive',
                                         self.experiment)
        self.work_path = os.path.join(self.lab_path, 'work', self.experiment)

        # Symbolic link paths to output
        self.work_sym_path = os.path.join(self.control_path, 'work')
        self.archive_sym_path = os.path.join(self.control_path, 'archive')

        for model in self.models:
            model.set_model_pathnames()

        # Stream output filenames
        # TODO: per-model output streams?
        self.stdout_fname = self.lab_name + '.out'
        self.stderr_fname = self.lab_name + '.err'


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
        restart_dir = 'restart{:03}'.format(self.counter)
        self.restart_path = os.path.join(self.archive_path, restart_dir)

        prior_restart_dir = 'restart{:03}'.format(self.counter - 1)
        prior_restart_path = os.path.join(self.archive_path, prior_restart_dir)
        if os.path.exists(prior_restart_path):
            self.prior_restart_path = prior_restart_path
        else:
            self.prior_restart_path = None
            if self.counter > 0:
                # TODO: This warning should be replaced with an abort in setup
                print('payu: warning: No restart files found.')

        for model in self.models:
            model.set_model_output_paths()


    #---
    def init(self):
        # TODO: The name `init` is too generic

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
            sys.exit('payu: error: Archived path already exists.')

        mkdir_p(self.work_path)

        # Stripe directory in Lustre
        # TODO: Make this more configurable
        if do_stripe:
            cmd = 'lfs setstripe -c 8 -s 8m {}'.format(self.work_path)
            cmd = shlex.split(cmd)
            rc = sp.call(cmd)
            assert rc == 0

        make_symlink(self.work_path, self.work_sym_path)

        for model in self.models:
            model.setup()

        # Call the macro-model setup
        if len(self.models) > 1:
            self.model.setup()

        setup_script = self.userscripts.get('setup')
        if setup_script:
            self.run_userscript(setup_script)


    #---
    def run(self, *user_flags):

        self.load_modules()

        f_out = open(self.stdout_fname, 'w')
        f_err = open(self.stderr_fname, 'w')

        mpirun_cmd = 'mpirun'

        mpi_flags = self.config.get('mpirun', [])
        if type(mpi_flags) != list:
            mpi_flags = [mpi_flags]

        # XXX: I think this may be broken
        if user_flags:
            mpi_flags.extend(list(user_flags))

        if self.debug:
            mpi_flags.append('--debug')

        mpi_progs = []
        for model in self.models:

            # Skip models without executables (e.g. couplers)
            if not model.exec_path:
                continue

            model_prog = []

            model_prog.append('-wdir {}'.format(model.work_path))

            model_ncpus = model.config.get('ncpus')
            if model_ncpus:
                model_prog.append('-np {}'.format(model_ncpus))

            model_npernode = model.config.get('npernode')
            if model_npernode:
                model_prog.append('-npernode {}'.format(model_npernode))

            model_prog.append(model.exec_path)

            mpi_progs.append(' '.join(model_prog))

        cmd = '{mpirun} {flags} {progs}'.format(
                    mpirun = mpirun_cmd,
                    flags = ' '.join(mpi_flags),
                    progs = ' : '.join(mpi_progs))

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
            sys.exit('payu: error {}; aborting.'.format(rc))

        # Decrement run counter on successful run
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

        run_script = self.userscripts.get('run')
        if run_script:
            self.run_userscript(run_script)


    #---
    def archive(self):

        mkdir_p(self.archive_path)
        make_symlink(self.archive_path, self.archive_sym_path)

        # Remove work symlink
        if os.path.islink(self.work_sym_path):
            os.remove(self.work_sym_path)

        mkdir_p(self.restart_path)

        for model in self.models:
            model.archive()

        # Postprocess the model suite
        if len(self.models) > 1:
            self.model.archive()

        # Double-check that the run path does not exist
        if os.path.exists(self.output_path):
            sys.exit('payu: error: Archived path already exists.')

        cmd = 'mv {} {}'.format(self.work_path, self.output_path)
        try:
            sp.check_call(shlex.split(cmd))
        except sp.CalledProcessError as exc:
            sys.exit('payu: error: {} (error {})'
                     ''.format(cmd, exc.returncode))

        # Remove old restart files
        # TODO: Move to subroutine
        restart_freq = self.config.get("restart_freq", default_restart_freq)

        if (self.counter >= restart_freq and self.counter % restart_freq == 0):
            i_s = self.counter - restart_freq
            i_e = self.counter - 1
            prior_restart_dirs = ('restart{:03}'.format(i)
                              for i in range(i_s, i_e))

            for restart_dirname in prior_restart_dirs:
                restart_path = os.path.join(self.archive_path, restart_dirname)
                cmd = 'rm -rf {}'.format(restart_path)
                cmd = shlex.split(cmd)
                try:
                    sp.check_call(cmd)
                except sp.CalledProcessError:
                    print('payu: warning: Could not delete directories {}'
                          ''.format(' '.join(prior_restart_dirs)))

        collate = self.config.get('collate', True)
        if collate:
            cmd = 'payu collate -i {}'.format(self.counter)

            cmd = shlex.split(cmd)
            rc = sp.Popen(cmd).wait()
            assert rc == 0

        archive_script = self.userscripts.get('archive')
        if archive_script:
            self.run_userscript(archive_script)


    #---
    def collate(self):

        for model in self.models:
            model.collate()


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

        if (self.counter % 5) == 0 and os.path.isdir(self.restart_path):
            # Tar restart files before rsyncing
            restart_tar_path = self.restart_path + '.tar.gz'

            cmd = 'tar -C {path} -czf {fpath} {res}'.format(
                        path=self.archive_path,
                        fpath=restart_tar_path,
                        res=os.path.basename(self.restart_path)
                        ).split()
            rc = sp.Popen(cmd).wait()

            restart_cmd = ('{} {} {}'
                           ''.format(rsync_cmd, restart_tar_path, remote_url))
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
    def resubmit(self):
        next_run = self.counter + 1
        cmd = 'payu run -i {} -n {}'.format(next_run, self.n_runs)
        cmd = shlex.split(cmd)
        sp.call(cmd)


    #---
    def run_userscript(self, script_cmd):

        # First try to interpret the argument as a full command:
        try:
            sp.check_call(shlex.split(script_cmd))
        except (OSError, sp.CalledProcessError) as exc:
            # Now try to run the script explicitly
            if type(exc) == OSError and exc.errno == errno.ENOENT:
                    cmd = os.path.join(self.control_path, script_cmd)
                    # Simplistic recursion check
                    assert os.path.isfile(cmd)
                    self.run_userscript(cmd)

            # If we get a "non-executable" error, then guess the type
            elif type(exc) == OSError and exc.errno == errno.EACCES:

                # TODO: Move outside
                ext_cmd = {'.py': 'python',
                           '.sh': '/bin/bash',
                           '.csh': '/bin/tcsh'}

                f_base, f_ext = os.path.splitext(script_cmd)
                shell_name = ext_cmd.get(f_ext)
                if shell_name:
                    print('payu: warning: Assuming that {} is a {} script '
                          'based on the filename extension.'
                          ''.format(os.path.basename(script_cmd),
                                    os.path.basename(shell_name)))
                    cmd = ' '.join([shell_name, script_cmd])
                    self.run_userscript(cmd)
                else:
                    # If we can't guess the shell, then abort
                    raise

            # If the script runs but the output is bad, then warn the user
            elif type(exc) == sp.CalledProcessError:
                print('payu: warning: user script \'{}\' failed (error {}).'
                      ''.format(script_cmd, exc.returncode))

            # If all else fails, raise an error
            else:
                raise


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
        short_job_name = self.job_name[:15]

        logs = [f for f in os.listdir(os.curdir) if os.path.isfile(f) and
                (f == self.stdout_fname or
                 f == self.stderr_fname or
                 f.startswith(short_job_name + '.o') or
                 f.startswith(short_job_name + '.e') or
                 f.startswith(short_job_name + '_c.o') or
                 f.startswith(short_job_name + '_c.e')
                 )
                ]

        pbs_log_path = os.path.join(os.curdir, 'pbs_logs')
        mkdir_p(pbs_log_path)

        for f in logs:
            print('Moving log {}'.format(f))
            os.rename(f, os.path.join(pbs_log_path, f))
