import os
import sys

execfile('/opt/Modules/default/init/python')
def repython(python_version, script_path):

    # NOTE: Older versions (<2.7) require the version as a tuple
    python_version_tuple = tuple(int(i) for i in python_version.split('.'))

    if sys.version_info < python_version_tuple:
        # First unload all python (and supporting) modules
        python_modules = [m for m in os.environ['LOADEDMODULES'].split(':')
                          if m.startswith('python')]

        for mod in python_modules:
            module('unload', mod)

        # Replace with specified version
        module('load', os.path.join('python', python_version))

        # Update payu version if provided
        try:
            module('use', os.environ['PAYU_MODULEPATH'])
            module('load', os.environ['PAYU_MODULENAME'])
        except KeyError:
            pass

        # Replace the current python process with the updated version
        os.execl(script_path, *sys.argv)
