# coding: utf-8
"""envmodules
   ==========

   A modular port of the Environment Modules Python ``init`` script
"""

import os
import shlex
import subprocess

DEFAULT_VERSION = '3.2.6'

def setup():
    """Set the environment modules used by the Environment Module system."""

    # Update PATH
    payu_path = os.environ.get('PAYU_PATH')
    if payu_path and not payu_path in os.environ['PATH'].split(':'):
        os.environ['PATH'] = ':'.join([payu_path, os.environ['PATH']])

    module_version = os.environ.get('MODULE_VERSION', DEFAULT_VERSION)
    module_basepath = os.path.join('/opt/Modules', module_version)

    os.environ['MODULE_VERSION'] = module_version
    os.environ['MODULE_VERSION_STACK'] = module_version
    os.environ['MODULESHOME'] = module_basepath

    if not 'MODULEPATH' in os.environ:
        module_initpath = os.path.join(module_basepath, 'init', '.modulespath')
        with open(module_initpath) as initpaths:
            modpaths = [mpath.strip() for mpath in line.partition('#')
                        for line in initpaths.readlines()
                        if not line.startswith('#')]

        os.environ['MODULEPATH'] = ':'.join(modpaths)

    os.environ['LOADEDMODULES'] = os.environ.get('LOADEDMODULES', '')


def module(command, *args):
    """Run the modulecmd tool and use its Python-formatted output to set the
    environment variables."""

    modulecmd = ('/opt/Modules/{0}/bin/modulecmd'
                 ''.format(os.environ['MODULE_VERSION']))

    cmd = '{0} python {1} {2}'.format(modulecmd, command, ' '.join(args))

    envs, _ = subprocess.Popen(shlex.split(cmd),
                               stdout=subprocess.PIPE).communicate()
    exec(envs)


def lib_update(bin_path, lib_name):
    # Local import to avoid reversion interference
    from payu import fsops

    # TODO: Use objdump instead of ldd
    cmd = 'ldd {}'.format(bin_path)
    slibs = subprocess.check_output(shlex.split(cmd)).split('\n')

    for lib_entry in slibs:
        if lib_name in lib_entry:
            lib_path = lib_entry.split()[2]

            mod_name, mod_version = fsops.splitpath(lib_path)[2:4]

            module('unload', mod_name)
            module('load', os.path.join(mod_name, mod_version))
            break
