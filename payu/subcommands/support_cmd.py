# coding: utf-8

# Standard Library
import os
import sys
import subprocess
import platform
import warnings

# Local
import payu
from payu import cli

warning_msg = "Unable to get machine information using platform module."

title = 'support'
parameters = {'description': 'generate report of system information for debugging and support requests'}

arguments = []

def get_machine_info():
    """Get machine information using platform module."""
    os_info = platform.freedesktop_os_release()
    
    system_name = os_info.get('NAME', None)
    version_id = os_info.get('VERSION_ID', None)

    machine_type = platform.machine()

    return f"{system_name}-{version_id}-{machine_type}"

def print_support(label, value):
    """Print support information in a consistent format."""
    label_width = 18
    # If value is a string, print it directly.
    if isinstance(value, str):
        print(f"  {f'{label}:':<{label_width}} {value}")
        
    # If value is a list, print each item on a new line with the label only on the first line.
    elif isinstance(value, list) and len(value) > 0:
        print(f"  {f'{label}:':<{label_width}} {value[0]}")
        for item in value[1:]:
            print(f"  {' ':<{label_width}} {item}")


def runcmd():
    print("=" * 40)
    # Get payu version and path
    payu_version = payu.__version__
    print_support("Payu Version", payu_version)

    payu_env_vars = cli.set_env_vars()
    payu_path = payu_env_vars.get('PAYU_PATH')
    print_support("Payu Path", payu_path)

    # Get python version and path
    python_version = platform.python_version()
    print_support("Python Version", python_version)

    # Print system path
    sys_path_list = sys.path
    print_support("System Path", sys_path_list)

    # Print loaded modules
    loaded_modules = os.environ.get('LOADEDMODULES', None)
    if loaded_modules:
        print_support("Loaded Modules", loaded_modules)

    # Print machine information
    print_support("Machine Info", get_machine_info())

    print("=" * 40)

runscript = runcmd