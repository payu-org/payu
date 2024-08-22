"""payu.experiment ===============

   Interface to an individual experiment managed by payu

   :copyright: Copyright 2011 Marshall Ward, see AUTHORS for details.
   :license: Apache License, Version 2.0, see LICENSE for details.
"""

from __future__ import print_function

# Standard Library
import datetime
import errno
import os
import re
import resource
import sys
import shlex
import shutil
import subprocess as sp
import sysconfig
from pathlib import Path

# Extensions
import yaml

# Local
from payu import envmod
from payu.fsops import mkdir_p, make_symlink, read_config, movetree
from payu.fsops import list_archive_dirs
from payu.fsops import run_script_command
from payu.fsops import needs_subprocess_shell
from payu.schedulers.pbs import get_job_info, pbs_env_init, get_job_id
from payu.models import index as model_index
import payu.profilers
from payu.runlog import Runlog
from payu.manifest import Manifest
from payu.calendar import parse_date_offset
from payu.sync import SyncToRemoteArchive
from payu.metadata import Metadata

# Environment module support on vayu
# TODO: To be removed
core_modules = ['python', 'payu']

# Default payu parameters
default_restart_freq = 5


class Experiment(object):

    def __init__(self, lab, reproduce=False, force=False, metadata_off=False):
        self.lab = lab

        if not force:
            # check environment for force flag under PBS
            self.force = os.environ.get('PAYU_FORCE', False)
        else:
            self.force = force

        self.start_time = datetime.datetime.now()

        # Initialise experiment metadata - uuid and experiment name
        self.metadata = Metadata(Path(lab.archive_path), disabled=metadata_off)
        self.metadata.setup()

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

        # Create metadata file and move to archive
        self.metadata.write_metadata(restart_path=self.prior_restart_path)

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

        self.user_modules_paths = None

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

        submodel_config = dict((f, self.config[f]) for f in model_fields
                               if f in self.config)
        submodel_config['name'] = self.model_name

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
            # Check for restart index
            max_restart_index = self.max_output_index(output_type="restart")
            if max_restart_index is not None:
                self.counter = 1 + max_restart_index
            else:
                # Now look for output directories,
                # as repeat runs do not generate restart files.
                max_output_index = self.max_output_index()
                if max_output_index is not None:
                    self.counter = 1 + max_output_index
                else:
                    self.counter = 0

    def max_output_index(self, output_type="output"):
        """Given a output directory type (output or restart),
        return the maximum index of output directories found"""
        try:
            output_dirs = list_archive_dirs(archive_path=self.archive_path,
                                            dir_type=output_type)
        except EnvironmentError as exc:
            if exc.errno == errno.ENOENT:
                output_dirs = None
            else:
                raise

        if output_dirs and len(output_dirs):
            return int(output_dirs[-1].lstrip(output_type))

    def set_stacksize(self, stacksize):

        if stacksize == 'unlimited':
            stacksize = resource.RLIM_INFINITY
        else:
            assert type(stacksize) is int

        resource.setrlimit(resource.RLIMIT_STACK,
                           (stacksize, resource.RLIM_INFINITY))

    def setup_modules(self):
        """Setup modules and get paths added to $PATH by user-modules"""
        envmod.setup()

        # Get user modules info from config
        user_modulepaths = self.config.get('modules', {}).get('use', [])
        user_modules = self.config.get('modules', {}).get('load', [])

        # Run module use + load commands for user-defined modules, and
        # get a set of paths and loaded modules added by loading the modules
        loaded_mods, paths = envmod.setup_user_modules(user_modules,
                                                       user_modulepaths)
        self.user_modules_paths = paths
        self.loaded_user_modules = [] if loaded_mods is None else loaded_mods

    def load_modules(self):
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
                if (mod_base not in core_modules and
                        mod not in self.loaded_user_modules):
                    envmod.module('unload', mod)

        # Now load model-dependent modules
        for mod in self.modules:
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

        # Local "control" path default used to be applied here,
        # but now done in read_config
        self.control_path = self.config.get('control_path')

        # Experiment name
        self.name = self.metadata.experiment_name

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
            assert (os.path.isdir(user_restart_dir))
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

        # Set up executable paths - first search through paths added by modules
        self.setup_modules()
        for model in self.models:
            model.setup_executable_paths()

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

        # Check restart pruning for valid configuration values and
        # warns user if more restarts than expected would be pruned
        if self.config.get('archive', True):
            self.get_restarts_to_prune()

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

        # MPI runtime flags
        mpi_flags = mpi_config.get('flags', [])
        if not mpi_flags:
            # DEPRECATED: confusing and a duplication of flags config
            if 'mpirun' in self.config:
                mpi_flags = self.config.get('mpirun')
                print('payu: warning: mpirun config option is deprecated.'
                      '  Use mpi: flags option instead')
            else:
                mpi_flags = []

        if not isinstance(mpi_flags, list):
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
            if mpi_module is None and model.required_libs is not None:
                envmod.lib_update(
                    model.required_libs,
                    'libmpi.so'
                )

            model_prog = []

            wdir_arg = '-wdir'
            if self.config.get('scheduler') == 'slurm':
                # Option to set the working directory differs in slurm
                wdir_arg = '--chdir'
            model_prog.append(f'{wdir_arg} {model.work_path}')

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
                    model_prog.append(prof.runscript)

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

    def archive(self, force_prune_restarts=False):
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

        # Remove any outdated restart files
        try:
            restarts_to_prune = self.get_restarts_to_prune(
                force=force_prune_restarts)
        except Exception as e:
            print(e)
            print("payu: error: Skipping pruning restarts")
            restarts_to_prune = []

        for restart in restarts_to_prune:
            restart_path = os.path.join(self.archive_path, restart)
            # Only delete real directories; ignore symbolic restart links
            if (os.path.isdir(restart_path) and
                    not os.path.islink(restart_path)):
                shutil.rmtree(restart_path)

        # Ensure dynamic library support for subsequent python calls
        ld_libpaths = os.environ.get('LD_LIBRARY_PATH', None)
        py_libpath = sysconfig.get_config_var('LIBDIR')
        if ld_libpaths is None:
            os.environ['LD_LIBRARY_PATH'] = py_libpath
        elif py_libpath not in ld_libpaths.split(':'):
            os.environ['LD_LIBRARY_PATH'] = f'{py_libpath}:{ld_libpaths}'

        collate_config = self.config.get('collate', {})
        collating = collate_config.get('enable', True)
        if collating:
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

        # Ensure postprocessing runs if model not collating
        if not collating:
            self.postprocess()

    def collate(self):
        # Setup modules - load user-defined modules
        self.setup_modules()

        for model in self.models:
            model.collate()

    def profile(self):
        for model in self.models:
            model.profile()

    def postprocess(self):
        """Submit any postprocessing scripts or remote syncing if enabled"""

        # First submit postprocessing script
        if self.postscript:
            self.set_userscript_env_vars()
            envmod.setup()
            envmod.module('load', 'pbs')

            cmd = 'qsub {script}'.format(script=self.postscript)

            if needs_subprocess_shell(cmd):
                sp.check_call(cmd, shell=True)
            else:
                sp.check_call(shlex.split(cmd))

        # Submit a sync script if remote syncing is enabled
        sync_config = self.config.get('sync', {})
        syncing = sync_config.get('enable', False)
        if syncing:
            cmd = '{python} {payu} sync'.format(
                python=sys.executable,
                payu=self.payu_path
            )

            if self.postscript:
                print('payu: warning: postscript is configured, so by default '
                      'the lastest outputs will not be synced. To sync the '
                      'latest output, after the postscript job has completed '
                      'run:\n'
                      '    payu sync')
                cmd += f' --sync-ignore-last'

            sp.check_call(shlex.split(cmd))

    def sync(self):
        # RUN any user scripts before syncing archive
        envmod.setup()
        pre_sync_script = self.userscripts.get('sync')
        if pre_sync_script:
            self.run_userscript(pre_sync_script)

        # Run rsync commmands
        SyncToRemoteArchive(self).run()

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

    def set_userscript_env_vars(self):
        """Save information of output directories and current run to
        environment variables, so they can be accessed via user-scripts"""
        os.environ.update(
            {
                'PAYU_CURRENT_OUTPUT_DIR': self.output_path,
                'PAYU_CURRENT_RESTART_DIR': self.restart_path,
                'PAYU_ARCHIVE_DIR': self.archive_path,
                'PAYU_CURRENT_RUN': str(self.counter)
            }
        )

    def run_userscript(self, script_cmd: str):
        """Run a user defined script or subcommand at various stages of the
        payu submissions"""
        self.set_userscript_env_vars()
        run_script_command(script_cmd,
                           control_path=Path(self.control_path))

    def sweep(self, hard_sweep=False):
        # TODO: Fix the IO race conditions!

        # TODO: model outstreams and pbs logs need to be handled separately
        default_job_name = os.path.basename(os.getcwd())
        short_job_name = str(self.config.get('jobname', default_job_name))[:15]

        log_filenames = [short_job_name + '.o', short_job_name + '.e']
        for postfix in ['_c.o', '_c.e', '_p.o', '_p.e', '_s.o', '_s.e']:
            log_filenames.append(short_job_name[:13] + postfix)

        logs = [
            f for f in os.listdir(os.curdir) if os.path.isfile(f) and (
                f.startswith(tuple(log_filenames))
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

    def get_restarts_to_prune(self,
                              ignore_intermediate_restarts=False,
                              force=False):
        """Returns a list of restart directories that can be pruned"""
        # Check if archive path exists
        if not os.path.exists(self.archive_path):
            return []

        # Sorted list of restart directories in archive
        restarts = list_archive_dirs(archive_path=self.archive_path,
                                     dir_type='restart')
        restart_indices = {}
        for restart in restarts:
            restart_indices[restart] = int(restart.lstrip('restart'))

        # TODO: Previous logic was to prune all restarts if self.repeat_run
        # Still need to figure out what should happen in this case
        if self.repeat_run:
            return [os.path.join(self.archive_path, restart)
                    for restart in restarts]

        # Use restart_freq to decide what restarts to prune
        restarts_to_prune = []
        intermediate_restarts, previous_intermediate_restarts = [], []
        restart_freq = self.config.get('restart_freq', default_restart_freq)
        if isinstance(restart_freq, int):
            # Using integer frequency to prune restarts
            for restart, restart_index in restart_indices.items():
                if not restart_index % restart_freq == 0:
                    intermediate_restarts.append(restart)
                else:
                    # Add any intermediate restarts to restarts to prune
                    restarts_to_prune.extend(intermediate_restarts)
                    previous_intermediate_restarts = intermediate_restarts
                    intermediate_restarts = []
        else:
            # Using date-based frequency to prune restarts
            try:
                date_offset = parse_date_offset(restart_freq)
            except ValueError as e:
                print('payu: error: Invalid configuration for restart_freq:',
                      restart_freq)
                raise

            next_dt = None
            for restart in restarts:
                # Use model-driver to parse restart directory for a datetime
                restart_path = os.path.join(self.archive_path, restart)
                try:
                    restart_dt = self.model.get_restart_datetime(restart_path)
                except NotImplementedError:
                    print('payu: error: Date-based restart pruning is not '
                          f'implemented for the {self.model.model_type} '
                          'model. To use integer based restart pruning, '
                          'set restart_freq to an integer value.')
                    raise
                except FileNotFoundError as e:
                    print(f'payu: warning: Ignoring {restart} from date-based '
                          f'restart pruning. Error: {e}')
                    continue
                except Exception:
                    print('payu: error: Error parsing restart directory ',
                          f'{restart} for a datetime to prune restarts.')
                    raise

                if (next_dt is not None and restart_dt < next_dt):
                    intermediate_restarts.append(restart)
                else:
                    # Keep the earliest datetime and use last kept datetime
                    # as point of reference when adding the next time interval
                    next_dt = date_offset.add_to_datetime(restart_dt)

                    # Add intermediate restarts to restarts to prune
                    restarts_to_prune.extend(intermediate_restarts)
                    previous_intermediate_restarts = intermediate_restarts
                    intermediate_restarts = []

        if ignore_intermediate_restarts:
            # Return all restarts that'll eventually be pruned
            restarts_to_prune.extend(intermediate_restarts)
            return restarts_to_prune

        if not force:
            # check environment for --force-prune-restarts flag
            force = os.environ.get('PAYU_FORCE_PRUNE_RESTARTS', False)

        # Flag to check whether more restarts than expected will be deleted
        is_unexpected = restarts_to_prune != previous_intermediate_restarts

        # Restart_history override
        restart_history = self.config.get('restart_history', None)
        if restart_history is not None:
            if not isinstance(restart_history, int):
                raise ValueError("payu: error: restart_history is not an "
                                 f"integer value: {restart_history}")

            if len(restarts) > 0:
                max_index = restart_indices[restarts[-1]]
                index_bound = max_index - restart_history

                # Keep restart_history latest restarts, in addition to the
                # permanently saved restarts defined by restart_freq
                restarts_to_prune.extend(intermediate_restarts)
                restarts_to_prune = [res for res in restarts_to_prune
                                     if restart_indices[res] <= index_bound]

                # Expect at most 1 restart to be pruned with restart_history
                is_unexpected = len(restarts_to_prune) > 1

        # Log out warning if more restarts than expected will be deleted
        if not force and is_unexpected:
            config_info = (f'restart pruning frequency of {restart_freq}')
            if restart_history:
                config_info += f' and restart history of {restart_history}'

            print(f'payu: warning: Current {config_info} would result in '
                  'following restarts being pruned: '
                  f'{" ".join(restarts_to_prune)}\n'
                  'If this is expected, use --force-prune-restarts flag at '
                  'next run or archive (if running archive manually), e.g.:\n'
                  '     payu run --force-prune-restarts, or\n'
                  '     payu archive --force-prune-restarts\n'
                  'Otherwise, no restarts will be pruned')

            # Return empty list to prevent restarts being pruned
            restarts_to_prune = []

        return restarts_to_prune


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
