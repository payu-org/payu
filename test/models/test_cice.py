import os
import shutil

import pytest
import f90nml

import payu

from test.common import cd
from test.common import tmpdir, ctrldir, labdir, expt_workdir, ctrldir_basename
from test.common import write_config, write_metadata
from test.common import make_inputs, make_exe

verbose = True

DEFAULT_CICE_NML = {
    "setup_nml": {
        "history_dir": "./HISTORY/",
        "restart_dir": "./RESTART/",
        "year_init": 9999,
        "days_per_year": 360,
        "ice_ic": "default",
        "restart": ".false.",
        "pointer_file": "./RESTART/ice.restart_file",
        "runtype": "initial",
        "npt": 99999,
        "dt": 1,
    },
    "grid_nml": {"grid_file": "./INPUT/grid.nc", "kmt_file": "./INPUT/kmt.nc"},
    "icefields_nml": {"f_icy": "x"},
}
CICE_NML_NAME = "cice_in.nml"
HIST_NML_NAME = "ice_history.nml"


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
        expt_workdir.mkdir(parents=True)
        make_inputs()
        make_exe()
        write_metadata()
    except Exception as e:
        print(e)

    config = {
        "laboratory": "lab",
        "jobname": "testrun",
        "model": "cice",
        "exe": "test.exe",
        "experiment": ctrldir_basename,
        "metadata": {"enable": False},
    }
    write_config(config)


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


# Confirm that 1: payu overwrites cice_in with ice_history
# 2: payu works without ice_history.nml
# 3: payu overwrites cice_in and allows additional fields
# In all cases confirm dump_last is not added to model_type='cice'
@pytest.mark.parametrize(
    "ice_history",
    [
        {"icefields_nml": { "f_icy": "m" }},
        False,
        {"icefields_nml": {"f_icy": "m", "f_new": "y"}},
    ],
)
def test_setup(ice_history):
    cice_nml = DEFAULT_CICE_NML

    # create the files parsed by setup:
    # 1. a restart pointer file
    with cd(expt_workdir):
        os.mkdir(cice_nml["setup_nml"]["restart_dir"])
        with open(cice_nml["setup_nml"]["pointer_file"], "w") as f:
            f.write("./RESTART/ice.r")
            f.close()

    with cd(ctrldir):
        # 2. Create config.nml
        f90nml.write(cice_nml, CICE_NML_NAME)
        if ice_history:
            f90nml.write(ice_history, HIST_NML_NAME)

        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)
        model = expt.models[0]

        # Function to test
        model.setup()

    # Check config files are moved to model's work path
    work_path_files = os.listdir(model.work_path)
    assert CICE_NML_NAME in work_path_files

    # Check cice_in was patched with ice_history
    work_input_fpath = os.path.join(model.work_path, CICE_NML_NAME)
    input_nml = f90nml.read(work_input_fpath)
    if ice_history:
        assert input_nml["icefields_nml"] == ice_history["icefields_nml"]
    else:
        assert input_nml["icefields_nml"] == DEFAULT_CICE_NML["icefields_nml"]

    # Check dump_last doesn't exist
    with pytest.raises(KeyError, match="dump_last"):
        input_nml["setup_nml"]["dump_last"]

    # cleanup
    with cd(expt_workdir):
        os.remove(cice_nml["setup_nml"]["pointer_file"])
        os.rmdir(cice_nml["setup_nml"]["restart_dir"])
    with cd(ctrldir):
        os.remove(CICE_NML_NAME)
        if ice_history:
            os.remove(HIST_NML_NAME)
