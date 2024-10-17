import os
import shutil

import pytest
import f90nml
import tarfile
from pathlib import Path

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
    try:
        shutil.rmtree(expt_workdir)
    except FileNotFoundError:
        pass
    workdir.unlink()


@pytest.fixture
def cice_nml():
    nml_path = os.path.join(ctrldir, CICE_NML_NAME)
    f90nml.write(DEFAULT_CICE_NML, nml_path)

    yield nml_path

    # Cleanup
    os.remove(nml_path)


# Important to test None case without separate ice history file
@pytest.fixture(params=[None,
                        {"icefields_nml": {"f_icy": "m"}},
                        {"icefields_nml": {"f_icy": "m", "f_new": "y"}}])
def cice_history_nml(request):
    """
    Write separate ice history namelist used by ESM1.5, if provided.
    """
    ice_history = request.param
    ice_history_path = os.path.join(ctrldir, HIST_NML_NAME)

    if ice_history:
        f90nml.write(ice_history, ice_history_path)

    yield {'ice_history': ice_history}

    # cleanup
    if ice_history:
        os.remove(ice_history_path)


@pytest.mark.parametrize("config", [DEFAULT_CONFIG],
                         indirect=True)
def test_setup(config, cice_nml, cice_history_nml):
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
    if cice_history_nml['ice_history']:
        assert (input_nml["icefields_nml"] ==
                cice_history_nml["ice_history"]["icefields_nml"])
    else:
        assert input_nml["icefields_nml"] == DEFAULT_CICE_NML["icefields_nml"]

    # Check dump_last doesn't exist
    with pytest.raises(KeyError, match="dump_last"):
        input_nml["setup_nml"]["dump_last"]


@pytest.fixture(
    # prior_istep0, prior_npt, runtime, expected_npt
    params=[
        (0, 0, {"years": 0, "months": 0, "days": 2}, 48),
        (0, 8670, {"years": 1, "months": 0, "days": 0}, 8760),
        (8760000, 8670, {"years": 0, "months": 0, "days": 31}, 744),
        (1416, 0, {"years": 0, "months": 1, "days": 0}, 744)
    ]
)
def run_timing_params(request):
    return request.param


@pytest.fixture
def prior_restart_cice4(run_timing_params):
    """
    Create fake prior restart files required by CICE4's setup.
    This differs from CICE5, which doesn't require a cice_in.nml
    file in the restart directory.
    """
    prior_restart_path = RESTART_PATH
    os.mkdir(prior_restart_path)

    prior_istep0, prior_npt, _, _ = run_timing_params
    # Previous cice_in namelist with time information
    restart_cice_in = {"setup_nml": {
            "istep0": prior_istep0,
            "npt": prior_npt,
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
def test_restart_setup(config, cice_nml, cice_history_nml, prior_restart_cice4,
                       run_timing_params):
    """
    Test that seting up an experiment from a cloned control directory
    works when a restart directory is specified.

    Use a restart directory mimicking the CICE4 files required by setup.
    """

    prior_istep0, prior_npt, runtime, expected_npt = run_timing_params
    # Setup experiment
    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)

        # Add a runtime to test calculated cice runtime values
        expt.runtime = runtime
        model = expt.models[0]

        # Function to test
        model.setup()

    # Check correct run time values written to work namelist
    work_cice_nml = f90nml.read(
        os.path.join(model.work_path, CICE_NML_NAME)
        )
    assert work_cice_nml["setup_nml"]["istep0"] == (
        prior_istep0 + prior_npt
    )
    assert work_cice_nml["setup_nml"]["npt"] == (
        expected_npt
    )

    # Check restart files were copied to work directory.
    cice_work_restart_files = os.listdir(model.work_restart_path)

    for file in [CICE_NML_NAME, ICED_RESTART_NAME, RESTART_POINTER_NAME]:
        assert file in cice_work_restart_files


@pytest.mark.parametrize("config", [DEFAULT_CONFIG],
                         indirect=True)
def test_no_restart_ptr(config, cice_nml, cice_history_nml):
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
        with pytest.raises(RuntimeError,
                           match="Cannot find previous restart file"):
            model.setup()


CONFIG_WITH_COMPRESSION = {
    "laboratory": "lab",
    "jobname": "testrun",
    "model": "cice",
    "exe": "test.exe",
    "experiment": ctrldir_basename,
    "metadata": {"enable": False},
    "compress_logs": True
}


@pytest.fixture
def cice4_log_files():
    """
    Create cice log files matching those produced during ESM1.5 simulations.
    """
    log_names = (["ice_diag_out", "ice_diag.d", "debug.root.03"]
                 + [f'iceout{x:03d}' for x in range(85, 96)])
    log_paths = [Path(expt_workdir)/name for name in log_names]

    for log_file in log_paths:
        log_file.touch()

    yield log_paths

    # Cleanup
    for log_file in log_paths:
        try:
            log_file.unlink()
        except FileNotFoundError:
            pass


@pytest.fixture
def non_log_file():
    """
    Create a cice4 output file to be ignored by log compression.
    Use cice_in.nml which is copied to the work directory in ESM1.5.
    """
    non_log_path = Path(expt_workdir)/CICE_NML_NAME
    non_log_path.touch()

    yield non_log_path

    # Cleanup
    non_log_path.unlink()


@pytest.mark.parametrize("config", [CONFIG_WITH_COMPRESSION],
                         indirect=True)
def test_log_compression(config, cice4_log_files, non_log_file,
                         cice_nml   # Required by expt.__init__
                         ):
    """
    Test that logfiles produced by cice during ESM1.5 simulations are
    properly compressed into a tarball by cice.compress_log_files().
    """
    with cd(ctrldir):
        # Initialise laboratory and experiment
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)
        model = expt.models[0]

        # Function to test
        model.compress_log_files()

    # Check that log tarball created and no original logs remain
    assert set(os.listdir(expt_workdir)) == {model.log_tar_name,
                                             non_log_file.name}

    # Check all logs present in tarball
    log_file_names = {log_path.name for
                      log_path in cice4_log_files}

    with tarfile.open(os.path.join(expt_workdir, model.log_tar_name),
                      "r") as tar:
        assert set(tar.getnames()) == log_file_names
