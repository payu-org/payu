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

    envs, err = subprocess.Popen(shlex.split(cmd),
                                 stdout=subprocess.PIPE).communicate()
    exec(envs)
