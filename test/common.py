from contextlib import contextmanager
import os
from pathlib import Path

import yaml


@contextmanager
def cd(directory):
    """
    Context manager to change into a directory and
    change back to original directory when complete
    """
    old_dir = Path.cwd()
    os.chdir(directory)
    try:
        yield
    finally:
        os.chdir(old_dir)


def make_random_file(filename, size=1000**2):
    """
    Make a file of specified size filled with some
    random content
    """
    with open(filename, 'wb') as fout:
        fout.write(os.urandom(size))


def get_manifests(mfdir):
    """
    Read in all manifests and return as a dict
    """
    manifests = {}
    for mf in ['exe', 'input', 'restart']:
        mfpath = Path(mfdir)/"{}.yaml".format(mf)
        with mfpath.open() as fh:
            manifests[mfpath.name] = list(yaml.safe_load_all(fh))[1]
    return manifests
