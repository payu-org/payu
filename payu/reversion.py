# coding: utf-8

import os
import sys

execfile('/opt/Modules/default/init/python')
def repython(version, script_path):

    # Ensure that payu is loaded
    try:
        module('use', os.environ['PAYU_MODULEPATH'])
        module('load', os.environ['PAYU_MODULENAME'])
    except KeyError:
        pass

    # NOTE: Older versions (<2.7) require the version as a tuple
    version_tuple = tuple(int(i) for i in version.split('.'))
    module_name = os.path.join('python', version)

    python_modules = [m for m in os.environ['LOADEDMODULES'].split(':')
                      if m.startswith('python')]

    if sys.version_info < version_tuple or not module_name in python_modules:

        # First unload all python (and supporting) modules
        python_modules = [m for m in os.environ['LOADEDMODULES'].split(':')
                          if m.startswith('python')]

        for mod in python_modules:
            module('unload', mod)

        # Replace with specified version
        module('load', module_name)

        # Replace the current python process with the updated version
        os.execl(script_path, *sys.argv)
