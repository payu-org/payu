# coding: utf-8
"""
Basic file system operations for Payu
-------------------------------------------------------------------------------
Contact: Marshall Ward <marshall.ward@anu.edu.au>
-------------------------------------------------------------------------------
Distributed as part of Payu, Copyright 2011 Marshall Ward
Licensed under the Apache License, Version 2.0
http://www.apache.org/licenses/LICENSE-2.0
"""

# Standard library
import errno
import os
import re
import shutil

# Extensions
import yaml

DEFAULT_CONFIG_FNAME = 'config.yaml'

# Lustre target paths for symbolic paths cannot be 60 characters (yes, really)
# Delete this once this bug in Lustre is fixed
CHECK_LUSTRE_PATH_LEN = True


#---
def mkdir_p(path):
    """Create a new directory; ignore if it already exists."""

    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise


#---
def read_config(config_fname=None):
    """Parse input configuration file and return a config dict."""

    if not config_fname:
        config_fname = DEFAULT_CONFIG_FNAME

    try:
        with open(config_fname, 'r') as config_file:
            config = yaml.load(config_file)
    except IOError as exc:
        if exc.errno == errno.ENOENT:
            config = {}
        else:
            raise

    return config


#---
def make_symlink(src_path, lnk_path):
    """Safely create a symbolic link to an input field."""

    # Check for Lustre 60-character symbolic link path bug
    if CHECK_LUSTRE_PATH_LEN:
        src_path = patch_lustre_path(src_path)
        lnk_path = patch_lustre_path(lnk_path)

    try:
        os.symlink(src_path, lnk_path)
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise
        elif not os.path.islink(lnk_path):
            # Warn the user, but do not interrput the job
            print("Warning: Cannot create symbolic link to {p}; a file named "
                  "{f} already exists.".format(p=src_path, f=lnk_path))
        else:
            # Overwrite any existing symbolic link
            if os.path.realpath(lnk_path) != src_path:
                os.remove(lnk_path)
                os.symlink(src_path, lnk_path)


#---
def splitpath(path):

    head, tail = os.path.split(path)
    if tail == '':
        return head,

    return splitpath(head) + (tail, )


#---
def patch_lustre_path(f_path):
    """Patch any 60-character pathnames, to avoid a current Lustre bug."""

    if CHECK_LUSTRE_PATH_LEN and len(f_path) == 60:
        if os.path.isabs(f_path):
            f_path = '/.' + f_path
        else:
            f_path = './' + f_path

    return f_path


#---
def patch_nml(nml_path, pattern, replace):
    """Replace lines matching ``pattern`` with ``replace`` of the Fortran
    namelist file located at ``nml_path``. If the file does not exist, then do
    nothing."""
    # NOTE: f90nml makes this subroutine redundant.

    temp_path = nml_path + '~'

    try:
        with open(nml_path) as nml, open(temp_path, 'w') as temp:

            re_pattern = re.compile(pattern, re.IGNORECASE)
            for line in nml:
                if re_pattern.match(line):
                    temp.write(replace)
                else:
                    temp.write(line)

        shutil.move(temp_path, nml_path)

    except IOError as exc:
        if exc.errno != errno.ENOENT:
            raise
