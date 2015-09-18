# coding: utf-8
"""envmodules
   ==========

   A modular port of the Environment Modules Python ``init`` script
"""

import os
import shlex
import subprocess

DEFAULT_BASEPATH = '/opt/Modules'
DEFAULT_VERSION = '3.2.6'


def setup(version=DEFAULT_VERSION, basepath=DEFAULT_BASEPATH):
    """Set the environment modules used by the Environment Module system."""

    # Update PATH
    payu_path = os.environ.get('PAYU_PATH')
    if payu_path and payu_path not in os.environ['PATH'].split(':'):
        os.environ['PATH'] = ':'.join([payu_path, os.environ['PATH']])

    module_version = os.environ.get('MODULE_VERSION', DEFAULT_VERSION)
    moduleshome = os.path.join(basepath, module_version)

    # Abort if MODULESHOME does not exist
    if not os.path.isdir(moduleshome):
        print('payu: warning: MODULESHOME does not exist; disabling '
              'environment modules.')
        os.environ['MODULESHOME'] = ''
        return

    os.environ['MODULE_VERSION'] = module_version
    os.environ['MODULE_VERSION_STACK'] = module_version
    os.environ['MODULESHOME'] = moduleshome

    if 'MODULEPATH' not in os.environ:
        module_initpath = os.path.join(moduleshome, 'init', '.modulespath')
        with open(module_initpath) as initpaths:
            modpaths = [mpath.strip() for mpath in line.partition('#')
                        for line in initpaths.readlines()
                        if not line.startswith('#')]

        os.environ['MODULEPATH'] = ':'.join(modpaths)

    os.environ['LOADEDMODULES'] = os.environ.get('LOADEDMODULES', '')


def module(command, *args):
    """Run the modulecmd tool and use its Python-formatted output to set the
    environment variables."""

    if not os.environ['MODULESHOME']:
        print('payu: warning: No Environment Modules found; skipping {} call.'
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
    from payu import fsops

    # TODO: Use objdump instead of ldd
    cmd = 'ldd {0}'.format(bin_path)
    slibs = subprocess.check_output(shlex.split(cmd)).split('\n')

    for lib_entry in slibs:
        if lib_name in lib_entry:
            lib_path = lib_entry.split()[2]

            mod_name, mod_version = fsops.splitpath(lib_path)[2:4]

            module('unload', mod_name)
            module('load', os.path.join(mod_name, mod_version))
            return '{0}/{1}'.format(mod_name, mod_version)

    # If there are no libraries, return an empty string
    return ''
