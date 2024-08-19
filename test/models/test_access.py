import copy
import os
import shutil

import pytest
import cftime

import payu

from test.common import cd
from test.common import tmpdir, ctrldir, labdir, workdir, archive_dir
from test.common import config as config_orig
from test.common import write_config
from test.common import make_all_files
from test.common import list_expt_archive_dirs
from test.common import make_expt_archive_dir, remove_expt_archive_dirs
from test.common import config_path
import f90nml


verbose = True


INPUT_ICE_FNAME = "input_ice.nml"
RESTART_DATE_FNAME = "restart_date.nml"


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
        workdir.mkdir()
        archive_dir.mkdir()
        make_all_files()
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
    except Exception as e:
        print(e)


@pytest.fixture
def access_1year_config():
    # Write an access model config file with 1 year runtime

    # Create a config.yaml file with the cice submodel and 1 year run length

    # Global config
    config = copy.deepcopy(config_orig)
    config['model'] = 'access'
    config['submodels'] = [{"name": "ice",
                            "model": "cice"}]

    config["calendar"] = {'start': {'year': 101, 'month': 1, 'days': 1},
                          'runtime': {'years': 1, 'months': 0, 'days': 0}}
    write_config(config)

    # Run test
    yield

    # Teardown
    os.remove(config_path)


@pytest.fixture
def ice_control_directory():
    # Make a cice control subdirectory
    ice_ctrl_dir = ctrldir / "ice"
    ice_ctrl_dir.mkdir()

    # Run test
    yield ice_ctrl_dir

    # Teardown
    shutil.rmtree(ice_ctrl_dir)


@pytest.fixture
def default_input_ice(ice_control_directory):
    # Create base input_ice.nml namelist
    ctrl_input_ice_path = ice_control_directory / INPUT_ICE_FNAME

    # Default timing values from the input_ice.nml namelist that will be
    # overwritten by the calendar calculations.
    default_input_nml = {
        "coupling":
        {
            "caltype": 1,
            "jobnum": 2,
            "inidate": "01010101",
            "init_date": "00010101",
            "runtime0": 3155673600,
            "runtime": 86400
        }
    }
    f90nml.write(default_input_nml, ctrl_input_ice_path)

    # Run test
    yield ctrl_input_ice_path

    # Teardown handled by ice_control_directory fixture


@pytest.fixture
def fake_cice_in(ice_control_directory):
    # Create a fake cice_in.nml file. This is irrelevant for the tests,
    # however is required to exist for the experiment initialisation.
    fake_cice_in_nml = {
        "setup_nml": {
            "restart_dir": "",
            "history_dir": ""
        },
        "grid_nml": {
            "grid_file": "",
            "kmt_file": ""
        }
    }
    fake_cice_in_path = ice_control_directory / "cice_in.nml"
    f90nml.write(fake_cice_in_nml, fake_cice_in_path)

    yield fake_cice_in_path

    # Teardown handled by ice_control_directory fixture


@pytest.fixture
def restart_dir():
    # Create restart directory for ice timing tests
    restart_path = archive_dir / "restart"
    restart_path.mkdir()

    # Run test
    yield restart_path

    # Teardown
    shutil.rmtree(restart_path)


@pytest.fixture
def initial_start_date_file(restart_dir):
    # Initital start date for testing calendar cycling
    initial_res_date = {
        "coupling": {
            "init_date": 10101,
            "inidate": 1010101
        }
    }
    res_date_path = restart_dir / RESTART_DATE_FNAME
    f90nml.write(initial_res_date, res_date_path)

    # Run test
    yield res_date_path

    # Teardown handled by restart_dir fixture


def test_esm_calendar_cycling_1000(
        access_1year_config,
        ice_control_directory,
        default_input_ice,
        fake_cice_in,
        restart_dir,
        initial_start_date_file):
    """
    Test that cice run date calculations remain correct when cycling
    over a large number of runs.
    """

    n_years = 1000
    expected_end_date = 11010101
    expected_end_init_date = 10101
    # Setup the experiment
    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)
        # Get the models
        for model in expt.models:
            if model.model_type == "cice":
                cice_model = model
        # There are two access models within the experiment. The top level
        # model, expt.model, and the one under expt.models. The top level
        # model's setup and archive steps are the ones that actually run.
        access_model = expt.model

        # Overwrite cice model paths created during experiment initialisation.
        # It's simpler to just set them here than rely on the ones collected
        # from the fake namelist files.
        cice_model.work_path = workdir

        # Path to read and write restart dates from. In a real experiment
        # The read and write restart dirs would be different and increment
        # each run. However we will just use one for the tests to avoid
        # creating hundreds of directories.
        cice_model.prior_restart_path = restart_dir
        cice_model.restart_path = restart_dir

        for i in range(n_years):
            if i % 100 == 0:
                print(f"Access setup/archive cycle: {i}")

            # Manually copy the input_ice.nml file from the control directory
            # to the work directory. This would normally happen in cice.setup()
            # which we are trying to bypass.
            shutil.copy(default_input_ice, cice_model.work_path)

            access_model.setup()
            access_model.archive()

        end_date_fpath = os.path.join(
                        cice_model.restart_path,
                        cice_model.start_date_nml_name
                    )

        end_date_nml = f90nml.read(end_date_fpath)[
                            cice_model.cpl_group]

        final_end_date = end_date_nml["inidate"]
        final_init_date = end_date_nml["init_date"]

        assert final_end_date == expected_end_date
        assert final_init_date == expected_end_init_date
