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

import errno
import os
import re
import shutil

#---
def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as ec:
        if ec.errno != errno.EEXIST:
            raise


#---
def make_symlink(path, link):
    try:
        os.symlink(path, link)
    except OSError as ec:
        if ec.errno != errno.EEXIST:
            raise
        elif not os.path.islink(link):
            # Warn the user, but do not interrput the job
            print("Warning: Cannot create symbolic link to {p}; a file named "
                  "{f} already exists.".format(p=path, f=link))
        else:
            # Overwrite any existing symbolic link
            if os.path.realpath(link) != path:
                os.remove(link)
                os.symlink(path, link)


#---
def patch_nml(nml_path, pattern, replace):
    """Replace lines matching ``pattern`` with ``replace`` of the Fortran
    namelist file located at ``nml_path``. If the file does not exist, then do
    nothing."""

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

    except IOError as ec:
        if ec.errno != errno.ENOENT:
            raise
