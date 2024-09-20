import copy
from pathlib import Path
import pytest
import shutil
from unittest.mock import patch

import payu

from .common import cd, make_random_file, get_manifests
from .common import tmpdir, ctrldir, labdir, workdir
from .common import payu_init, payu_setup
from .common import config as config_orig
from .common import write_config
from .common import make_exe

# Config files in the test model driver
CONFIG_FILES = ['data', 'diag', 'input.nml']
INPUT_NML_FILENAME = 'input.nml'

# INPUT PATHS
INPUT_TO_PATHS = {
    # Inputs in lab directory
    "lab_inputs": labdir / 'input' / 'lab_inputs',
    # Inputs in control directory
    "ctrl_inputs": ctrldir / 'ctrl_inputs',
    # Inputs in tmp directory - that will be symlinked to control directory
    "tmp_inputs": tmpdir / 'tmp_inputs'
}


@pytest.fixture(autouse=True)
def setup_and_teardown():
    # Create tmp, lab and control directories
    try:
        tmpdir.mkdir()
        labdir.mkdir()
        ctrldir.mkdir()
    except Exception as e:
        print(e)

    yield

    # Remove tmp directory
    try:
        shutil.rmtree(tmpdir)
    except Exception as e:
        print(e)


def test_init():
    write_config(config_orig)

    # Initialise a payu laboratory
    with cd(ctrldir):
        payu_init(None, None, str(labdir))

    # Check all the correct directories have been created
    for subdir in ['bin', 'input', 'archive', 'codebase']:
        assert((labdir / subdir).is_dir())


def create_configuration_files():
    """Create model config files in control directory"""
    for file in CONFIG_FILES:
        if file != INPUT_NML_FILENAME:
            make_random_file(ctrldir / file, 8)

    # For input.nml, create a file symlink in control directory
    input_nml_realpath = tmpdir / INPUT_NML_FILENAME
    input_nml_symlink = ctrldir / INPUT_NML_FILENAME
    make_random_file(input_nml_realpath, 8)
    input_nml_symlink.symlink_to(input_nml_realpath)
    assert input_nml_symlink.is_symlink()


def check_configuration_files():
    """Test model config_files are copied to work directory,
    and that any symlinks are followed"""
    for file in CONFIG_FILES + ['config.yaml']:
        filepath = workdir / file
        # Check file has been copied to work path
        assert filepath.exists() and filepath.is_file()

        # Check file is not a symlink
        assert not filepath.is_symlink()

        # Check file contents are copied
        assert filepath.read_bytes() == (ctrldir / file).read_bytes()


def create_inputs():
    """Create inputs in laboratory, control and a temporary
    directory - that are symlinked to the control directory"""
    # Make inputs
    for inputs, path in INPUT_TO_PATHS.items():
        path.mkdir(parents=True, exist_ok=True)
        for i in range(1, 4):
            make_random_file(path / f'{inputs}_input_00{i}.bin',
                            1000**2 + i)

    # Create symlink in work directory
    (ctrldir / 'tmp_inputs').symlink_to(INPUT_TO_PATHS['tmp_inputs'])


def check_inputs():
    """Check inputs are symlinked to work directory,
    and added in input manifest
    """
    input_manifest = get_manifests(ctrldir/'manifests')['input.yaml']
    for inputs, path in INPUT_TO_PATHS.items():
        for i in range(1, 4):
            filename = f'{inputs}_input_00{i}.bin'
            work_input = workdir / filename

            # Check file exists and file size is expected
            assert work_input.exists() and work_input.is_symlink()
            assert work_input.stat().st_size == 1000**2 + i

            # Check relative input path is added to manifest
            filepath = str(Path('work') / filename)
            assert filepath in input_manifest

            # Check manifest fullpath
            expected_fullpath = path / filename
            manifest_fullpath_str = input_manifest[filepath]['fullpath']
            assert manifest_fullpath_str == str(expected_fullpath)

            # Check fullpath is a resolved path
            manifest_fullpath = Path(manifest_fullpath_str)
            assert manifest_fullpath.is_absolute()
            assert not manifest_fullpath.is_symlink()


def check_exe(exe_name):
    """Test executable has been added to work directory"""
    bin_exe = labdir / 'bin' / exe_name
    work_exe = workdir / exe_name
    assert work_exe.exists() and work_exe.is_symlink()
    assert work_exe.resolve() == bin_exe.resolve()


def check_workdir(config):
    """Test work directory is setup as expected"""
    assert workdir.is_symlink and workdir.is_dir()

    # Check configuration files, inputs and executables are moved to work dir
    check_configuration_files()
    check_inputs()
    check_exe(config['exe'])


def test_setup():
    """Test work directory is setup as expected, e.g. configuratiom files are
    copied across, and inputs and executables are symlinked"""
    config = copy.deepcopy(config_orig)

    # Create test configuration files, excutables, and inputs
    create_configuration_files()
    create_inputs()
    make_exe()

    # Over-ride input in default configuration
    config['input'] = [input for input in INPUT_TO_PATHS]
    write_config(config)

    # Initialise a payu laboratory
    with cd(ctrldir):
        payu_init(None, None, str(labdir))

    # Run setup
    payu_setup(lab_path=str(labdir))

    # Check files in work directory are setup as expected
    check_workdir(config)

    # Re-run setup - expect an error
    with pytest.raises(SystemExit,
                       match="work path already exists") as setup_error:
        payu_setup(lab_path=str(labdir), sweep=False, force=False)
    assert setup_error.type == SystemExit

    # Re-run payu setup with force=True
    payu_setup(lab_path=str(labdir), sweep=False, force=True)

    # Check files in work directory are setup as expected
    check_workdir(config)


@pytest.mark.parametrize(
    "current_version, min_version",
    [
        ("2.0.0", "1.0.0"),
        ("v0.11.2", "v0.11.1"),
        ("1.0.0", "1.0.0"),
        ("1.0.0+4.gabc1234", "1.0.0"),
        ("1.0.0+0.gxyz987.dirty", "1.0.0"),
        ("1.1.5", 1.1)
    ]
)
def test_check_payu_version_pass(current_version, min_version):
    # Mock the payu version
    with patch('payu.__version__', current_version):
        # Avoid running Experiment init method
        with patch.object(payu.experiment.Experiment, '__init__',
                          lambda x: None):
            expt = payu.experiment.Experiment()

            # Mock config.yaml
            expt.config = {
                "payu_minimum_version": min_version
            }
            expt.check_payu_version()


@pytest.mark.parametrize(
    "current_version, min_version",
    [
        ("1.0.0", "2.0.0"),
        ("v0.11", "v0.11.1"),
        ("1.0.0+4.gabc1234", "1.0.1"),
        ("1.0.0+0.gxyz987.dirty", "v1.2"),
    ]
)
def test_check_payu_version_fail(current_version, min_version):
    with patch('payu.__version__', current_version):
        with patch.object(payu.experiment.Experiment, '__init__',
                          lambda x: None):
            expt = payu.experiment.Experiment()

            expt.config = {
                "payu_minimum_version": min_version
            }

            with pytest.raises(RuntimeError):
                expt.check_payu_version()


@pytest.mark.parametrize(
    "current_version", ["1.0.0", "1.0.0+4.gabc1234"]
)
def test_check_payu_version_pass_with_no_minimum_version(current_version):
    with patch('payu.__version__', current_version):
        with patch.object(payu.experiment.Experiment, '__init__',
                          lambda x: None):
            expt = payu.experiment.Experiment()

            # Leave version out of config.yaml
            expt.config = {}

            # Check runs without an error
            expt.check_payu_version()


@pytest.mark.parametrize(
    "minimum_version", ["abcdefg", None]
)
def test_check_payu_version_configured_invalid_version(minimum_version):
    with patch('payu.__version__', "1.0.0"):
        with patch.object(payu.experiment.Experiment, '__init__',
                          lambda x: None):
            expt = payu.experiment.Experiment()

            expt.config = {
                "payu_minimum_version": minimum_version
            }

            with pytest.raises(ValueError):
                expt.check_payu_version()
