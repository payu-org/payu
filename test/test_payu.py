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
import payu.envmod

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
    config_path = os.path.join('test', 'resources', 'config_mom5.yaml')
    config = payu.fsops.read_config(config_path)

    # Test control_path is not set in read_config
    assert('control_path' in config)
    assert(config['control_path'] == os.path.dirname(
                                         os.path.abspath(config_path)))

    # Raise a non-ENOENT error (e.g. EACCES)
    config_tmp = 'config_tmp.yaml'
    config_file = open(config_tmp, 'w')
    os.chmod(config_tmp, 0)

    with pytest.raises(IOError):
        payu.fsops.read_config(config_tmp)

    os.chmod(config_tmp, stat.S_IWUSR | stat.S_IREAD)
    config_file.close()

    config = payu.fsops.read_config(config_tmp)

    assert(config.pop('collate') == {})
    assert(config.pop('control_path') == os.getcwd())
    assert(config.pop('modules') == {})
    assert(config == {})

    os.remove(config_tmp)


def test_read_config_modules_legacy_option():
    # Test transform legacy modules option
    config_path = os.path.join('test', 'resources', 'config_legacy_modules.yaml')

    config = payu.fsops.read_config(config_path)
    modules_config = config.get('modules', {})

    assert(modules_config.get('load', []) == ['module_1', 'module_2'])
    assert(modules_config.get('use', []) == [])


def test_read_config_modules_option():
    # Test modules with load/use options is unchanged
    config_path = os.path.join('test', 'resources', 'config_modules.yaml')

    config = payu.fsops.read_config(config_path)
    modules_config = config.get('modules', {})

    assert(modules_config.get('load', []) == ['module_1', 'module_2'])
    assert(modules_config.get('use', []) == ['path/to/module/dir/1', 'path/to/module/dir/2'])


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


def test_parse_ldd_output():
    ldd_output_path = os.path.join('test', 'resources', 'sample_ldd_output.txt')
    with open(ldd_output_path, 'r') as f:
        ldd_output = f.read()
    required_libs = payu.fsops.parse_ldd_output(ldd_output)
    assert(len(required_libs) == 4)
    assert(required_libs['libmpi.so.40'] == '/apps/openmpi/4.0.2/lib/libmpi.so.40')


def test_lib_update_lib_if_required():
    required_libs_dict = {
        'libmpi.so.40': '/apps/openmpi/4.0.2/lib/libmpi.so.40',
        'libmpi_usempif08_Intel.so.40': '/apps/openmpi/4.0.2/lib/libmpi_usempif08_Intel.so.40'
    }
    result = payu.envmod.lib_update(required_libs_dict, 'libmpi.so')
    assert(result == 'openmpi/4.0.2')


def test_lib_update_if_nci_module_not_required():
    required_libs_dict = {
         'libmpi.so.40': '/$HOME/spack-microarchitectures.git/opt/spack/linux-rocky8-cascadelake/intel-2019.5.281/openmpi-4.1.5-ooyg5wc7sa3tvmcpazqqb44pzip3wbyo/lib/libmpi.so.40', 
         'libmpi_usempif08.so.40': '/$HOME/exe/spack-microarchitectures.git/opt/spack/linux-rocky8-cascadelake/intel-2019.5.281/openmpi-4.1.5-ooyg5wc7sa3tvmcpazqqb44pzip3wbyo/lib/libmpi_usempif08.so.40',
    }
    result = payu.envmod.lib_update(required_libs_dict, 'libmpi.so')
    assert (result == '')


def test_list_archive_dirs():
    # Create archive directories - mix of valid/invalid names
    archive_dirs = [
        'output000', 'output1001', 'output023',
        'output', 'Output001', 'output1',
        'Restart', 'restart2', 'restart',
        'restart102932', 'restart021', 'restart001',
    ]
    tmp_archive = tmpdir / 'test_archive'
    for dir in archive_dirs:
        (tmp_archive / dir).mkdir(parents=True)

    # Add some files
    (tmp_archive / 'restart005').touch()
    (tmp_archive / 'output005').touch()

    # Add a restart symlink
    tmp_archive_2 = tmpdir / 'test_archive_2'
    source_path = tmp_archive_2 / 'restart999'
    source_path.mkdir(parents=True)
    (tmp_archive / 'restart23042').symlink_to(source_path)

    # Test list output dirs and with string archive path
    outputs = payu.fsops.list_archive_dirs(str(tmp_archive), dir_type="output")
    assert outputs == ['output000', 'output023', 'output1001']

    # Test list restarts
    restarts = payu.fsops.list_archive_dirs(tmp_archive, dir_type="restart")
    assert restarts == ['restart001', 'restart021',
                        'restart23042', 'restart102932']

    # Clean up test archive
    shutil.rmtree(tmp_archive)
    shutil.rmtree(tmp_archive_2)
