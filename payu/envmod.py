# coding: utf-8
"""envmodules
   ==========

   A modular port of the Environment Modules Python ``init`` script
"""

import os
import shlex
import subprocess

# Python 2.6 subprocess.check_output support
if not hasattr(subprocess, 'check_output'):
    from backports import check_output
    subprocess.check_output = check_output

DEFAULT_BASEPATH = '/opt/Modules'
DEFAULT_VERSION = 'v4.3.0'


def setup(basepath=DEFAULT_BASEPATH):
    """Set the environment modules used by the Environment Module system."""

    module_version = os.environ.get('MODULE_VERSION', DEFAULT_VERSION)

    moduleshome = os.environ.get('MODULESHOME', None)

    if moduleshome is None:
        moduleshome = os.path.join(basepath, module_version)

    # Abort if MODULESHOME does not exist
    if not os.path.isdir(moduleshome):
        print('payu: warning: MODULESHOME does not exist; disabling '
              'environment modules.')
        try:
            del(os.environ['MODULESHOME'])
        except KeyError:
            pass
        return
    else:
        print('payu: Found modules in {}'.format(moduleshome))

    os.environ['MODULE_VERSION'] = module_version
    os.environ['MODULE_VERSION_STACK'] = module_version
    os.environ['MODULESHOME'] = moduleshome

    if 'MODULEPATH' not in os.environ:
        module_initpath = os.path.join(moduleshome, 'init', '.modulespath')
        with open(module_initpath) as initpaths:
            modpaths = [
                line.partition('#')[0].strip()
                for line in initpaths.readlines() if not line.startswith('#')
            ]

        os.environ['MODULEPATH'] = ':'.join(modpaths)

    os.environ['LOADEDMODULES'] = os.environ.get('LOADEDMODULES', '')

    # Environment modules with certain characters will cause corruption
    # when MPI jobs get launched on other nodes (possibly a PBS issue).
    #
    # Bash processes obscure the issue at NCI, since it occurs in an
    # environment module function, and bash moves those to the end of
    # the environment variable list.
    #
    # NCI's mpirun wrapper is a bash script, and therefore "fixes" by doing
    # the shuffle and limiting the damage to other bash functions, but some
    # wrappers (e.g. OpenMPI 2.1.x) may not be present.  So we manually patch
    # the problematic variable here.  But a more general solution would be nice
    # someday.

    if 'BASH_FUNC_module()' in os.environ:
        bash_func_module = os.environ['BASH_FUNC_module()']
        os.environ['BASH_FUNC_module()'] = bash_func_module.replace('\n', ';')


def module(command, *args):
    """Run the modulecmd tool and use its Python-formatted output to set the
    environment variables."""

    if 'MODULESHOME' not in os.environ:
        print('payu: warning: No Environment Modules found; skipping {0} call.'
              ''.format(command))
        return

    modulecmd = ('{0}/bin/modulecmd'.format(os.environ['MODULESHOME']))

    cmd = '{0} python {1} {2}'.format(modulecmd, command, ' '.join(args))

    envs, _ = subprocess.Popen(shlex.split(cmd),
                               stdout=subprocess.PIPE).communicate()
    exec(envs)


def lib_update(required_libs, lib_name):
    # Local import to avoid reversion interference
    # TODO: Bad design, fixme!
    # NOTE: We may be able to move this now that reversion is going away
    from payu import fsops

    for lib_filename, lib_path in required_libs.items():
        if lib_filename.startswith(lib_name) and lib_path.startswith('/apps/'): 
            # Load nci's /apps/ version of module if required 
            # pylint: disable=unbalanced-tuple-unpacking
            mod_name, mod_version = fsops.splitpath(lib_path)[2:4]

            module('unload', mod_name)
            module('load', os.path.join(mod_name, mod_version))
            return '{0}/{1}'.format(mod_name, mod_version)

    # If there are no libraries, return an empty string
    return ''


def paths_set_by_user_modules(user_modules, user_modulepaths):
    """Search along changes PATH added by user defined modules
    and return a set of paths added - this is used for
    searching for the model executable"""
    if 'MODULESHOME' not in os.environ:
        print('payu: warning: No Environment Modules found; skipping '
              'inspecting user module changes to PATH')
        return set()

    # Orginal environment
    previous_env = dict(os.environ)
    previous_modulepath = os.environ['MODULEPATH']

    # Set restrict module path to only user defined module paths
    os.environ['MODULEPATH'] = ':'.join(user_modulepaths)

    # Note: Using subprocess shell to isolate changes to environment
    paths = []
    try:
        # Get $PATH paths with no modules loaded
        init_paths = paths_post_module_commands(["purge"])
        for module in user_modules:
            # Check if module is available
            module_cmd = f"{os.environ['MODULESHOME']}/bin/modulecmd bash"
            cmd = f"{module_cmd} is-avail {module}"
            if run_cmd(cmd).returncode != 0:
                continue
            # TODO: Check if multiple modules are available..
            try:
                # Get $PATH paths post running module purge && module load
                paths.extend(paths_post_module_commands(['purge',
                                                         f'load {module}']))
            except subprocess.CalledProcessError as e:
                continue
    finally:
        os.environ['MODULEPATH'] = previous_modulepath

    if previous_env != os.environ:
        print(
            "Warning: Env vars changed when inspecting paths set by modules"
        )

    # Remove inital paths and convert into a set
    return set(paths).difference(set(init_paths))


def paths_post_module_commands(commands):
    """Runs subprocess module command and parse out the resulting
    PATH environment variable"""
    # Use modulecmd as module command is not available on compute nodes
    module_cmds = [
        f"eval `{os.environ['MODULESHOME']}/bin/modulecmd bash {c}`"
        for c in commands
    ]
    command = ' && '.join(module_cmds) + ' && echo $PATH'

    # Run Command and check the ouput
    output = run_cmd(command)
    output.check_returncode()

    # Extact out the PATH value, and split the paths
    path = output.stdout.strip().split('\n')[-1]
    return path.split(':')


def run_cmd(command):
    """Wrapper around subprocess command"""
    return subprocess.run(command, shell=True, text=True, capture_output=True)
