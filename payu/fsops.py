# coding: utf-8
"""payu.experiment
   ===============

   Basic file system operations for Payu

   :copyright: Copyright 2011 Marshall Ward, see AUTHORS for details.
   :license: Apache License, Version 2.0, see LICENSE for details.
"""

# Standard library
import errno
import sys, os
import subprocess
import shlex

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


def read_config(config_fname=None):
    """Parse input configuration file and return a config dict."""

    if not config_fname:
        config_fname = DEFAULT_CONFIG_FNAME

    try:
        with open(config_fname, 'r') as config_file:
            config = yaml.load(config_file)
    except IOError as exc:
        if exc.errno == errno.ENOENT:
            print('payu: warning: Configuration file {0} not found!'
                  .format(config_fname))
            config = {}
        else:
            raise
    else:
        # Store the git commit id for later use
        config['_git_commit_id'] = get_commit_id(config_fname)
  
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

    return config


def make_symlink(src_path, lnk_path):
    """Safely create a symbolic link to an input field."""

    # Check for Lustre 60-character symbolic link path bug
    if CHECK_LUSTRE_PATH_LEN:
        src_path = patch_lustre_path(src_path)
        lnk_path = patch_lustre_path(lnk_path)

    # os.symlink will happily make a symlink to a non-existent
    # file, but we don't want that behaviour
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


def get_commit_id(filepath):
    """
    Return git commit hash for filepath
    """
    cmd = shlex.split("git log -n 1 --pretty=format:%H -- ")
    cmd.append(filepath)
    try:
        hash = subprocess.check_output(cmd)
        if sys.version_info.major==3:
          hash.decode('ascii')
        return hash.strip() 
    except subprocess.CalledProcessError:
        return None

def get_git_revision_hash(short=False):
    """
    Return git commit hash for repository
    """
    cmd = ['git', 'rev-parse', 'HEAD']
    if short:
        cmd.insert(-1,'--short')

    try:
        hash = subprocess.check_output(['git', 'rev-parse', 'HEAD'])
        if sys.version_info.major==3:
          hash.decode('ascii')
        return hash.strip() 
    except subprocess.CalledProcessError:
        return None

def is_ancestor(id1, id2):
    """
    Return True if git commit id1 is a ancestor of git commit id2
    """
    revs = subprocess.check_output(['git', 'rev-list', id2])
    return id1 in revs