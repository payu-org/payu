import copy
import os
import shutil
import datetime

import pytest
import cftime
import f90nml
from unittest.mock import patch

import payu

from test.common import cd, expt_workdir
from test.common import tmpdir, ctrldir, labdir, workdir, archive_dir
from test.common import config as config_orig
from test.common import write_config
from test.common import make_all_files
from test.common import list_expt_archive_dirs
from test.common import make_expt_archive_dir, remove_expt_archive_dirs
from test.common import config_path
from test.models.test_um import make_atmosphere_restart_dir
from test.models.test_mom_mixin import make_ocean_restart_dir
from payu.calendar import GREGORIAN, NOLEAP


verbose = True


INPUT_ICE_FNAME = "input_ice.nml"
RESTART_DATE_FNAME = "restart_date.nml"
SEC_PER_DAY = 24*60*60


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


def test_access_cice_calendar_cycling_500(
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

    n_years = 500
    expected_end_date = 6010101
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

            # Skip writing restart pointer as it requires iced file
            # with valid header. Restart pointer functionality is tested
            # in test_cice.py.
            with patch(
                'payu.models.cice.Cice.overwrite_restart_ptr',
                return_value=None
            ):
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


@pytest.mark.parametrize(
        "start_date_int, caltype, expected_runtime",
        [(1010101, GREGORIAN, 365*SEC_PER_DAY),
         (1010101, NOLEAP, 365*SEC_PER_DAY),
         (1040101, GREGORIAN, 366*SEC_PER_DAY),
         (1040101, NOLEAP, 365*SEC_PER_DAY),
         (3000101, GREGORIAN, 365*SEC_PER_DAY),
         (3000101, NOLEAP, 365*SEC_PER_DAY),
         (4000101, GREGORIAN, 366*SEC_PER_DAY),
         (4000101, NOLEAP, 365*SEC_PER_DAY)]
)
def test_access_cice_1year_runtimes(
    access_1year_config,
    ice_control_directory,
    fake_cice_in,
    restart_dir,
    initial_start_date_file,
    start_date_int,
    caltype,
    expected_runtime
):
    """
    The large setup/archive cycling test won't pick up situations
    where the calculations during setup and archive are simultaneously
    wrong, e.g. if they both used the wrong calendar.
    Hence test seperately that the correct runtimes for cice are
    written by the access.setup() step for a range of standard
    and generally tricky years.
    """
    # Write an input_ice.nml namelist to the control directory
    # with the specified calendar type.
    ctrl_input_ice_path = ice_control_directory / INPUT_ICE_FNAME
    input_ice_nml = {
        "coupling":
        {
            "caltype": caltype
        }
    }
    f90nml.write(input_ice_nml, ctrl_input_ice_path)

    # Reset the start date in the initial_start_date_file
    initial_start_nml = f90nml.read(initial_start_date_file)
    # Make sure our start date doesn't occur before the init_date
    assert start_date_int >= initial_start_nml["coupling"]["init_date"]

    initial_start_nml["coupling"]["inidate"] = start_date_int
    f90nml.write(initial_start_nml, initial_start_date_file, force=True)

    # Setup the experiment
    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)

        # For the purposes of the test, use one year runtime
        expt.runtime["years"] = 1
        expt.runtime["months"] = 0
        expt.runtime["days"] = 0
        expt.runtime["seconds"] = 0

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
        # each run. However we will just use one for the tests.
        cice_model.prior_restart_path = restart_dir
        cice_model.restart_path = restart_dir

        # Manually copy the input_ice.nml file from the control directory
        # to the work directory. This would normally happen in cice.setup()
        # which we are trying to bypass.
        shutil.copy(ctrl_input_ice_path, cice_model.work_path)

        # Skip writing restart pointer as it requires iced file
        # with valid header. Restart pointer functionality is tested
        # in test_cice.py
        with patch(
            'payu.models.cice.Cice.overwrite_restart_ptr',
            return_value=None
        ):
            access_model.setup()

        # Check that the correct runtime is written to the work directory's
        # input ice namelist.
        work_input_ice = f90nml.read(cice_model.work_path/INPUT_ICE_FNAME)
        written_runtime = work_input_ice["coupling"]["runtime"]
        assert written_runtime == expected_runtime


@pytest.fixture
def remove_restart_dirs():
    """Clear any restart directories created during a test"""
    yield
    # Teardown
    remove_expt_archive_dirs(type="restart")


@pytest.fixture
def two_model_config():
    config = copy.deepcopy(config_orig)
    config["model"] = "access"
    config["submodels"] = [{"name": "atmosphere",
                           "model": "um"},
                           {"name": "ocean",
                           "model": "mom"}
                           ]
    write_config(config)

    # Run test
    yield

    # Teardown
    os.remove(config_path)


def test_access_get_mom_restart_datetime(two_model_config,
                                         remove_restart_dirs):
    """
    Check that the restart datetime is read using the
    the mom submodel by default.
    """
    # Create 1 mom restart directory
    start_dt = "1900-01-01 00:00:00"
    run_dt = "1900-02-01 00:00:00"
    calendar = 3  # proleptic Gregorian
    make_ocean_restart_dir(start_dt, run_dt, calendar, additional_path="ocean")

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)

    restart_path = list_expt_archive_dirs()[0]

    with (
        patch("payu.models.um.UnifiedModel.get_restart_datetime") as um_date
    ):
        parsed_run_dt = expt.model.get_restart_datetime(restart_path)

    um_date.assert_not_called()

    assert parsed_run_dt == cftime.datetime(1900, 2, 1,
                                            calendar="proleptic_gregorian")


@pytest.fixture
def um_only_config():
    config = copy.deepcopy(config_orig)
    config["model"] = "access"
    config["submodels"] = [{"name": "atmosphere",
                           "model": "um"}]
    write_config(config)

    # Run test
    yield

    # Teardown
    os.remove(config_path)


def test_access_get_um_restart_datetime(um_only_config, remove_restart_dirs):
    """
    Check that the restart datetime can be read when only
    the UM submodel is present.
    """
    # Create UM restart directory
    date = datetime.datetime(100, 1, 1)
    make_atmosphere_restart_dir("um.res.yaml", date,
                                additional_path="atmosphere")

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)

    restart_path = list_expt_archive_dirs()[0]
    parsed_run_dt = expt.model.get_restart_datetime(restart_path)
    assert parsed_run_dt == cftime.datetime(100, 1, 1,
                                            calendar="proleptic_gregorian")
