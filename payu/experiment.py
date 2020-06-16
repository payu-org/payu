"""payu.experiment ===============

   Interface to an individual experiment managed by payu

   :copyright: Copyright 2011 Marshall Ward, see AUTHORS for details.
   :license: Apache License, Version 2.0, see LICENSE for details.
"""

from __future__ import print_function

# Standard Library
import datetime
import errno
import getpass
import os
import resource
import sys
import shlex
import shutil
import subprocess as sp
import sysconfig

# Extensions
import yaml

# Local
from payu import envmod
from payu.fsops import mkdir_p, make_symlink, read_config, movetree
from payu.schedulers.pbs import get_job_info, pbs_env_init, get_job_id
from payu.models import index as model_index
import payu.profilers
from payu.runlog import Runlog
from payu.manifest import Manifest

# Environment module support on vayu
# TODO: To be removed
core_modules = ['python', 'payu']

# Default payu parameters
default_archive_url = 'dc.nci.org.au'
default_restart_freq = 5
default_restart_history = 5


class Experiment(object):

    def __init__(self, lab, reproduce=False, force=False):
        self.lab = lab

        if not force:
            # check environment for force flag under PBS
            self.force = os.environ.get('PAYU_FORCE', False)
        else:
            self.force = force

        self.start_time = datetime.datetime.now()

        # TODO: replace with dict, check versions via key-value pairs
        self.modules = set()

        # TODO: __init__ should not be a config dumping ground!
        self.config = read_config()

        # Payu experiment type
        self.debug = self.config.get('debug', False)
        self.postscript = self.config.get('postscript')
        self.repeat_run = self.config.get('repeat', False)

        # Configuration
        self.expand_shell_vars = True   # TODO: configurable

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

        if not reproduce:
            # check environment for reproduce flag under PBS
            reproduce = os.environ.get('PAYU_REPRODUCE', False)

        # Initialize manifest
        self.manifest = Manifest(self.config.get('manifest', {}),
                                 reproduce=reproduce)

        # Miscellaneous configurations
        # TODO: Move this stuff somewhere else
        self.userscripts = self.config.get('userscripts', {})

        self.profilers = []

        init_script = self.userscripts.get('init')
        if init_script:
            self.run_userscript(init_script)

        self.runlog = Runlog(self)

        # XXX: Temporary spot for the payu path
        #      This is horrible; payu/cli.py does this much more safely!
        #      But also does not even store it in os.environ!
        default_payu_bin = os.path.dirname(sys.argv[0])
        payu_bin = os.environ.get('PAYU_PATH', default_payu_bin)

        self.payu_path = os.path.join(payu_bin, 'payu')

        self.run_id = None

    def init_models(self):

        self.model_name = self.config.get('model')
        assert self.model_name

        model_fields = ['model', 'exe', 'input', 'ncpus', 'npernode', 'build',
                        'mpthreads', 'exe_prefix']

        # XXX: Temporarily adding this to model config...
        model_fields += ['mask']

        # TODO: Rename this to self.submodels
        self.models = []

        submodels = self.config.get('submodels', [])

        solo_model = self.config.get('model')
        if not solo_model:
            sys.exit('payu: error: Unknown model configuration.')

        submodel_config = dict((f, self.config[f]) for f in model_fields
                               if f in self.config)
        submodel_config['name'] = solo_model

        submodels.append(submodel_config)

        for m_config in submodels:
            ModelType = model_index[m_config['model']]
            self.models.append(ModelType(self, m_config['name'], m_config))

        # Load the top-level model
        if self.model_name:
            ModelType = model_index[self.model_name]
            model_config = dict((f, self.config[f]) for f in model_fields
                                if f in self.config)
            self.model = ModelType(self, self.model_name, model_config)
            self.model.top_level_model = True
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
            except EnvironmentError as exc:
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
                # repeat runs do not generate restart files, so check outputs
                try:
                    output_dirs = [d for d in os.listdir(self.archive_path)
                                   if d.startswith('output')]
                except EnvironmentError as exc:
                    if exc.errno == errno.ENOENT:
                        output_dirs = None
                    else:
                        raise

                # First test for restarts
                # Now look for output directories
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
        # NOTE: This function is increasingly irrelevant, and may be removable.

        # Scheduler
        sched_modname = self.config.get('scheduler', 'pbs')
        self.modules.add(sched_modname)

        # MPI library
        mpi_config = self.config.get('mpi', {})

        # Assign MPI module paths
        mpi_modpath = mpi_config.get('modulepath', None)
        if mpi_modpath:
            envmod.module('use', mpi_modpath)

        mpi_modname = mpi_config.get('module', 'openmpi')
        self.modules.add(mpi_modname)

        # Unload non-essential modules
        loaded_mods = os.environ.get('LOADEDMODULES', '').split(':')

        for mod in loaded_mods:
            if len(mod) > 0:
                print('mod '+mod)
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

        for prof in self.profilers:
            prof.load_modules()

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

        if self.debug:
            envmod.module('load', 'totalview')

    def set_expt_pathnames(self):

        # Local "control" path
        self.control_path = self.config.get('control', os.getcwd())

        # Experiment name
        self.name = self.config.get('experiment',
                                    os.path.basename(self.control_path))

        # Experiment subdirectories
        self.archive_path = os.path.join(self.lab.archive_path, self.name)
        self.work_path = os.path.join(self.lab.work_path, self.name)

        # Symbolic link paths to output
        self.work_sym_path = os.path.join(self.control_path, 'work')
        self.archive_sym_path = os.path.join(self.control_path, 'archive')

        for model in self.models:
            model.set_model_pathnames()
            model.set_local_pathnames()

        # Stream output filenames
        # TODO: per-model output streams?
        self.stdout_fname = self.lab.model_type + '.out'
        self.stderr_fname = self.lab.model_type + '.err'

        self.job_fname = 'job.yaml'
        self.env_fname = 'env.yaml'

        self.output_fnames = (self.stderr_fname,
                              self.stdout_fname,
                              self.job_fname,
                              self.env_fname)

    def set_output_paths(self):

        # Local archive paths

        # Check to see if we've provided a hard coded path -- valid for collate
        dir_path = os.environ.get('PAYU_DIR_PATH')
        if dir_path is not None:
            self.output_path = os.path.normpath(dir_path)
        else:
            output_dir = 'output{0:03}'.format(self.counter)
            self.output_path = os.path.join(self.archive_path, output_dir)

        # TODO: check case counter == 0
        prior_output_dir = 'output{0:03}'.format(self.counter - 1)
        prior_output_path = os.path.join(self.archive_path, prior_output_dir)
        if os.path.exists(prior_output_path):
            self.prior_output_path = prior_output_path
        else:
            self.prior_output_path = None

        # Local restart paths
        restart_dir = 'restart{0:03}'.format(self.counter)
        self.restart_path = os.path.join(self.archive_path, restart_dir)

        # Prior restart path

        # Check if a user restart directory is avaiable
        user_restart_dir = self.config.get('restart')
        if (self.counter == 0 or self.repeat_run) and user_restart_dir:
            # TODO: Some user friendliness needed...
            assert(os.path.isdir(user_restart_dir))
            self.prior_restart_path = user_restart_dir
        else:
            prior_restart_dir = 'restart{0:03}'.format(self.counter - 1)
            prior_restart_path = os.path.join(self.archive_path,
                                              prior_restart_dir)
            if os.path.exists(prior_restart_path) and not self.repeat_run:
                self.prior_restart_path = prior_restart_path
            else:
                self.prior_restart_path = None
                if self.counter > 0 and not self.repeat_run:
                    # TODO: This warning should be replaced with an abort in
                    #       setup
                    print('payu: warning: No restart files found.')

        for model in self.models:
            model.set_model_output_paths()

    def build_model(self):

        self.load_modules()

        for model in self.models:
            model.get_codebase()

        for model in self.models:
            model.build_model()

    def setup(self, force_archive=False):

        # Confirm that no output path already exists
        if os.path.exists(self.output_path):
            sys.exit('payu: error: Output path already exists: '
                     '{path}.'.format(path=self.output_path))

        # Confirm that no work path already exists
        if os.path.exists(self.work_path):
            if self.force:
                print('payu: work path already exists.\n'
                      '      Sweeping as --force option is True.')
                self.sweep()
            else:
                sys.exit('payu: error: work path already exists: {path}.\n'
                         '             payu sweep and then payu run'
                         .format(path=self.work_path))

        mkdir_p(self.work_path)

        if force_archive:
            mkdir_p(self.archive_path)
            make_symlink(self.archive_path, self.archive_sym_path)

        # Archive the payu config
        # TODO: This just copies the existing config.yaml file, but we should
        #       reconstruct a new file including default values
        config_src = os.path.join(self.control_path, 'config.yaml')
        config_dst = os.path.join(self.work_path)
        shutil.copy(config_src, config_dst)

        # Stripe directory in Lustre
        # TODO: Make this more configurable
        do_stripe = self.config.get('stripedio', False)
        if do_stripe:
            cmd = 'lfs setstripe -c 8 -s 8m {0}'.format(self.work_path)
            sp.check_call(shlex.split(cmd))

        make_symlink(self.work_path, self.work_sym_path)

        # Set up all file manifests
        self.manifest.setup()

        for model in self.models:
            model.setup()

        # Call the macro-model setup
        if len(self.models) > 1:
            self.model.setup()

        self.manifest.check_manifests()

        # Copy manifests to work directory so they archived on completion
        manifest_path = os.path.join(self.work_path, 'manifests')
        self.manifest.copy_manifests(manifest_path)

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

        # XXX: This was previously done in reversion
        envmod.setup()

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

        # MPI runtime flags
        mpi_flags = mpi_config.get('flags', [])
        if not mpi_flags:
            mpi_flags = self.config.get('mpirun', [])
            # TODO: Legacy config removal warning

        if type(mpi_flags) != list:
            mpi_flags = [mpi_flags]

        # TODO: More uniform support needed here
        if self.config.get('scalasca', False):
            mpi_flags = ['\"{0}\"'.format(f) for f in mpi_flags]

        # XXX: I think this may be broken
        if user_flags:
            mpi_flags.extend(list(user_flags))

        if self.debug:
            mpi_flags.append('--debug')

        mpi_progs = []
        for model in self.models:

            # Skip models without executables (e.g. couplers)
            if not model.exec_path_local:
                continue

            mpi_config = self.config.get('mpi', {})
            mpi_module = mpi_config.get('module', None)

            # Update MPI library module (if not explicitly set)
            # TODO: Check for MPI library mismatch across multiple binaries
            if mpi_module is None:
                mpi_module = envmod.lib_update(
                    model.exec_path_local,
                    'libmpi.so'
                )

            model_prog = []

            if mpi_module.startswith('openmpi'):
                # Our MPICH wrapper does not support a working directory flag
                model_prog.append('-wdir {0}'.format(model.work_path))
            elif self.config.get('scheduler') == 'slurm':
                # Slurm's launcher controls the working directory
                model_prog.append('--chdir {0}'.format(model.work_path))

            # Append any model-specific MPI flags
            model_flags = model.config.get('mpiflags', [])
            if not isinstance(model_flags, list):
                model_prog.append(model_flags)
            else:
                model_prog.extend(model_flags)

            model_ncpus = model.config.get('ncpus')
            if model_ncpus:
                if self.config.get('scheduler') == 'slurm':
                    model_prog.append('-n {0}'.format(model_ncpus))
                else:
                    # Default to preferred mpirun syntax
                    model_prog.append('-np {0}'.format(model_ncpus))

            model_npernode = model.config.get('npernode')
            # TODO: New Open MPI format?
            if model_npernode:
                if model_npernode % 2 == 0:
                    npernode_flag = ('-map-by ppr:{0}:socket'
                                     ''.format(model_npernode / 2))
                else:
                    npernode_flag = ('-map-by ppr:{0}:node'
                                     ''.format(model_npernode))

                if self.config.get('scalasca', False):
                    npernode_flag = '\"{0}\"'.format(npernode_flag)
                model_prog.append(npernode_flag)

            if self.config.get('hpctoolkit', False):
                os.environ['HPCRUN_EVENT_LIST'] = 'WALLCLOCK@5000'
                model_prog.append('hpcrun')

            for prof in self.profilers:
                if prof.runscript:
                    model_prog = model_prog.append(prof.runscript)

            model_prog.append(model.exec_prefix)

            # Use the full path to symlinked exec_name in work as some
            # older MPI libraries complained executable was not in PATH
            model_prog.append(os.path.join(model.work_path, model.exec_name))

            mpi_progs.append(' '.join(model_prog))

        cmd = '{runcmd} {flags} {exes}'.format(
            runcmd=mpi_runcmd,
            flags=' '.join(mpi_flags),
            exes=' : '.join(mpi_progs)
        )

        for prof in self.profilers:
            cmd = prof.wrapper(cmd)

        # Expand shell variables inside flags
        if self.expand_shell_vars:
            cmd = os.path.expandvars(cmd)

        # TODO: Consider making this default
        if self.config.get('coredump', False):
            enable_core_dump()

        # Our MVAPICH wrapper does not support working directories
        if mpi_module.startswith('mvapich'):
            curdir = os.getcwd()
            os.chdir(self.work_path)
        else:
            curdir = None

        # Dump out environment
        with open(self.env_fname, 'w') as file:
            file.write(yaml.dump(dict(os.environ), default_flow_style=False))

        self.runlog.create_manifest()
        if self.runlog.enabled:
            self.runlog.commit()

        # NOTE: This may not be necessary, since env seems to be getting
        # correctly updated.  Need to look into this.
        print(cmd)
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

        f_out.close()
        f_err.close()

        self.finish_time = datetime.datetime.now()

        info = get_job_info()

        if info is None:
            # Not being run under PBS, reverse engineer environment
            info = {
                'PAYU_PATH': os.path.dirname(self.payu_path)
            }

        # Add extra information to save to jobinfo
        info.update(
            {
                'PAYU_CONTROL_DIR': self.control_path,
                'PAYU_RUN_ID': self.run_id,
                'PAYU_CURRENT_RUN': self.counter,
                'PAYU_N_RUNS':  self.n_runs,
                'PAYU_JOB_STATUS': rc,
                'PAYU_START_TIME': self.start_time.isoformat(),
                'PAYU_FINISH_TIME': self.finish_time.isoformat(),
                'PAYU_WALLTIME': "{0} s".format(
                    (self.finish_time - self.start_time).total_seconds()
                ),
            }
        )

        # Dump job info
        with open(self.job_fname, 'w') as file:
            file.write(yaml.dump(info, default_flow_style=False))

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
        # NOTE: This does not appear to catch hanging jobs killed by PBS
        if rc != 0:
            # Backup logs for failed runs
            error_log_dir = os.path.join(self.archive_path, 'error_logs')
            mkdir_p(error_log_dir)

            # NOTE: This is PBS-specific
            job_id = get_job_id(short=False)

            if job_id == '':
                job_id = str(self.run_id)[:6]

            for fname in self.output_fnames:

                src = os.path.join(self.control_path, fname)

                stem, suffix = os.path.splitext(fname)
                dest = os.path.join(error_log_dir,
                                    ".".join((stem, job_id)) + suffix)

                print(src, dest)

                shutil.copyfile(src, dest)

            # Create the symlink to the logs if it does not exist
            make_symlink(self.archive_path, self.archive_sym_path)

            error_script = self.userscripts.get('error')
            if error_script:
                self.run_userscript(error_script)

            # Terminate payu
            sys.exit('payu: Model exited with error code {0}; aborting.'
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
        for f in self.output_fnames:
            f_path = os.path.join(self.control_path, f)
            if os.path.getsize(f_path) == 0:
                os.remove(f_path)
            else:
                shutil.move(f_path, self.work_path)

        run_script = self.userscripts.get('run')
        if run_script:
            self.run_userscript(run_script)

    def archive(self):
        if not self.config.get('archive', True):
            print('payu: not archiving due to config.yaml setting.')
            return

        # Check there is a work directory, otherwise bail
        if not os.path.exists(self.work_sym_path):
            sys.exit('payu: error: No work directory to archive.')

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

        movetree(self.work_path, self.output_path)

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
                if (os.path.isdir(res_path) and not os.path.islink(res_path)):
                    shutil.rmtree(res_path)

        # Ensure dynamic library support for subsequent python calls
        ld_libpaths = os.environ['LD_LIBRARY_PATH']
        py_libpath = sysconfig.get_config_var('LIBDIR')
        if py_libpath not in ld_libpaths.split(':'):
            os.environ['LD_LIBRARY_PATH'] = ':'.join([py_libpath, ld_libpaths])

        collate_config = self.config.get('collate', {})
        if collate_config.get('enable', True):
            cmd = '{python} {payu} collate -i {expt}'.format(
                python=sys.executable,
                payu=self.payu_path,
                expt=self.counter
            )
            sp.check_call(shlex.split(cmd))

        if self.config.get('hpctoolkit', False):
            cmd = '{python} {payu} profile -i {expt}'.format(
                python=sys.executable,
                payu=self.payu_path,
                expt=self.counter
            )
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
        envmod.setup()
        envmod.module('load', 'pbs')

        cmd = 'qsub {script}'.format(script=self.postscript)

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
        rsync_cmd = ('rsync -a --safe-links -e "ssh -i {key}" '
                     ''.format(key=ssh_key_path))

        if rsync_protocol:
            rsync_cmd += '--protocol={0} '.format(rsync_protocol)

        run_cmd = rsync_cmd + '{src} {dst}'.format(src=self.output_path,
                                                   dst=remote_url)
        rsync_calls = [run_cmd]

        if (self.counter % 5) == 0 and os.path.isdir(self.restart_path):
            # Tar restart files before rsyncing
            restart_tar_path = self.restart_path + '.tar.gz'

            cmd = ('tar -C {0} -czf {1} {2}'
                   ''.format(self.archive_path, restart_tar_path,
                             os.path.basename(self.restart_path)))
            sp.check_call(shlex.split(cmd))

            restart_cmd = ('{0} {1} {2}'
                           ''.format(rsync_cmd, restart_tar_path, remote_url))
            rsync_calls.append(restart_cmd)
        else:
            res_tar_path = None

        for model in self.models:
            for input_path in self.model.input_paths:
                # Using explicit path separators to rename the input directory
                input_cmd = rsync_cmd + '{0} {1}'.format(
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
        cmd = '{python} {payu} run -i {start} -n {n}'.format(
            python=sys.executable,
            payu=self.payu_path,
            start=next_run,
            n=self.n_runs
        )
        cmd = shlex.split(cmd)
        sp.call(cmd)

    def run_userscript(self, script_cmd):
        # First try to interpret the argument as a full command:
        try:
            sp.check_call(shlex.split(script_cmd))
        except EnvironmentError as exc:
            # Now try to run the script explicitly
            if exc.errno == errno.ENOENT:
                cmd = os.path.join(self.control_path, script_cmd)
                # Simplistic recursion check
                assert os.path.isfile(cmd)
                self.run_userscript(cmd)

            # If we get a "non-executable" error, then guess the type
            elif exc.errno == errno.EACCES:
                # TODO: Move outside
                ext_cmd = {'.py': sys.executable,
                           '.sh': '/bin/bash',
                           '.csh': '/bin/tcsh'}

                _, f_ext = os.path.splitext(script_cmd)
                shell_name = ext_cmd.get(f_ext)
                if shell_name:
                    print('payu: warning: Assuming that {0} is a {1} script '
                          'based on the filename extension.'
                          ''.format(os.path.basename(script_cmd),
                                    os.path.basename(shell_name)))
                    cmd = ' '.join([shell_name, script_cmd])
                    self.run_userscript(cmd)
                else:
                    # If we can't guess the shell, then abort
                    raise
        except sp.CalledProcessError as exc:
            # If the script runs but the output is bad, then warn the user
            print('payu: warning: user script \'{0}\' failed (error {1}).'
                  ''.format(script_cmd, exc.returncode))

    def sweep(self, hard_sweep=False):
        # TODO: Fix the IO race conditions!

        # TODO: model outstreams and pbs logs need to be handled separately
        default_job_name = os.path.basename(os.getcwd())
        short_job_name = str(self.config.get('jobname', default_job_name))[:15]

        logs = [
            f for f in os.listdir(os.curdir) if os.path.isfile(f) and (
                f.startswith(short_job_name + '.o') or
                f.startswith(short_job_name + '.e') or
                f.startswith(short_job_name[:13] + '_c.o') or
                f.startswith(short_job_name[:13] + '_c.e') or
                f.startswith(short_job_name[:13] + '_p.o') or
                f.startswith(short_job_name[:13] + '_p.e')
            )
        ]

        pbs_log_path = os.path.join(self.archive_path, 'pbs_logs')
        legacy_pbs_log_path = os.path.join(self.control_path, 'pbs_logs')

        if os.path.isdir(legacy_pbs_log_path):
            # TODO: New path may still exist!
            assert not os.path.isdir(pbs_log_path)
            print('payu: Moving pbs_logs to {0}'.format(pbs_log_path))
            shutil.move(legacy_pbs_log_path, pbs_log_path)
        else:
            mkdir_p(pbs_log_path)

        for f in logs:
            print('Moving log {0}'.format(f))
            shutil.move(f, os.path.join(pbs_log_path, f))

        if hard_sweep:
            if os.path.isdir(self.archive_path):
                print('Removing archive path {0}'.format(self.archive_path))
                cmd = 'rm -rf {0}'.format(self.archive_path)
                cmd = shlex.split(cmd)
                rc = sp.call(cmd)
                assert rc == 0

            if os.path.islink(self.archive_sym_path):
                print('Removing symlink {0}'.format(self.archive_sym_path))
                os.remove(self.archive_sym_path)

        # Remove stdout/err and yaml dumps
        for f in self.output_fnames:
            if os.path.isfile(f):
                os.remove(f)

        if os.path.isdir(self.work_path):
            print('Removing work path {0}'.format(self.work_path))
            cmd = 'rm -rf {0}'.format(self.work_path)
            cmd = shlex.split(cmd)
            rc = sp.call(cmd)
            assert rc == 0

        if os.path.islink(self.work_sym_path):
            print('Removing symlink {0}'.format(self.work_sym_path))
            os.remove(self.work_sym_path)


def enable_core_dump():
    # Newer Intel compilers support 'FOR_DUMP_CORE_FILE' while most support
    # 'decfort_dump_flag'.  Setting both for now, but there may be a more
    # platform-independent way to support this.

    # Enable Fortran core dump
    os.environ['FOR_DUMP_CORE_FILE'] = 'TRUE'
    os.environ['decfort_dump_flag'] = 'TRUE'

    # Allow unlimited core dump file sizes
    resource.setrlimit(resource.RLIMIT_CORE,
                       (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
