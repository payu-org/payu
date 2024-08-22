"""Generic model interface, primarily to be inherited by other models.

:copyright: Copyright 2011 Marshall Ward, see AUTHORS for details
:license: Apache License, Version 2.0, see LICENSE for details
"""
import errno
import os
import shutil
import shlex
import sys
import subprocess as sp

from payu import envmod
from payu.fsops import mkdir_p, required_libs


class Model(object):
    """Abstract model class."""

    def __init__(self, expt, model_name, model_config):
        """Create the model interface."""
        # Inherit experiment configuration
        self.expt = expt
        self.name = model_name
        self.config = model_config
        self.top_level_model = False

        # Model details
        self.model_type = None
        self.default_exec = None
        self.input_basepath = None
        self.modules = []
        self.config_files = []
        self.optional_config_files = []

        # Path names
        self.work_input_path = None
        self.work_restart_path = None
        self.work_init_path = None
        # A string to add before the exe name, useful for e.g. gdb, gprof,
        # valgrind
        self.exec_prefix = None
        self.exec_path = None
        self.exec_name = None
        self.codebase_path = None
        self.work_path_local = None
        self.work_input_path_local = None
        self.work_restart_path_local = None
        self.work_init_path_local = None
        self.exec_path_local = None

        self.build_exec_path = None
        self.build_path = None

        self.required_libs = None

        # Control flags
        self.copy_restarts = False
        self.copy_inputs = False

        # Codebase details
        self.repo_url = None
        self.repo_tag = None
        self.build_command = None

    def set_model_pathnames(self):
        """Define the paths associated with this model."""
        self.control_path = self.expt.control_path
        self.input_basepath = self.expt.lab.input_basepath
        self.work_path = self.expt.work_path
        self.codebase_path = self.expt.lab.codebase_path

        if len(self.expt.models) > 1:

            self.control_path = os.path.join(self.control_path, self.name)
            self.work_path = os.path.join(self.work_path, self.name)
            self.codebase_path = os.path.join(self.codebase_path, self.name)

        # NOTE: Individual models may override the work subdirectories
        self.work_input_path = self.work_path
        self.work_restart_path = self.work_path
        self.work_output_path = self.work_path
        self.work_init_path = self.work_path

    def set_local_pathnames(self):

        # This is the path relative to the control directory, required for
        # manifests and must be called after set_model_pathnames to ensure it
        # captures changes made in model subclasses which override
        # set_model_pathnames

        # XXX: If path is relative to control_path, why not use it?
        self.work_path_local = os.path.normpath(
            os.path.join(
                'work',
                os.path.relpath(self.work_path, self.expt.work_path)
            )
        )
        self.work_input_path_local = os.path.normpath(
            os.path.join(
                'work',
                os.path.relpath(self.work_input_path, self.expt.work_path)
            )
        )
        self.work_restart_path_local = os.path.normpath(
            os.path.join(
                'work',
                os.path.relpath(self.work_restart_path, self.expt.work_path)
            )
        )
        self.work_init_path_local = os.path.normpath(
            os.path.join(
                'work',
                os.path.relpath(self.work_init_path, self.expt.work_path)
            )
        )

    def set_input_paths(self):
        if len(self.expt.models) == 1:
            input_dirs = self.expt.config.get('input')
        else:
            input_dirs = self.config.get('input')

        if input_dirs is None:
            input_dirs = []
        elif isinstance(input_dirs, str):
            input_dirs = [input_dirs]

        self.input_paths = []
        for input_dir in input_dirs:

            # First test for absolute path
            if os.path.exists(input_dir):
                self.input_paths.append(input_dir)
            else:
                # Test for path relative to /${lab_path}/input/${model_name}
                assert self.input_basepath
                rel_path = os.path.join(self.input_basepath, input_dir)
                if os.path.exists(rel_path):
                    self.input_paths.append(rel_path)
                else:
                    sys.exit('payu: error: Input directory {0} not found; '
                             'aborting.'.format(rel_path))

    def set_model_output_paths(self):

        self.output_path = self.expt.output_path
        self.restart_path = self.expt.restart_path

        self.prior_output_path = self.expt.prior_output_path
        self.prior_restart_path = self.expt.prior_restart_path

        if len(self.expt.models) > 1:

            # If '-d' option specified for collate don't want to change the
            # output path, but respect the absolute path specified
            if os.environ.get('PAYU_DIR_PATH') is None:
                self.output_path = os.path.join(self.output_path, self.name)

            self.restart_path = os.path.join(self.restart_path, self.name)

            if self.prior_output_path:
                self.prior_output_path = os.path.join(self.prior_output_path,
                                                      self.name)

            if self.prior_restart_path:
                self.prior_restart_path = os.path.join(self.prior_restart_path,
                                                       self.name)

    def get_prior_restart_files(self):

        try:
            respath = self.prior_restart_path
            return [f for f in os.listdir(respath)
                    if os.path.isfile(os.path.join(respath, f))]
        except Exception as e:
            print("No prior restart files found: {error}".format(error=str(e)))
            return []

    def expand_executable_path(self, exec):
        """Given an executable, return the expanded executable path"""
        # Check if exe is already an absolute path
        if os.path.isabs(exec):
            return exec

        # Check if path set by loading user modules has been defined
        module_added_paths = self.expt.user_modules_paths
        if module_added_paths is None:
            print("payu: warning: Skipping searching for model executable " +
                  "in $PATH set by user modules")
            module_added_paths = []

        # Search for exe inside paths added to $PATH by user-defined modules
        exec_paths = []
        for path in module_added_paths:
            exec_path = os.path.join(path, exec)
            if os.path.exists(exec_path) and os.access(exec_path, os.X_OK):
                exec_paths.append(exec_path)

        if len(exec_paths) > 1:
            raise ValueError(
                f"Executable {exec} found in multiple $PATH paths added by " +
                f"user-defined modules in `config.yaml`. Paths: {exec_paths}")
        elif len(exec_paths) == 1:
            return exec_paths[0]

        # Else prepend the lab bin path to exec
        return os.path.join(self.expt.lab.bin_path, exec)

    def setup_executable_paths(self):
        """Set model executable paths"""
        self.exec_prefix = self.config.get('exe_prefix', '')
        self.exec_name = self.config.get('exe', self.default_exec)
        self.exec_path = None
        if self.exec_name:
            self.exec_path = self.expand_executable_path(self.exec_name)

            # Make exec_name consistent for models with fully qualified path.
            # In all cases it will just be the name of the executable without a
            # path
            self.exec_name = os.path.basename(self.exec_path)

            # Local path in work directory
            self.exec_path_local = os.path.join(
                self.work_path_local,
                os.path.basename(self.exec_path)
            )

    def setup_configuration_files(self):
        """Copy configuration and optional configuration files from control
         path to work path"""
        for f_name in self.config_files:
            f_path = os.path.join(self.control_path, f_name)
            shutil.copy(f_path, self.work_path)

        for f_name in self.optional_config_files:
            f_path = os.path.join(self.control_path, f_name)
            try:
                shutil.copy(f_path, self.work_path)
            except IOError as exc:
                if exc.errno == errno.ENOENT:
                    pass
                else:
                    raise

    def setup(self):

        print("Setting up {model}".format(model=self.name))
        # Create experiment directory structure
        mkdir_p(self.work_init_path)
        mkdir_p(self.work_input_path)
        mkdir_p(self.work_restart_path)
        mkdir_p(self.work_output_path)

        # Copy configuration files from control path
        self.setup_configuration_files()

        # Add restart files from prior run to restart manifest
        if self.prior_restart_path:
            restart_files = self.get_prior_restart_files()
            for f_name in restart_files:
                f_orig = os.path.join(self.prior_restart_path, f_name)
                f_link = os.path.join(self.work_init_path_local, f_name)
                self.expt.manifest.add_filepath(
                    'restart',
                    f_link,
                    f_orig,
                    self.copy_restarts
                )

        # Add input files to input manifest
        for input_path in self.input_paths:
            if os.path.isfile(input_path):
                # Build a mock walk iterator for a single file
                fwalk = iter([(
                    os.path.dirname(input_path),
                    [],
                    [os.path.basename(input_path)]
                )])
                # Overwrite the input_path as a directory
                input_path = os.path.dirname(input_path)
            else:
                fwalk = os.walk(input_path)

            for path, dirs, files in fwalk:
                workrelpath = os.path.relpath(path, input_path)
                subdir = os.path.normpath(
                    os.path.join(self.work_input_path_local,
                                 workrelpath)
                )

                if not os.path.exists(subdir):
                    os.mkdir(subdir)

                for f_name in files:
                    f_orig = os.path.join(path, f_name)
                    f_link = os.path.join(
                        self.work_input_path_local,
                        workrelpath,
                        f_name
                    )
                    # Do not use input file if already linked
                    # as a restart file
                    if not os.path.exists(f_link):
                        self.expt.manifest.add_filepath(
                            'input',
                            f_link,
                            f_orig,
                            self.copy_inputs
                        )

        # Make symlink to executable in work directory
        if self.exec_path:
            # Check whether executable path exists
            if not os.path.isfile(self.exec_path):
                raise FileNotFoundError(
                    f'Executable for {self.name} model '
                    f'not found on path: {self.exec_path}')

            # Check whether executable has executable permission
            if not os.access(self.exec_path, os.X_OK):
                raise PermissionError(
                    f'Executable for {self.name} model '
                    f'is not executable: {self.exec_path}')

            # Add to exe manifest (this is always done so any change in exe
            # path will be picked up)
            self.expt.manifest.add_filepath(
                'exe',
                self.exec_path_local,
                self.exec_path
            )

            # Populate information about required dynamically loaded libraries
            self.required_libs = required_libs(self.exec_path)

        timestep = self.config.get('timestep')
        if timestep:
            self.set_timestep(timestep)

    def set_timestep(self, timestep):
        """Set the model timestep."""
        raise NotImplementedError

    def archive(self):
        """Store model output to laboratory archive."""

        # Traverse the model directory deleting symlinks, zero length files
        # and empty directories
        for path, dirs, files in os.walk(self.work_path, topdown=False):
            for f_name in files:
                f_path = os.path.join(path, f_name)
                if os.path.islink(f_path) or os.path.getsize(f_path) == 0:
                    os.remove(f_path)
            if len(os.listdir(path)) == 0:
                os.rmdir(path)

    def collate(self):
        """Collate any tiled output into a single file."""
        raise NotImplementedError

    def build_model(self):
        self.setup_executable_paths()

        if not self.repo_url:
            return

        # Check to see if executable already exists.
        if self.exec_path and os.path.isfile(self.exec_path):
            print('payu: warning: {0} will be overwritten.'
                  ''.format(self.exec_path))

        # First step is always to go to the codebase.
        curdir = os.getcwd()

        # Do the build. First check whether there is a build command in the
        # config. If not check for the model default, otherwise just run make.

        try:
            build_path = self.config['build']['path_to_build_command']
        except KeyError:
            if self.build_path:
                build_path = self.build_path
            else:
                build_path = './'

        os.chdir(os.path.join(self.codebase_path, build_path))

        try:
            cmd = self.config['build']['command']
        except KeyError:
            if self.build_command:
                cmd = self.build_command
            else:
                cmd = 'make'

        print('Running command {0}'.format(cmd))
        sp.check_call(shlex.split(cmd))

        try:
            build_exec_path = os.path.join(self.codebase_path,
                                           self.config['build']['exec_path'])
        except KeyError:
            if self.build_exec_path:
                build_exec_path = self.build_exec_path
            else:
                build_exec_path = self.codebase_path

        # Copy new executable to bin dir
        if self.exec_path:
            # Create the bin path if it doesn't exist
            mkdir_p(self.expt.lab.bin_path)

            build_exec_path = os.path.join(build_exec_path, self.exec_name)
            shutil.copy(build_exec_path, self.exec_path)

        os.chdir(curdir)

    def get_codebase(self):

        if not self.repo_url:
            return

        # Disable the user's .gitconfig file
        os.environ['GIT_CONFIG_NOGLOBAL'] = 'yes'

        build_config = self.config.get('build', {})
        self.repo_url = build_config.get('repository', self.repo_url)
        self.repo_tag = build_config.get('tag', self.repo_tag)

        git_path = os.path.join(self.codebase_path, '.git')
        if not os.path.exists(git_path):
            cmd = 'git clone {0} {1}'.format(self.repo_url, self.codebase_path)
            sp.check_call(shlex.split(cmd))

        curdir = os.getcwd()
        os.chdir(self.codebase_path)
        sp.check_call(shlex.split('git checkout {0}'.format(self.repo_tag)))
        sp.check_call(shlex.split('git pull'))
        os.chdir(curdir)

    def profile(self):
        # TODO: Replace with call to "profile" drivers

        if self.expt.config.get('hpctoolkit', False) and self.exec_name:

            envmod.module('load', 'hpctoolkit')

            # Create the code structure file
            hpcstruct_fname = '{0}.hpcstruct'.format(self.exec_name)
            hpcstruct_path = os.path.join(self.expt.lab.bin_path,
                                          hpcstruct_fname)

            # TODO: Validate struct file
            if not os.path.isfile(hpcstruct_path):
                cmd = 'hpcstruct -o {0} {1}'.format(hpcstruct_path,
                                                    self.exec_path)
                sp.check_call(shlex.split(cmd))

            # Parse the profile output
            hpctk_header = 'hpctoolkit-{0}-measurements'.format(self.exec_name)
            hpctk_measure_dir = [os.path.join(self.output_path, f)
                                 for f in os.listdir(self.output_path)
                                 if f.startswith(hpctk_header)][0]

            hpctk_db_dir = hpctk_measure_dir.replace('measurements',
                                                     'database')

            # TODO: This needs to be model-specifc
            src_path = os.path.join(self.codebase_path, 'src')

            cmd = 'hpcprof-mpi -S {0} -I {1} -o {2} {3}'.format(
                hpcstruct_path, src_path, hpctk_db_dir, hpctk_measure_dir)
            sp.check_call(shlex.split(cmd))

        if self.expt.config.get('scalasca', False):

            envmod.module('use', '/home/900/mpc900/my_modules')
            envmod.module('load', 'scalasca')

            scorep_path = [os.path.join(self.output_path, f)
                           for f in os.listdir(self.output_path)
                           if f.startswith('scorep')][0]
            cmd = 'scalasca -examine -s {0}'.format(scorep_path)
            sp.check_call(shlex.split(cmd))

        if self.expt.config.get('scorep', False):

            envmod.module('load', 'scorep')

            scorep_path = [os.path.join(self.output_path, f)
                           for f in os.listdir(self.output_path)
                           if f.startswith('scorep')][0]
            cube_path = [os.path.join(scorep_path, f)
                         for f in os.listdir(scorep_path)
                         if f.endswith('.cubex')][0]
            cmd = 'scorep-score {0}'.format(cube_path)
            sp.check_call(shlex.split(cmd))

    def get_restart_datetime(self, restart_path):
        """Given a restart path, parse the restart files and return a cftime
        datetime (currently used for date-based restart pruning)"""
        raise NotImplementedError
