import copy
import os
import shutil
from pathlib import Path
import pytest

import payu

from test.common import cd, tmpdir, ctrldir, labdir, workdir, write_config, config_path
from test.common import config as config_orig
from test.common import make_inputs, make_exe

NCPU = 24
MODEL = 'access-om3'

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
    config['model'] = MODEL
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
                         {"pio_typename": "netcdf4c"},
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
