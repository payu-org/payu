import os
import shutil

import pytest
import f90nml

import payu

from test.common import cd
from test.common import tmpdir, ctrldir, labdir, expt_workdir
from test.common import workdir, expt_archive_dir, ctrldir_basename
from test.common import write_config, config_path, write_metadata
from test.common import make_exe

verbose = True

DEFAULT_CICE_NML = {
    "setup_nml": {
        "history_dir": "./HISTORY/",
        "restart_dir": "./RESTART/",
        "year_init": 9999,
        "days_per_year": 360,
        "ice_ic": "default",
        "restart": False,
        "pointer_file": "./RESTART/ice.restart_file",
        "runtype": "initial",
        "npt": 99999,
        "dt": 1,
    },
    "grid_nml": {"grid_file": "./INPUT/grid.nc", "kmt_file": "./INPUT/kmt.nc"},
    "icefields_nml": {"f_icy": "x"},
}
CICE_NML_NAMES = ["cice_in.nml", "input_ice.nml",
                  "input_ice_gfdl.nml", "input_ice_monin.nml"]
ICED_RESTART_NAME = "iced.18510101"
RESTART_POINTER_NAME = "ice.restart_file"

DEFAULT_CONFIG = {
    "laboratory": "lab",
    "jobname": "testrun",
    "model": "cice5",
    "exe": "test.exe",
    "experiment": ctrldir_basename,
    "metadata": {"enable": False}
}
RESTART_PATH = expt_archive_dir / "restartXYZ"

CONFIG_WITH_RESTART = {
    "laboratory": "lab",
    "jobname": "testrun",
    "model": "cice5",
    "exe": "test.exe",
    "experiment": ctrldir_basename,
    "metadata": {"enable": False},
    "restart": str(RESTART_PATH)
}


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
        expt_archive_dir.mkdir(parents=True)
        make_exe()
        write_metadata()
    except Exception as e:
        print(e)


@pytest.fixture
def config(request):
    """
    Write a specified dictionary to config.yaml.
    Used to allow writing configs with and without
    restarts.
    """
    config = request.param
    write_config(config, config_path)

    yield config_path

    os.remove(config_path)


def teardown_module(module):
    """
    Put any test-wide teardown code in here, e.g. removing test outputs
    """
    if verbose:
        print("teardown_module   module:%s" % module.__name__)

    try:
        shutil.rmtree(tmpdir)
        print("removing tmp")
    except Exception as e:
        print(e)


@pytest.fixture(autouse=True)
def empty_workdir():
    """
    Model setup tests require a clean work directory and symlink from
    the control directory.
    """
    expt_workdir.mkdir(parents=True)
    # Symlink must exist for setup to use correct locations
    workdir.symlink_to(expt_workdir)

    yield expt_workdir
    shutil.rmtree(expt_workdir)
    workdir.unlink()


@pytest.fixture
def cice_config_files():
    cice_nml = DEFAULT_CICE_NML

    with cd(ctrldir):
        # 2. Create config.nml
        f90nml.write(cice_nml, CICE_NML_NAMES[0])
        for name in CICE_NML_NAMES[1:]:
            with open(name, "w") as f:
                f.close()

    yield

    with cd(ctrldir):
        for name in CICE_NML_NAMES:
            os.remove(name)


@pytest.mark.parametrize("config", [DEFAULT_CONFIG],
                         indirect=True)
def test_setup(config, cice_config_files):
    """
    # Confirm that payu setup works
    """
    with cd(ctrldir):

        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)
        model = expt.models[0]

        # Function to test
        model.setup()

    # Check config files are moved to model's work path
    work_path_files = os.listdir(model.work_path)
    for name in CICE_NML_NAMES:
        assert name in work_path_files

    # Check cice_in was not patched with ice_history
    work_input_fpath = os.path.join(model.work_path, CICE_NML_NAMES[0])
    input_nml = f90nml.read(work_input_fpath)
    assert input_nml["icefields_nml"] == DEFAULT_CICE_NML["icefields_nml"]

    # Check dump_last
    assert input_nml["setup_nml"]["dump_last"] is True


@pytest.fixture
def prior_restart_dir_cice5():
    """
    Create fake prior restart files required by CICE5's setup.
    """
    prior_restart_path = RESTART_PATH
    os.mkdir(prior_restart_path)

    # Restart files required by CICE5 setup
    (prior_restart_path/ICED_RESTART_NAME).touch()
    (prior_restart_path/RESTART_POINTER_NAME).touch()

    yield prior_restart_path

    # Teardown
    shutil.rmtree(prior_restart_path)


@pytest.mark.parametrize("config", [CONFIG_WITH_RESTART],
                         indirect=True)
def test_restart_setup(config, cice_config_files, prior_restart_dir_cice5):
    """
    Test that seting up an experiment from a cloned control directory
    works when a restart directory is specified.

    Use a restart directory mimicking the CICE5 files required by setup.
    """

    # Setup experiment
    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)
        model = expt.models[0]

        # Function to test
        model.setup()

    # Check restart files were copied to work directory.
    cice_work_restart_files = os.listdir(model.work_restart_path)

    for file in [ICED_RESTART_NAME, RESTART_POINTER_NAME]:
        assert file in cice_work_restart_files
