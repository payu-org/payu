import os
import shutil

import pytest
import f90nml

import payu
from payu.branch import clone
import git


from test.common import cd
from test.common import tmpdir, ctrldir, labdir, expt_workdir
from test.common import expt_archive_dir, ctrldir_basename
from test.common import write_config, write_metadata
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


@pytest.fixture(autouse=True)
def empty_workdir():
    """
    Tests involving cloning + specified restarts require
    a clean work directory
    """
    expt_workdir.mkdir(parents=True)
    print(f"SPENCER {expt_workdir}")

    yield expt_workdir
    shutil.rmtree(expt_workdir)


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


def test_setup(cice_config_files):
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


class TestClone:
    """
    Test setting up the cice model in cloned control directories.
    """

    @pytest.fixture
    def ctrldir_repo(self, cice_config_files):
        """
        Initialise a git repository in the control directory.
        """
        repo = git.Repo.init(ctrldir)
        repo.index.add("*")

        # Commit the changes
        repo.index.commit("First commit - initialising repository")

        yield repo

        # Remove git from control dir after tests
        git.rmtree(ctrldir/".git")

    @pytest.fixture
    def clone_control_dir(self, ctrldir_repo):
        """
        Yield function for cloning the control directory. Cloning
        is not done directly in fixture to allow for an optional
        restart path to be supplied.
        """
        cloned_repo_path = tmpdir / "clonedRepo"

        def _clone_control_dir(restart_path=None):
            clone(str(ctrldir),
                  cloned_repo_path,
                  lab_path=labdir,
                  restart_path=restart_path)
            return cloned_repo_path

        yield _clone_control_dir

        # Teardown: Delete the cloned repository
        try:
            git.rmtree(cloned_repo_path)
        except FileNotFoundError:
            # Cloned repo won't exist if yielded function not called
            pass

    def test_clone(self, cice_config_files, ctrldir_repo, clone_control_dir):
        """
        Test that setting up cice works from a cloned control directory.
        """
        source_main = str(ctrldir_repo.active_branch)

        # Clone control directory
        cloned_repo_path = clone_control_dir(restart_path=None)
        cloned_repo = git.Repo(cloned_repo_path)
        cloned_repo.git.checkout(source_main)

        cloned_ctrl_path_files = os.listdir(cloned_repo_path)
        for name in CICE_NML_NAMES:
            assert name in cloned_ctrl_path_files

        # Set up experiment
        with cd(cloned_repo_path):
            lab = payu.laboratory.Laboratory(lab_path=str(labdir))
            expt = payu.experiment.Experiment(lab, reproduce=False)
            model = expt.models[0]

            # Test that model setup runs without issue
            model.setup()

        work_path_files = os.listdir(model.work_path)
        for name in CICE_NML_NAMES:
            assert name in work_path_files

    @pytest.fixture
    def prior_restart_dir_cice5(self, scope="class"):
        """
        Create fake prior restart files required by CICE5's setup.
        """
        prior_restart_path = expt_archive_dir / "restartxyz"
        os.mkdir(prior_restart_path)

        # Additional restart files required by CICE4 setup
        (prior_restart_path/ICED_RESTART_NAME).touch()
        (prior_restart_path/RESTART_POINTER_NAME).touch()

        yield prior_restart_path

        # Teardown
        shutil.rmtree(prior_restart_path)

    def test_restart_clone(self, cice_config_files, ctrldir_repo,
                           clone_control_dir, prior_restart_dir_cice5):

        """
        Test that seting up an experiment from a cloned control directory
        works when a restart directory is specified.

        Use a restart directory mimicking the CICE5 restarts required by setup.
        This differs from the cice4 test in that 'cice_in.nml' doesn't exist.
        """
        source_main = str(ctrldir_repo.active_branch)

        # Clone control directory
        cloned_repo_path = clone_control_dir(
                                restart_path=prior_restart_dir_cice5
                            )
        cloned_repo = git.Repo(cloned_repo_path)
        cloned_repo.git.checkout(source_main)

        cloned_ctrl_path_files = os.listdir(cloned_repo_path)

        for name in CICE_NML_NAMES:
            assert name in cloned_ctrl_path_files

        # Setup experiment
        with cd(cloned_repo_path):

            lab = payu.laboratory.Laboratory(lab_path=str(labdir))
            expt = payu.experiment.Experiment(lab, reproduce=False)
            model = expt.models[0]

            # Test that model setup runs without issue
            model.setup()

        work_path_files = os.listdir(model.work_path)
        for name in CICE_NML_NAMES:
            assert name in work_path_files

        # Check restart files were copied to cloned experiment's
        # work directory.
        cice_work_restart_files = os.listdir(model.work_restart_path)

        for file in [CICE_NML_NAME, ICED_RESTART_NAME, RESTART_POINTER_NAME]:
            assert file in cice_work_restart_files
