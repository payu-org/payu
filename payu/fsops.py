"""payu.experiment
   ===============

   Basic file system operations for Payu

   :copyright: Copyright 2011 Marshall Ward, see AUTHORS for details.
   :license: Apache License, Version 2.0, see LICENSE for details.
"""

# Standard library
import errno
import os
from pathlib import Path
import re
import shutil
import sys
import shlex
import subprocess
from typing import Union, List

# Extensions
import yaml

DEFAULT_CONFIG_FNAME = 'config.yaml'

# Lustre target paths for symbolic paths cannot be 60 characters (yes, really)
# Delete this once this bug in Lustre is fixed
CHECK_LUSTRE_PATH_LEN = True


def mkdir_p(path):
    """Create a new directory; ignore if it already exists."""

    try:
        os.makedirs(path)
    except EnvironmentError as exc:
        if exc.errno != errno.EEXIST:
            raise


def movetree(src, dst, symlinks=False):
    """
    Code based on shutil copytree, but non-recursive
    as uses move for contents of src directory
    """
    names = os.listdir(src)
    os.makedirs(dst)
    for name in names:
        srcname = os.path.join(src, name)
        dstname = os.path.join(dst, name)
        if symlinks and os.path.islink(srcname):
            linkto = os.readlink(srcname)
            os.symlink(linkto, dstname)
        else:
            shutil.move(srcname, dstname)

    shutil.rmtree(src)


def read_config(config_fname=None):
    """Parse input configuration file and return a config dict."""

    if not config_fname:
        config_fname = DEFAULT_CONFIG_FNAME

    try:
        with open(config_fname, 'r') as config_file:
            config = yaml.safe_load(config_file)

        # NOTE: A YAML file with no content returns `None`
        if config is None:
            config = {}
    except IOError as exc:
        if exc.errno == errno.ENOENT:
            print('payu: warning: Configuration file {0} not found!'
                  .format(config_fname))
            config = {}
        else:
            raise

    collate_config = config.pop('collate', {})

    # Transform legacy collate config options
    if type(collate_config) is bool:
        collate_config = {'enable': collate_config}

    collatestr = 'collate_'
    foundkeys = []
    # Cycle through old collate config and convert to newer dict format
    for key in list(config.keys()):
        if key.startswith(collatestr):
            foundkeys.append(key)
            collate_config[key[len(collatestr):]] = config.pop(key)
    if foundkeys:
        print("Use of these keys is deprecated: {}.".format(
                ", ".join(foundkeys)))
        print("Instead use collate dictionary and subkey "
              "without 'collate_' prefix")

    config['collate'] = collate_config

    # Transform legacy modules config options
    modules_config = config.pop('modules', {})
    if type(modules_config) is list:
        modules_config = {'load': modules_config}
    config['modules'] = modules_config
     
    # Local "control" path. Must be set here so it can be
    # scanned for storage points
    config["control_path"] = config.get('control',
                                        os.path.dirname(
                                            os.path.abspath(config_fname)))

    return config


def make_symlink(src_path, lnk_path):
    """Safely create a symbolic link to an input field."""

    # Check for Lustre 60-character symbolic link path bug
    if CHECK_LUSTRE_PATH_LEN:
        src_path = patch_lustre_path(src_path)
        lnk_path = patch_lustre_path(lnk_path)

    # os.symlink will happily make a symlink to a non-existent
    # file, but we don't want that behaviour
    # XXX: Do we want to be doing this?
    if not os.path.exists(src_path):
        return

    try:
        os.symlink(src_path, lnk_path)
    except EnvironmentError as exc:
        if exc.errno != errno.EEXIST:
            raise
        elif not os.path.islink(lnk_path):
            # Warn the user, but do not interrupt the job
            print("Warning: Cannot create symbolic link to {p}; a file named "
                  "{f} already exists.".format(p=src_path, f=lnk_path))
        else:
            # Overwrite any existing symbolic link
            if os.path.realpath(lnk_path) != src_path:
                os.remove(lnk_path)
                os.symlink(src_path, lnk_path)


def splitpath(path):
    """Recursively split a filepath into all directories and files."""

    head, tail = os.path.split(path)
    if tail == '':
        return head,
    elif head == '':
        return tail,
    else:
        return splitpath(head) + (tail,)


def patch_lustre_path(f_path):
    """Patch any 60-character pathnames, to avoid a current Lustre bug."""

    if CHECK_LUSTRE_PATH_LEN and len(f_path) == 60:
        if os.path.isabs(f_path):
            f_path = '/.' + f_path
        else:
            f_path = './' + f_path

    return f_path


def check_exe_path(payu_path, pbs_script):
    """Check a payu executable path is locateable """
    if not os.path.isabs(pbs_script):
        pbs_script = os.path.join(payu_path, pbs_script)

    assert os.path.isfile(pbs_script)

    return pbs_script


def is_conda():
    """Return True if python interpreter is in a conda environment"""

    return os.path.exists(os.path.join(sys.prefix, 'conda-meta'))


def parse_ldd_output(ldd_output):
    """Parses the string output from ldd and returns a dictionary of lib filename and fullpath pairs"""
    needed_libs = {}
    for line in ldd_output.split("\n"):
        word_list = line.split()
        if len(word_list) >= 3 and word_list[1] == '=>':
            needed_libs[word_list[0]] = word_list[2]
    return needed_libs


def required_libs(bin_path):
    """
    Runs ldd command and parses the output.
    This function should only be called once per binary
    i.e. Use a singleton pattern in the caller object.
    PARAMETERS:
        string bin_path: full path to the binary
    RETURN:
        dict: {filename-of-lib: fullpath-of-file}
    """
    cmd = 'ldd {0}'.format(bin_path)
    try: 
        ldd_out = subprocess.check_output(shlex.split(cmd)).decode('ascii')
    except:
        print("payu: error running ldd command on exe path: ", bin_path)
        return {}
    return parse_ldd_output(ldd_out)


def list_archive_dirs(archive_path: Union[Path, str],
                      dir_type: str = "output") -> List[str]:
    """Return a sorted list of restart or output directories in archive"""
    naming_pattern = re.compile(fr"^{dir_type}[0-9][0-9][0-9]+$")

    if isinstance(archive_path, str):
        archive_path = Path(archive_path)

    dirs = []
    for path in archive_path.iterdir():
        real_path = path.resolve()
        if real_path.is_dir() and naming_pattern.match(path.name):
            dirs.append(path.name)

    dirs.sort(key=lambda d: int(d.lstrip(dir_type)))
    return dirs
