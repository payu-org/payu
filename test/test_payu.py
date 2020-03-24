from io import StringIO
import os
from pathlib import Path
import pytest
import shutil
import stat
import sys

# Submodules
import payu
import payu.fsops
import payu.laboratory

from .common import testdir, tmpdir, ctrldir, labdir, workdir
from .common import make_exe, make_inputs, make_restarts, make_all_files


sys.path.insert(1, '../')
verbose = False

tmptwo = testdir / 'tmp2'


def setup_module(module):
    """
    Put any test-wide setup code in here, e.g. creating test files
    """
    if verbose:
        print("setup_module      module:%s" % module.__name__)

    # Should be taken care of by teardown, in case remnants lying around
    try:
        shutil.rmtree(tmpdir)
    except FileNotFoundError:
        pass

    try:
        tmpdir.mkdir()
        labdir.mkdir()
        ctrldir.mkdir()
    except Exception as e:
        print(e)


def teardown_module(module):
    """
    Put any test-wide teardown code in here, e.g. removing test outputs
    """
    if verbose:
        print("teardown_module   module:%s" % module.__name__)

    try:
        shutil.rmtree(tmpdir)
        print('removing tmp')
        shutil.rmtree(tmptwo)
        print('removing tmp2')
    except Exception as e:
        print(e)


def scantree(path):
    """
    Recursively yield DirEntry objects for given directory.
    https://stackoverflow.com/a/33135143/4727812
    """
    for entry in os.scandir(path):
        if entry.is_dir(follow_symlinks=False):
            yield from scantree(entry.path)
        else:
            yield entry


def savetree(path):
    """
    Save a directory tree to a dict
    """
    result = {}
    for entry in scantree(path):
        result[entry.name] = (Path(entry.path).relative_to(path),
                              entry.stat().st_size)
    return(result)


# fsops tests
def test_mkdir_p():
    tmp_dir = os.path.join(os.getcwd(), 'tmp_dir')
    payu.fsops.mkdir_p(tmp_dir)

    # Re-create existing directory
    payu.fsops.mkdir_p(tmp_dir)

    # Raise a non-EEXIST error (e.g. EACCES)
    tmp_tmp_dir = os.path.join(tmp_dir, 'more_tmp')
    os.chmod(tmp_dir, stat.S_IRUSR)
    with pytest.raises(OSError):
        payu.fsops.mkdir_p(tmp_tmp_dir)

    # Cleanup
    os.chmod(tmp_dir, stat.S_IWUSR)
    os.rmdir(tmp_dir)


def test_movetree():

    make_all_files()

    treeinfo = savetree(tmpdir)

    tmp_inode = tmpdir.stat().st_ino

    payu.fsops.movetree(tmpdir, tmptwo)

    # Ensure src directory removed
    assert(not tmpdir.exists())

    # Ensure dst directory has new inode number
    assert(tmp_inode != tmptwo.stat().st_ino)

    # Ensure directory tree faithfully moved
    assert(treeinfo == savetree(tmptwo))

    # Move tmp2 back to tmp
    shutil.move(tmptwo, tmpdir)


def test_read_config():
    config_path = os.path.join('test', 'config_mom5.yaml')
    config = payu.fsops.read_config(config_path)

    # Raise a non-ENOENT error (e.g. EACCES)
    config_tmp = 'config_tmp.yaml'
    config_file = open(config_tmp, 'w')
    os.chmod(config_tmp, 0)

    with pytest.raises(IOError):
        payu.fsops.read_config(config_tmp)

    os.chmod(config_tmp, stat.S_IWUSR)
    config_file.close()
    os.remove(config_tmp)


def test_make_symlink():
    tmp_path = 'tmp_file'
    tmp_sym = 'tmp_sym'
    tmp_alt_path = 'tmp_alt'
    tmp_dir = 'tmp_dir'

    # Simple symlink test
    tmp = open(tmp_path, 'w')
    payu.fsops.make_symlink(tmp_path, tmp_sym)

    # Override an existing symlink
    tmp_alt = open(tmp_alt_path, 'w')
    payu.fsops.make_symlink(tmp_alt_path, tmp_sym)

    # Try to create symlink when filename already exists
    # TODO: validate stdout
    sys.stdout = StringIO()
    payu.fsops.make_symlink(tmp_path, tmp_alt_path)
    sys.stdout = sys.__stdout__

    # Raise a non-EEXIST signal (EACCESS)
    tmp_dir_sym = os.path.join(tmp_dir, tmp_sym)
    os.mkdir(tmp_dir)
    os.chmod(tmp_dir, 0)
    with pytest.raises(OSError):
        payu.fsops.make_symlink(tmp_path, tmp_dir_sym)

    # Cleanup
    tmp.close()
    tmp_alt.close()

    os.rmdir(tmp_dir)
    os.remove(tmp_sym)
    os.remove(tmp_path)
    os.remove(tmp_alt_path)


def test_splitpath():

    # Absolute path
    paths = payu.fsops.splitpath('/a/b/c')
    assert(paths == ('/', 'a', 'b', 'c'))

    # Relative path
    paths = payu.fsops.splitpath('a/b/c')
    assert(paths == ('a', 'b', 'c'))

    # Single local path
    paths = payu.fsops.splitpath('a')
    assert(paths == ('a',))


def test_default_lab_path():
    # TODO
    pass


def test_lab_new():
    # TODO: validate stdout
    sys.stdout = StringIO()
    lab = payu.laboratory.Laboratory('model')
    sys.stdout = sys.__stdout__
