import copy
import os
import shutil
from pathlib import Path
import pytest

import payu
from payu.models.cesm_cmeps import Runconfig

from test.common import cd, tmpdir, ctrldir, labdir, workdir, write_config, config_path
from test.common import config as config_orig
from test.common import make_inputs, make_exe

NCPU = 24


@pytest.fixture()
def runconfig_path():
    return os.path.join('test', 'resources', 'nuopc.runconfig')


@pytest.fixture()
def runconfig(runconfig_path):
    return Runconfig(runconfig_path)


# Runconfig tests:

@pytest.mark.parametrize(
    "section, variable, expected",
    [
        ("ALLCOMP_attributes", "OCN_model", "mom"),
        ("CLOCK_attributes", "restart_n", "1"),
        ("DOES_NOT_EXIST", "OCN_model", None),
        ("ALLCOMP_attributes", "DOES_NOT_EXIST", None),
        ("allcomp_attributes", "OCN_model", None), # verify case sensitivity in section
        ("ALLCOMP_attributes", "ocn_model", None), # verify case sensitivity in variable
        ("ATM_attributes", "perpetual", ".false."), # correctly read booleans
        ("ICE_attributes", "eps_imesh", "1e-13"), # correctly read commented value
        ("MED_attributes", "histaux_atm2med_file1_flds", "Faxa_swndr:Faxa_swvdr:Faxa_swndf:Faxa_swvdf"), # correctly read long colon separated value
    ]
)
def test_runconfig_get(section, variable, expected, runconfig):
    """Test getting values from a nuopc.runconfig file"""
    assert runconfig.get(section, variable) == expected


def test_runconfig_get_default(runconfig):
    """Test getting default values from a nuopc.runconfig file"""
    assert runconfig.get("DOES_NOT_EXIST", "DOES_NOT_EXIST", value="default") == "default"


def test_runconfig_get_component_list(runconfig):
    """Test getting component_list from a nuopc.runconfig file"""
    COMP_LIST = ['MED', 'ATM', 'ICE', 'OCN', 'ROF']
    assert runconfig.get_component_list() == COMP_LIST


@pytest.mark.parametrize(
    "section, variable, new_variable",
    [
        ("ALLCOMP_attributes", "OCN_model", "pop"),
        ("CLOCK_attributes", "restart_n", "2"),
    ]
)
def test_runconfig_set(section, variable, new_variable, runconfig):
    """Test setting values in a nuopc.runconfig file"""
    runconfig.set(section, variable, new_variable)

    assert runconfig.get(section, variable) == new_variable


def test_runconfig_set_error(runconfig):
    """Test error setting values in a nuopc.runconfig file that don't exist"""
    with pytest.raises(
        NotImplementedError,
        match='Cannot set value of variable that does not already exist'
        ):
        runconfig.set("DOES_NOT_EXIST", "OCN_model", "value")
        runconfig.set("ALLCOMP_attributes", "DOES_NOT_EXIST", "value")


def test_runconfig_set_write_get(runconfig):
    """Test updating the values in a nuopc.runconfig file"""
    assert runconfig.get("CLOCK_attributes", "restart_n") == "1"

    runconfig.set("CLOCK_attributes", "restart_n", "2")

    runconfig_path_tmp = os.path.join(tmpdir, "nuopc.runconfig.tmp")
    runconfig.write(file=runconfig_path_tmp)

    runconfig_updated = Runconfig(runconfig_path_tmp)
    assert runconfig_updated.get("CLOCK_attributes", "restart_n") == "2"

    os.remove(runconfig_path_tmp)


# Tests of cesm_cmeps

def setup_module(module):
    """
    Put any test-wide setup code in here, e.g. creating test files
    """

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
        # archive_dir.mkdir()
        make_inputs()
        make_exe()
    except Exception as e:
        print(e)


def teardown_module(module):
    """
    Put any test-wide teardown code in here, e.g. removing test outputs
    """

    try:
        shutil.rmtree(tmpdir)
        print('removing tmp')
    except Exception as e:
        print(e)


@pytest.fixture
def cmeps_config():
    # Create a config.yaml and nuopc.runconfig file

    config = copy.deepcopy(config_orig)
    config['model'] = 'access-om3'
    config['ncpus'] = NCPU

    write_config(config)

    with open(os.path.join(ctrldir, 'nuopc.runconfig'), "w") as f:
        f.close()

    # Run test
    yield

    # Teardown
    os.remove(config_path)


# Mock runconfig for some tests
# valid minimum nuopc.runconfig for _setup_checks
MOCK_IO_RUNCONF = {
    "PELAYOUT_attributes": dict(
        moc_ntasks=NCPU,
        moc_nthreads=1,
        moc_pestride=1,
        moc_rootpe=0
    ),
    "MOC_modelio": dict(
        pio_numiotasks=1,
        pio_rearranger=1,
        pio_root=0,
        pio_stride=1,
        pio_typename='netcdf4p',
        pio_async_interface='.false.'
    )
}


class MockRunConfig:

    def __init__(self, config):
        self.conf = config

    def get_component_list(self):
        return ['MOC']

    def get(self, section, variable, value=None):
        return self.conf[section][variable]


@pytest.mark.parametrize("PELAYOUT_patch", [
                         {"moc_ntasks": 1},
                         {"moc_ntasks": NCPU},
                         {"moc_ntasks": 2, "moc_nthreads": NCPU/2},
                         {"moc_ntasks": 2, "moc_pestride": NCPU/2},
                         {"moc_ntasks": 2, "moc_rootpe": NCPU-2},
                         {"moc_ntasks": NCPU/4, "moc_nthreads": 2, "moc_pestride": 2},
                         ])
def test__setup_checks_npes(cmeps_config, PELAYOUT_patch):

    test_runconf = copy.deepcopy(MOCK_IO_RUNCONF)
    test_runconf["PELAYOUT_attributes"].update(PELAYOUT_patch)

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)
        model = expt.models[0]

        model.realms = ["moc"]

        model.runconfig = MockRunConfig(test_runconf)

        model._setup_checks()  


@pytest.mark.parametrize("PELAYOUT_patch", [
                         {"moc_ntasks": NCPU+1},
                         {"moc_ntasks": 1, "moc_nthreads": NCPU+1},
                         {"moc_ntasks": 1, "moc_pestride": NCPU+1},
                         {"moc_ntasks": 1, "moc_rootpe": NCPU},
                         {"moc_ntasks": NCPU/4+1, "moc_nthreads": 2, "moc_pestride": 2},
                         ])
def test__setup_checks_too_many_pes(cmeps_config, PELAYOUT_patch):

    test_runconf = copy.deepcopy(MOCK_IO_RUNCONF)
    test_runconf["PELAYOUT_attributes"].update(PELAYOUT_patch)

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)
        model = expt.models[0]

        model.realms = ["moc"]

        model.runconfig = MockRunConfig(test_runconf)

        with pytest.raises(ValueError):
            model._setup_checks() 


@pytest.mark.parametrize("modelio_patch", [
                         {"pio_typename": "netcdf"},
                         {"pio_typename": "netcdf", "pio_root": NCPU-1},
                         {"pio_typename": "netcdf", "pio_stride": 1000, "pio_numiotask": 1000},
                         {"pio_numiotasks": NCPU},
                         {"pio_numiotasks": 1, "pio_root": NCPU-1},
                         {"pio_numiotasks": 1, "pio_stride": NCPU},
                         {"pio_numiotasks": 1, "pio_root": NCPU/2, "pio_stride": NCPU/2}
                         ])
def test__setup_checks_io(cmeps_config, modelio_patch):

    test_runconf = copy.deepcopy(MOCK_IO_RUNCONF)
    test_runconf["MOC_modelio"].update(modelio_patch)
    
    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)
        model = expt.models[0]

        model.realms = ["moc"]

        model.runconfig = MockRunConfig(test_runconf)

        model._setup_checks()  


@pytest.mark.parametrize("modelio_patch", [
                         {"pio_typename": "netcdf4s"},
                         {"pio_typename": "netcdf", "pio_root": NCPU+1},
                         {"pio_numiotasks": NCPU+1},
                         {"pio_numiotasks": 1, "pio_root": NCPU},
                         {"pio_numiotasks": 2, "pio_stride": NCPU},
                         {"pio_numiotasks": 1, "pio_stride": NCPU+1},
                         {"pio_numiotasks": 1, "pio_root": NCPU/2, "pio_stride": NCPU/2+1}
                         ])
def test__setup_checks_bad_io(cmeps_config, modelio_patch):

    test_runconf = copy.deepcopy(MOCK_IO_RUNCONF)
    test_runconf["MOC_modelio"].update(modelio_patch)

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)
        model = expt.models[0]

        model.realms = ["moc"]

        model.runconfig = MockRunConfig(test_runconf)

        with pytest.raises(ValueError):
            model._setup_checks() 
