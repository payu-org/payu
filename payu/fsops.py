"""payu.experiment
   ===============

   Basic file system operations for Payu

   :copyright: Copyright 2011 Marshall Ward, see AUTHORS for details.
   :license: Apache License, Version 2.0, see LICENSE for details.
"""

# Standard library
import errno
import os
import shlex
import subprocess
import sys

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


def get_commit_id(filepath):
    """
    Return git commit hash for filepath
    """
    cmd = shlex.split("git log -n 1 --pretty=format:%H -- ")
    cmd.append(filepath)
    try:
        with open(os.devnull, 'w') as devnull:
            hash = subprocess.check_output(cmd, stderr=devnull)
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
        with open(os.devnull, 'w') as devnull:
            hash = subprocess.check_output(['git', 'rev-parse', 'HEAD'], stderr=devnull)
        if sys.version_info.major==3:
          hash.decode('ascii')
        return hash.strip() 
    except subprocess.CalledProcessError:
        return None

def is_ancestor(id1, id2):
    """
    Return True if git commit id1 is a ancestor of git commit id2
    """
    try:
        with open(os.devnull, 'w') as devnull:
            revs = subprocess.check_output(['git', 'rev-list', id2], stderr=devnull)
    except:
        return None
    else:
        return id1 in revs

def get_job_info():
    """
    Get information about the job from the PBS server
    """

    jobid = os.environ.get('PBS_JOBID',None)

    if jobid is None:
        return None
    
    # Strip off '.rman2'
    jobid = jobid.split('.')[0]

    info = get_qstat_info('-ft {0}'.format(jobid),'Job Id:')

    # Select the dict for this job (there should only be one entry in any case) 
    info = info['Job Id: {}'.format(jobid)]

    # Grab the environment variables from the job, add them to the dict and then
    # delete that entry
    for var in info['Variable_List'].split(','):
        k,v = var.split('=')
        info[k] = v 
    del(info['Variable_List'])

    return(info)

def dump_yaml(info, fname):
    with open(fname, 'w') as file:
        file.write(yaml.dump(info,default_flow_style=False))

def pbs_env_init():

    # Initialise against PBS_CONF_FILE
    if sys.platform == 'win32':
        pbs_conf_fpath = 'C:\Program Files\PBS Pro\pbs.conf'
    else:
        pbs_conf_fpath = '/etc/pbs.conf'
    os.environ['PBS_CONF_FILE'] = pbs_conf_fpath

    try:
        with open(pbs_conf_fpath) as pbs_conf:
            for line in pbs_conf:
                try:
                    key, value = line.split('=')
                    os.environ[key] = value.rstrip()
                except ValueError:
                    pass
    except IOError as ec:
        print('Unable to find PBS_CONF_FILE ... ' + pbs_conf_fpath)
        sys.exit(1)

def get_qstat_info(qflag, header, projects=None, users=None):

    qstat = os.path.join(os.environ['PBS_EXEC'], 'bin', 'qstat')
    cmd = '{} {}'.format(qstat, qflag)

    cmd = shlex.split(cmd)
    output = subprocess.check_output(cmd).decode().encode()

    entries = (e for e in output.split('{}: '.format(header)) if e)

    # Immediately remove any non-project entries
    if projects or users:
        entries = (e for e in entries
                   if any('project = {}'.format(p) in e for p in projects)
                   or any('Job_Owner = {}'.format(u) in e for u in users))

    attribs = ((k.split('.')[0], v.replace('\n\t', '').split('\n'))
                for k, v in (e.split('\n', 1) for e in entries))

    status = {k: dict((kk.strip(), vv.strip())
                        for kk, vv in (att.split('=', 1) for att in v if att))
                        for k, v in attribs}

    return status
