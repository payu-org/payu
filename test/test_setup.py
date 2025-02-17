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
from .common import make_exe, make_inputs

# Config files in the test model driver
CONFIG_FILES = ['data', 'diag', 'input.nml']
OPTIONAL_CONFIG_FILES = ['opt_data']
INPUT_NML_FILENAME = 'input.nml'


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


def make_config_files():
    """
    Create files required for test model
    """
    for file in CONFIG_FILES:
        make_random_file(ctrldir/file, 29)


def run_payu_setup(config=config_orig, create_inputs=False,
                   create_config_files=True):
    """Helper function to write config.yaml files, make inputs,
    config files and run experiment setup"""
    # Setup files
    write_config(config)
    make_exe()
    if create_inputs:
        make_inputs()
    if create_config_files:
        make_config_files()

    # Initialise a payu laboratory
    with cd(ctrldir):
        payu_init(None, None, str(labdir))

    # Run payu setup
    payu_setup(lab_path=str(labdir))


def test_setup_configuration_files():
    """Test model config_files are copied to work directory,
    and that any symlinks are followed"""
    # Create configuration files
    all_config_files = CONFIG_FILES + OPTIONAL_CONFIG_FILES
    for file in all_config_files:
        if file != INPUT_NML_FILENAME:
            make_random_file(ctrldir / file, 8)

    # For input.nml, create a file symlink in control directory
    input_nml_realpath = tmpdir / INPUT_NML_FILENAME
    input_nml_symlink = ctrldir / INPUT_NML_FILENAME
    make_random_file(input_nml_realpath, 8)
    input_nml_symlink.symlink_to(input_nml_realpath)
    assert input_nml_symlink.is_symlink()

    # Run payu setup
    run_payu_setup(create_inputs=True)

    # Check config files have been copied to work path
    for file in all_config_files + ['config.yaml']:
        filepath = workdir / file
        assert filepath.exists() and filepath.is_file()
        assert not filepath.is_symlink()
        assert filepath.read_bytes() == (ctrldir / file).read_bytes()


@pytest.mark.parametrize(
    "input_path, is_symlink, is_absolute",
    [
        (labdir / 'input' / 'lab_inputs', False, False),
        (ctrldir / 'ctrl_inputs', False, False),
        (tmpdir / 'symlinked_inputs', True, False),
        (tmpdir / 'tmp_inputs', False, True)
    ]
)
def test_setup_inputs(input_path, is_symlink, is_absolute):
    """Test inputs are symlinked to work directory,
    and added in input manifest"""
    # Make inputs
    input_path.mkdir(parents=True, exist_ok=True)
    for i in range(1, 4):
        make_random_file(input_path / f'input_00{i}.bin', 1000**2 + i)

    if is_symlink:
        # Create an input symlink in control directory
        (ctrldir / input_path.name).symlink_to(input_path)

    # Modify config to specify input path
    config = copy.deepcopy(config_orig)
    config['input'] = str(input_path) if is_absolute else input_path.name

    # Run payu setup
    run_payu_setup(config=config, create_config_files=True)

    input_manifest = get_manifests(ctrldir/'manifests')['input.yaml']
    for i in range(1, 4):
        filename = f'input_00{i}.bin'
        work_input = workdir / filename

        # Check file exists and file size is expected
        assert work_input.exists() and work_input.is_symlink()
        assert work_input.stat().st_size == 1000**2 + i

        # Check relative input path is added to manifest
        filepath = str(Path('work') / filename)
        assert filepath in input_manifest

        # Check manifest fullpath
        manifest_fullpath = input_manifest[filepath]['fullpath']
        assert manifest_fullpath == str(input_path / filename)

        # Check fullpath is a resolved path
        assert Path(manifest_fullpath).is_absolute()
        assert not Path(manifest_fullpath).is_symlink()


def test_setup():
    """Test work directory and executable are setup as expected,
    and re-running setup requires a force=True"""
    run_payu_setup(create_inputs=True, create_config_files=True)

    assert workdir.is_symlink and workdir.is_dir()

    # Check executable symlink is in work directory
    bin_exe = labdir / 'bin' / config_orig['exe']
    work_exe = workdir / config_orig['exe']
    assert work_exe.exists() and work_exe.is_symlink()
    assert work_exe.resolve() == bin_exe.resolve()

    # Re-run setup - expect an error
    with pytest.raises(SystemExit,
                       match="work path already exists") as setup_error:
        payu_setup(lab_path=str(labdir), sweep=False, force=False)
    assert setup_error.type == SystemExit

    assert workdir.is_symlink and workdir.is_dir()


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



# model.expt.runlog.enabled is used in code for writing runlog
# it can be set as runlog:true or runlog:enable:true in config.yaml
@pytest.mark.parametrize(
        "runlog, enabled", 
        [   
            (None, True), #default is True
            (True, True), 
            (False, False), 
            ({"enable":True}, True),
            ({"enable":False}, False)
         ]
)
@pytest.mark.filterwarnings("error")
def test_runlog_enable(runlog, enabled):
    config = copy.deepcopy(config_orig)
    if runlog == None:
        config.pop('runlog') #remove from config for default case
    else:
        config['runlog'] = runlog

    write_config(config)

    make_inputs()

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)
        model = expt.models[0]

    assert model.expt.runlog.enabled == enabled