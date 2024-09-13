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

DEFAULT_YEAR_INIT = 101  # arbitrary value for tests
DEFAULT_DT = 3600  # 1 hour
DEFAULT_CICE_NML = {
    "setup_nml": {
        "history_dir": "./HISTORY/",
        "restart_dir": "./RESTART/",
        "year_init": DEFAULT_YEAR_INIT,
        "days_per_year": 365,
        "ice_ic": "default",
        "restart": False,
        "pointer_file": "./RESTART/ice.restart_file",
        "runtype": "initial",
        "npt": 99999,
        "dt": DEFAULT_DT,
    },
    "grid_nml": {"grid_file": "./INPUT/grid.nc", "kmt_file": "./INPUT/kmt.nc"},
    "icefields_nml": {"f_icy": "x"},
}
CICE_NML_NAME = "cice_in.nml"
HIST_NML_NAME = "ice_history.nml"
RESTART_NAME = "./RESTART/iced.r"
ICED_RESTART_NAME = "iced.18510101"
RESTART_POINTER_NAME = "ice.restart_file"


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


DEFAULT_CONFIG = {
    "laboratory": "lab",
    "jobname": "testrun",
    "model": "cice",
    "exe": "test.exe",
    "experiment": ctrldir_basename,
    "metadata": {"enable": False}
}
RESTART_PATH = expt_archive_dir / "restartXYZ"

CONFIG_WITH_RESTART = {
    "laboratory": "lab",
    "jobname": "testrun",
    "model": "cice",
    "exe": "test.exe",
    "experiment": ctrldir_basename,
    "metadata": {"enable": False},
    "restart": str(RESTART_PATH)
}


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


# Important to test None case without separate ice history file
@pytest.fixture(params=[None,
                        {"icefields_nml": {"f_icy": "m"}},
                        {"icefields_nml": {"f_icy": "m", "f_new": "y"}}])
def cice_config_files(request):
    """
    Write the default cice_in.nml namelist, and if included, separate ice
    history namelist used by ESM1.5. Important to also test OM2/CICE5 case
    without separate ice history namelist.
    """
    cice_nml = DEFAULT_CICE_NML
    ice_history = request.param

    with cd(ctrldir):
        # 2. Create config.nml
        f90nml.write(cice_nml, CICE_NML_NAME)

        if ice_history:
            f90nml.write(ice_history, HIST_NML_NAME)

    yield {'ice_history': ice_history}

    # cleanup
    with cd(ctrldir):
        os.remove(CICE_NML_NAME)
        if ice_history:
            os.remove(HIST_NML_NAME)


@pytest.mark.parametrize("config", [DEFAULT_CONFIG],
                         indirect=True)
def test_setup(config, cice_config_files):
    """
    Confirm that
        1: payu overwrites cice_in with ice_history
        2: payu works without ice_history.nml
        3: payu overwrites cice_in and allows additional fields
    In all cases confirm dump_last is not added to model_type='cice'
    """

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)
        model = expt.models[0]

        # Function to test
        model.setup()

    # Check config files are moved to model's work path
    work_path_files = os.listdir(model.work_path)
    assert CICE_NML_NAME in work_path_files
    assert HIST_NML_NAME not in work_path_files

    # Check cice_in was patched with ice_history
    work_input_fpath = os.path.join(model.work_path, CICE_NML_NAME)
    input_nml = f90nml.read(work_input_fpath)
    if cice_config_files['ice_history']:
        assert (input_nml["icefields_nml"] ==
                cice_config_files["ice_history"]["icefields_nml"])
    else:
        assert input_nml["icefields_nml"] == DEFAULT_CICE_NML["icefields_nml"]

    # Check dump_last doesn't exist
    with pytest.raises(KeyError, match="dump_last"):
        input_nml["setup_nml"]["dump_last"]


PREVIOUS_ISTEP0 = 0
PREVIOUS_NPT = 8760  # 1 year of 1hr timesteps


@pytest.fixture
def prior_restart_dir_cice4():
    """
    Create fake prior restart files required by CICE4's setup.
    This differs from CICE5, which doesn't require a cice_in.nml
    file in the restart directory.
    """
    prior_restart_path = RESTART_PATH
    os.mkdir(prior_restart_path)

    # Previous cice_in namelist with time information
    restart_cice_in = {"setup_nml": {
            "istep0": PREVIOUS_ISTEP0,
            "npt": PREVIOUS_NPT,
            "dt": DEFAULT_DT
        }}
    f90nml.write(restart_cice_in, prior_restart_path/CICE_NML_NAME)

    # Additional restart files required by CICE4 setup
    (prior_restart_path/ICED_RESTART_NAME).touch()
    (prior_restart_path/RESTART_POINTER_NAME).touch()

    yield prior_restart_path

    # Teardown
    shutil.rmtree(prior_restart_path)


@pytest.mark.parametrize("config", [CONFIG_WITH_RESTART],
                         indirect=True)
def test_restart_setup(config, cice_config_files, prior_restart_dir_cice4):
    """
    Test that seting up an experiment from a cloned control directory
    works when a restart directory is specified.

    Use a restart directory mimicking the CICE4 files required by setup.
    """

    # Setup experiment
    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)

        # Add a runtime to test calculated cice runtime values
        expt.runtime = {"years": 0,
                        "months": 0,
                        "days": 2}
        model = expt.models[0]

        # Function to test
        model.setup()

    # Check correct run time values written to work namelist
    work_cice_nml = f90nml.read(
        os.path.join(model.work_path, CICE_NML_NAME)
        )
    assert work_cice_nml["setup_nml"]["istep0"] == (
        PREVIOUS_ISTEP0 + PREVIOUS_NPT
    )
    assert work_cice_nml["setup_nml"]["npt"] == (
        48
    )

    # Check restart files were copied to work directory.
    cice_work_restart_files = os.listdir(model.work_restart_path)

    for file in [CICE_NML_NAME, ICED_RESTART_NAME, RESTART_POINTER_NAME]:
        assert file in cice_work_restart_files


@pytest.mark.parametrize("config", [DEFAULT_CONFIG],
                         indirect=True)
def test_no_restart_ptr(config, cice_config_files):
    """
    Test that payu raises an error if no prior restart path is specified,
    restart is `true` in cice_in.nml, and the restart pointer is missing.
    """
    cice_in_patch = {"setup_nml": {"restart": True}}
    with cd(ctrldir):
        cice_in_default = f90nml.read(CICE_NML_NAME)
        cice_in_default.patch(cice_in_patch)
        cice_in_default.write(CICE_NML_NAME, force=True)

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)
        model = expt.models[0]

        # Function to test
        with pytest.raises(RuntimeError):
            model.setup()
