"""payu.experiment
   ===============

   Interface to an individual experiment managed by payu

   :copyright: Copyright 2011 Marshall Ward, see AUTHORS for details.
   :license: Apache License, Version 2.0, see LICENSE for details.
"""

# Python3 preparation
from __future__ import print_function

# Standard Library
import errno
import getpass
import os
import resource
import sys
import shlex
import shutil
import subprocess as sp

# Local
from payu import envmod
from payu.fsops import mkdir_p, make_symlink, read_config
from payu.models import index as model_index
import payu.profilers
from payu.runlog import Runlog

# Environment module support on vayu
module_path = '/projects/v45/modules'
core_modules = ['python', 'payu']

# Default payu parameters
default_archive_url = 'dc.nci.org.au'
default_restart_freq = 5
default_restart_history = 5


class Experiment(object):

    def __init__(self, lab):
        self.lab = lab

        # TODO: replace with dict, check versions via key-value pairs
        self.modules = set()

        # TODO: __init__ should not be a config dumping ground!
        self.config = read_config()

        # Model run time
        self.runtime = None
        if ('calendar' in self.config and
                'runtime' in self.config['calendar']):
            self.runtime = self.config['calendar']['runtime']

        # Stacksize
        # NOTE: Possible PBS issue in setting non-unlimited stacksizes
        stacksize = self.config.get('stacksize', 'unlimited')
        self.set_stacksize(stacksize)

        # Initialize the submodels
        self.init_models()

        # TODO: Move to run/collate/sweep?
        self.set_expt_pathnames()
        self.set_counters()

        for model in self.models:
            model.set_input_paths()

        self.set_output_paths()

        # Miscellaneous configurations
        # TODO: Move this stuff somewhere else
        self.userscripts = self.config.get('userscripts', {})

        self.profilers = []

        self.debug = self.config.get('debug', False)
        self.postscript = self.config.get('postscript')
        self.repeat_run = self.config.get('repeat', False)

        init_script = self.userscripts.get('init')
        if init_script:
            self.run_userscript(init_script)

        # Logging
        if self.config.get('runlog', False):
            self.runlog = Runlog(self)
        else:
            self.runlog = None

    def init_models(self):

        self.model_name = self.config.get('model')
        assert self.model_name

        model_fields = ['model', 'exe', 'input', 'ncpus', 'npernode', 'build']

        # TODO: Rename this to self.submodels
        self.models = []

        submodels = self.config.get('submodels', [])

        if not submodels:

            solo_model = self.config.get('model')
            if not solo_model:
                sys.exit('payu: error: Unknown model configuration.')

            submodel_config = {f: self.config[f] for f in model_fields
                               if f in self.config}
            submodel_config['name'] = solo_model

            submodels = [submodel_config]

        for m_config in submodels:
            ModelType = model_index[m_config['model']]
            self.models.append(ModelType(self, m_config['name'], m_config))

        # Load the top-level model
        if self.model_name:
            ModelType = model_index[self.model_name]
            model_config = {f: self.config[f] for f in model_fields
                            if f in self.config}
            self.model = ModelType(self, self.model_name, model_config)
        else:
            self.model = None

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
            except OSError as exc:
                if exc.errno == errno.ENOENT:
                    restart_dirs = None
                else:
                    raise

            # First test for restarts
            if restart_dirs:
                self.counter = 1 + max([int(d.lstrip('restart'))
                                        for d in restart_dirs
                                        if d.startswith('restart')])
            else:
                # Repeat runs do not generate restart files, so check outputs
                try:
                    output_dirs = [d for d in os.listdir(self.archive_path)
                                   if d.startswith('output')]
                except OSError as exc:
                    if exc.errno == errno.ENOENT:
                        output_dirs = None
                    else:
                        raise

                # First test for restarts
                if output_dirs:
                    self.counter = 1 + max([int(d.lstrip('output'))
                                            for d in output_dirs
                                            if d.startswith('output')])
                else:
                    self.counter = 0

    def set_stacksize(self, stacksize):

        if stacksize == 'unlimited':
            stacksize = resource.RLIM_INFINITY
        else:
            assert type(stacksize) is int

        resource.setrlimit(resource.RLIMIT_STACK,
                           (stacksize, resource.RLIM_INFINITY))

    def load_modules(self):

        # Scheduler
        sched_modname = self.config.get('scheduler', 'pbs')
        self.modules.add(sched_modname)

        # MPI library
        mpi_config = self.config.get('mpi', {})
        mpi_modname = mpi_config.get('module', 'openmpi')
        self.modules.add(mpi_modname)

        # Unload non-essential modules
        loaded_mods = os.environ.get('LOADEDMODULES', '').split(':')

        for mod in loaded_mods:
            mod_base = mod.split('/')[0]
            if mod_base not in core_modules:
                envmod.module('unload', mod)

        # Now load model-dependent modules
        for mod in self.modules:
            envmod.module('load', mod)

        # User-defined modules
        user_modules = self.config.get('modules', [])
        for mod in user_modules:
            envmod.module('load', mod)

        envmod.module('list')

        # TODO: Consolidate this profiling stuff
        c_ipm = self.config.get('ipm', False)
        if c_ipm:
            if isinstance(c_ipm, str):
                ipm_mod = os.path.join('ipm', c_ipm)
            else:
                ipm_mod = 'ipm/2.0.2'

            envmod.module('load', ipm_mod)
            os.environ['IPM_LOGDIR'] = self.work_path

        if self.config.get('mpiP', False):
            envmod.module('load', 'mpiP')

        if self.config.get('hpctoolkit', False):
            envmod.module('load', 'hpctoolkit')

        if self.config.get('scalasca', False):
            envmod.module('use', '/home/900/mpc900/my_modules')
            envmod.module('load', 'scalasca')

        if self.config.get('scorep', False):
            envmod.module('load', 'scorep')

        if self.config.get('openspeedshop', False):
            envmod.module('load', 'openspeedshop')

        if self.debug:
            envmod.module('load', 'totalview')

    def set_expt_pathnames(self):

        # Local "control" path
        self.control_path = self.config.get('control', os.getcwd())

        # Experiment name
        expt_name = self.config.get('experiment',
                                    os.path.basename(self.control_path))

        # Experiment subdirectories
        self.archive_path = os.path.join(self.lab.archive_path, expt_name)
        self.work_path = os.path.join(self.lab.work_path, expt_name)

        # Symbolic link paths to output
        self.work_sym_path = os.path.join(self.control_path, 'work')
        self.archive_sym_path = os.path.join(self.control_path, 'archive')

        for model in self.models:
            model.set_model_pathnames()

        # Stream output filenames
        # TODO: per-model output streams?
        self.stdout_fname = self.lab.model_type + '.out'
        self.stderr_fname = self.lab.model_type + '.err'

    def set_output_paths(self):

        # Local archive paths

        # Check to see if we've provided a hard coded path -- valid for collate
        dir_path = os.environ.get('PAYU_DIR_PATH')
        if dir_path is not None:
            self.output_path = os.path.normpath(dir_path)
        else:
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

    def build_model(self):

        self.load_modules()

        for model in self.models:
            model.get_codebase()

        for model in self.models:
            model.build_model()

    def setup(self, do_stripe=False):

        # Confirm that no output path already exists
        if os.path.exists(self.output_path):
            sys.exit('payu: error: Output path already exists.')

        mkdir_p(self.work_path)

        # Archive the payu config
        # TODO: This just copies the existing config.yaml file, but we should
        #       reconstruct a new file including default values
        config_src = os.path.join(self.control_path, 'config.yaml')
        config_dst = os.path.join(self.work_path)
        shutil.copy(config_src, config_dst)

        # Stripe directory in Lustre
        # TODO: Make this more configurable
        if do_stripe:
            cmd = 'lfs setstripe -c 8 -s 8m {}'.format(self.work_path)
            sp.check_call(shlex.split(cmd))

        make_symlink(self.work_path, self.work_sym_path)

        for model in self.models:
            model.setup()

        # Call the macro-model setup
        if len(self.models) > 1:
            self.model.setup()

        setup_script = self.userscripts.get('setup')
        if setup_script:
            self.run_userscript(setup_script)

        # Profiler setup
        expt_profs = self.config.get('profilers', [])
        if not isinstance(expt_profs, list):
            expt_profs = [expt_profs]

        for prof_name in expt_profs:
            ProfType = payu.profilers.index[prof_name]
            prof = ProfType(self)
            self.profilers.append(prof)

            # Testing
            prof.setup()

    def run(self, *user_flags):

        self.load_modules()

        f_out = open(self.stdout_fname, 'w')
        f_err = open(self.stderr_fname, 'w')

        # Set MPI environment variables
        env = self.config.get('env')

        # Explicitly check for `None`, in case of an empty `env:` entry
        if env is None:
            env = {}

        for var in env:

            if env[var] is None:
                env_value = ''
            else:
                env_value = str(env[var])

            os.environ[var] = env_value

        mpi_config = self.config.get('mpi', {})
        mpi_runcmd = mpi_config.get('runcmd', 'mpirun')

        if self.config.get('scalasca', False):
            mpi_runcmd = ' '.join(['scalasca -analyze', mpi_runcmd])

        mpi_flags = self.config.get('mpirun')
        # Correct an empty mpirun entry
        if mpi_flags is None:
            mpi_flags = []

        if type(mpi_flags) != list:
            mpi_flags = [mpi_flags]

        # TODO: More uniform support needed here
        if self.config.get('scalasca', False):
            mpi_flags = ['\"{}\"'.format(f) for f in mpi_flags]

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

            mpi_config = self.config.get('mpi', {})
            mpi_module = mpi_config.get('module', None)

            # Update MPI library module (if not explicitly set)
            # TODO: Check for MPI library mismatch across multiple binaries
            if mpi_module is None:
                mpi_module = envmod.lib_update(model.exec_path, 'libmpi.so')

            model_prog = []

            # Our MPICH wrapper does not support a working directory flag
            if not mpi_module.startswith('mvapich'):
                model_prog.append('-wdir {}'.format(model.work_path))

            # Append any model-specific MPI flags
            model_flags = model.config.get('mpiflags', [])
            if not isinstance(model_flags, list):
                model_prog.append(model_flags)
            else:
                model_prog.extend(model_flags)

            model_ncpus = model.config.get('ncpus')
            if model_ncpus:
                model_prog.append('-np {}'.format(model_ncpus))

            model_npernode = model.config.get('npernode')
            # TODO: New Open MPI format?
            if model_npernode:
                if model_npernode % 2 == 0:
                    npernode_flag = '-npersocket {}'.format(model_npernode / 2)
                else:
                    npernode_flag = '-npernode {}'.format(model_npernode)

                if self.config.get('scalasca', False):
                    npernode_flag = '\"{}\"'.format(npernode_flag)
                model_prog.append(npernode_flag)

            if self.config.get('hpctoolkit', False):
                os.environ['HPCRUN_EVENT_LIST'] = 'WALLCLOCK@5000'
                model_prog.append('hpcrun')

            for prof in self.profilers:
                if prof.wrapper:
                    model_prog.append(prof.wrapper)

            model_prog.append(model.exec_prefix)
            model_prog.append(model.exec_path)

            mpi_progs.append(' '.join(model_prog))

        cmd = '{} {} {}'.format(mpi_runcmd,
                                ' '.join(mpi_flags),
                                ' : '.join(mpi_progs))

        oss = self.config.get('openspeedshop')
        if oss:
            oss_runcmd = oss.get('runcmd')
            if not oss_runcmd:
                print('payu: error: OpenSpeedShop requires an executable.')
                sys.exit(1)

            oss_hwc = oss.get('hwc')
            if oss_runcmd.startswith('osshwc') and not oss_hwc:
                print('payu: error: This OSS command requires hardware '
                      'counters.')
                sys.exit(1)

            cmd = '{} "{}" {}'.format(oss_runcmd, cmd, oss_hwc)

        print(cmd)

        # Our MVAPICH wrapper does not support working directories
        if mpi_module.startswith('mvapich'):
            curdir = os.getcwd()
            os.chdir(self.work_path)
        else:
            curdir = None

        if env:
            # TODO: Replace with mpirun -x flag inputs
            proc = sp.Popen(shlex.split(cmd), stdout=f_out, stderr=f_err,
                            env=os.environ.copy())
            proc.wait()
            rc = proc.returncode
        else:
            rc = sp.call(shlex.split(cmd), stdout=f_out, stderr=f_err)

        # Return to control directory
        if curdir:
            os.chdir(curdir)

        if self.runlog:
            self.runlog.commit()

        f_out.close()
        f_err.close()

        # Remove any empty output files (e.g. logs)
        for fname in os.listdir(self.work_path):
            fpath = os.path.join(self.work_path, fname)
            if os.path.getsize(fpath) == 0:
                os.remove(fpath)

        # Clean up any profiling output
        # TODO: Move after `rc` code check?
        for prof in self.profilers:
            prof.postprocess()

        # TODO: Need a model-specific cleanup method call here
        if rc != 0:
            sys.exit('payu: Model exited with error code {}; aborting.'
                     ''.format(rc))

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
            f_path = os.path.join(self.control_path, f)
            if os.path.getsize(f_path) == 0:
                os.remove(f_path)
            else:
                shutil.move(f_path, self.work_path)

        run_script = self.userscripts.get('run')
        if run_script:
            self.run_userscript(run_script)

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
            sys.exit('payu: error: Output path already exists.')

        cmd = 'mv {} {}'.format(self.work_path, self.output_path)
        sp.check_call(shlex.split(cmd))

        # Remove old restart files
        # TODO: Move to subroutine
        restart_freq = self.config.get('restart_freq', default_restart_freq)
        restart_history = self.config.get('restart_history',
                                          default_restart_history)

        # Remove any outdated restart files
        prior_restart_dirs = [d for d in os.listdir(self.archive_path)
                              if d.startswith('restart')]

        for res_dir in prior_restart_dirs:

            res_idx = int(res_dir.lstrip('restart'))
            if (self.repeat_run or
                    (not res_idx % restart_freq == 0 and
                     res_idx <= (self.counter - restart_history))):

                res_path = os.path.join(self.archive_path, res_dir)

                # Only delete real directories; ignore symbolic restart links
                if os.path.isdir(res_path):
                    shutil.rmtree(res_path)

        if self.config.get('collate', True):
            cmd = 'payu collate -i {}'.format(self.counter)
            sp.check_call(shlex.split(cmd))

        if self.config.get('hpctoolkit', False):
            cmd = 'payu profile -i {}'.format(self.counter)
            sp.check_call(shlex.split(cmd))

        archive_script = self.userscripts.get('archive')
        if archive_script:
            self.run_userscript(archive_script)

    def collate(self):

        for model in self.models:
            model.collate()

    def profile(self):
        for model in self.models:
            model.profile()

    def postprocess(self):
        """Submit a postprocessing script after collation"""
        assert self.postscript

        cmd = 'qsub {}'.format(self.postscript)

        cmd = shlex.split(cmd)
        rc = sp.call(cmd)
        assert rc == 0, 'Postprocessing script submission failed.'

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
        rsync_cmd = ('rsync -a --safe-links -e "ssh -i {}" '
                     ''.format(ssh_key_path))

        if rsync_protocol:
            rsync_cmd += '--protocol={} '.format(rsync_protocol)

        run_cmd = rsync_cmd + '{src} {dst}'.format(src=self.output_path,
                                                   dst=remote_url)
        rsync_calls = [run_cmd]

        if (self.counter % 5) == 0 and os.path.isdir(self.restart_path):
            # Tar restart files before rsyncing
            restart_tar_path = self.restart_path + '.tar.gz'

            cmd = ('tar -C {} -czf {} {}'
                   ''.format(self.archive_path, restart_tar_path,
                             os.path.basename(self.restart_path)))
            sp.check_call(shlex.split(cmd))

            restart_cmd = ('{} {} {}'
                           ''.format(rsync_cmd, restart_tar_path, remote_url))
            rsync_calls.append(restart_cmd)
        else:
            res_tar_path = None

        for input_path in self.input_paths:
            # Using explicit path separators to rename the input directory
            input_cmd = rsync_cmd + '{} {}'.format(
                input_path + os.path.sep,
                os.path.join(remote_url, 'input') + os.path.sep)
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

    def resubmit(self):
        next_run = self.counter + 1
        cmd = 'payu run -i {} -n {}'.format(next_run, self.n_runs)
        cmd = shlex.split(cmd)
        sp.call(cmd)

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

                _, f_ext = os.path.splitext(script_cmd)
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

    def sweep(self, hard_sweep=False):
        # TODO: Fix the IO race conditions!

        if hard_sweep:
            if os.path.isdir(self.archive_path):
                print('Removing archive path {}'.format(self.archive_path))
                cmd = 'rm -rf {}'.format(self.archive_path)
                cmd = shlex.split(cmd)
                rc = sp.call(cmd)
                assert rc == 0

            if os.path.islink(self.archive_sym_path):
                print('Removing symlink {}'.format(self.archive_sym_path))
                os.remove(self.archive_sym_path)

        if os.path.isdir(self.work_path):
            print('Removing work path {}'.format(self.work_path))
            cmd = 'rm -rf {}'.format(self.work_path)
            cmd = shlex.split(cmd)
            rc = sp.call(cmd)
            assert rc == 0

        if os.path.islink(self.work_sym_path):
            print('Removing symlink {}'.format(self.work_sym_path))
            os.remove(self.work_sym_path)

        # TODO: model outstreams and pbs logs need to be handled separately
        default_job_name = os.path.basename(os.getcwd())
        short_job_name = self.config.get('jobname', default_job_name)[:15]

        logs = [
            f for f in os.listdir(os.curdir) if os.path.isfile(f) and (
                f == self.stdout_fname or
                f == self.stderr_fname or
                f.startswith(short_job_name + '.o') or
                f.startswith(short_job_name + '.e') or
                f.startswith(short_job_name[:13] + '_c.o') or
                f.startswith(short_job_name[:13] + '_c.e') or
                f.startswith(short_job_name[:13] + '_p.o') or
                f.startswith(short_job_name[:13] + '_p.e')
            )
        ]

        pbs_log_path = os.path.join(os.curdir, 'pbs_logs')
        mkdir_p(pbs_log_path)

        for f in logs:
            print('Moving log {}'.format(f))
            os.rename(f, os.path.join(pbs_log_path, f))
