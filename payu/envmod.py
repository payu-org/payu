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
    # Bash processes obscure the issue on Raijin, since it occurs in an
    # environment module function, and bash moves those to the end of
    # the environment variable list.
    #
    # Raijin's mpirun wrapper is a bash script, and therefore "fixes" by doing
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


def lib_update(bin_path, lib_name):
    # Local import to avoid reversion interference
    # TODO: Bad design, fixme!
    # NOTE: We may be able to move this now that reversion is going away
    from payu import fsops

    # TODO: Use objdump instead of ldd
    cmd = 'ldd {0}'.format(bin_path)
    ldd_output = subprocess.check_output(shlex.split(cmd)).decode('ascii')
    slibs = ldd_output.split('\n')

    for lib_entry in slibs:
        if lib_name in lib_entry:
            lib_path = lib_entry.split()[2]

            # pylint: disable=unbalanced-tuple-unpacking
            mod_name, mod_version = fsops.splitpath(lib_path)[2:4]

            module('unload', mod_name)
            module('load', os.path.join(mod_name, mod_version))
            return '{0}/{1}'.format(mod_name, mod_version)

    # If there are no libraries, return an empty string
    return ''
