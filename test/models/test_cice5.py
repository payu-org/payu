import os
import shutil

import pytest
import f90nml

import payu
from payu.branch import clone
import git


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
CICE_NML_NAMES = ["cice_in.nml", "input_ice.nml", "input_ice_gfdl.nml", "input_ice_monin.nml"]

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
        "model": "cice5",
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

@pytest.fixture
def cice_config_files():
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
        f90nml.write(cice_nml, CICE_NML_NAMES[0])
        for name in CICE_NML_NAMES[1:]:
            with open(name, "w") as f:
                f.close()

    yield

    # cleanup
    with cd(expt_workdir):
        os.remove(cice_nml["setup_nml"]["pointer_file"])
        os.rmdir(cice_nml["setup_nml"]["restart_dir"])
    with cd(ctrldir):
        for name in CICE_NML_NAMES:
            os.remove(name)
        

# Confirm that 1: payu setup works 
def test_setup(cice_config_files):

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


def test_clone(cice_config_files):
    with cd(ctrldir):
            
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)
        model = expt.models[0]

        # Function to test
        model.setup()

    # Initialise a control repo
    repo = git.Repo.init(ctrldir)
    repo.index.add("*")
    # Commit the changes
    repo.index.commit("First commit - initialising repository")
    source_main = str(repo.active_branch)

    # Clone
    cloned_repo_path = tmpdir / "clonedRepo"
    clone(str(ctrldir), cloned_repo_path, lab_path=labdir)

    cloned_repo = git.Repo(cloned_repo_path)
    cloned_repo.git.checkout(source_main)

    ctrl_path_files = os.listdir(cloned_repo_path)
    for name in CICE_NML_NAMES:
        assert name in ctrl_path_files

    # Setup

    with cd(cloned_repo_path):

        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)
        model = expt.models[0]

        # Function to test
        model.setup()

    work_path_files = os.listdir(model.work_path)
    for name in CICE_NML_NAMES:
        assert name in ctrl_path_files

    shutil.rmtree(cloned_repo_path)