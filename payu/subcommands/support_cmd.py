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
    print(f"  {f'{label}:':<{label_width}} {value}")


def runcmd():
    print("=" * 40)
    payu_env_vars = cli.set_env_vars()

    # Get payu version and path
    payu_version = payu.__version__
    payu_path = payu_env_vars.get('PAYU_PATH')
    print_support("Payu Version", payu_version)
    print_support("Payu Path", payu_path)

    # Get python version and path
    python_version = platform.python_version()
    python_path = sys.executable
    print_support("Python Version", python_version)
    print_support("Python Path", python_path)

    # Get python path from environment variable
    python_path_env = os.environ.get('PYTHONPATH', None)
    if python_path_env:
        print_support("Python Path from Environment", python_path_env)

    # Print loaded modules
    loaded_modules = os.environ.get('LOADEDMODULES', None)
    if loaded_modules:
        print_support("LOADEDMODULES", loaded_modules)

    # Print machine information
    print_support("Machine Info", get_machine_info())

    print("=" * 40)

runscript = runcmd