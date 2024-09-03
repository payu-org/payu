import copy
import os
import shutil
from pathlib import Path
import pytest

import payu

from test.common import cd, tmpdir, ctrldir, labdir, workdir, write_config, config_path
from test.common import config as config_orig
from test.common import make_inputs, make_exe

MODEL = 'access-om3'


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


def cmeps_config(ncpu):
    # Create a config.yaml and nuopc.runconfig file

    config = copy.deepcopy(config_orig)
    config['model'] = MODEL
    config['ncpus'] = ncpu

    write_config(config)

    with open(os.path.join(ctrldir, 'nuopc.runconfig'), "w") as f:
        f.close()


def teardown_cmeps_config():
    # Teardown
    os.remove(config_path)


# Mock runconfig for some tests
# valid minimum nuopc.runconfig for _setup_checks
MOCK_IO_RUNCONF = {
    "PELAYOUT_attributes": dict(
        moc_ntasks=1,
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


@pytest.mark.parametrize("ncpu, moc_ntasks, moc_nthreads, moc_pestride, moc_rootpe", [
                         (1, 1, 1, 1, 0),  # min
                         (4, 4, 1, 1, 0),  # min tasks
                         (4, 2, 2, 2, 0),  # min tasks * threads
                         (4, 2, 1, 1, 2),  # min tasks + rootpe
                         (4, 1, 2, 2, 2),  # min threads + rootpe
                         (4, 1, 1, 1, 3),  # max rootpe
                         (5, 2, 1, 4, 0),  # max stride
                         (13, 4, 1, 3, 1),  # odd ncpu
                         (13, 2, 3, 3, 1),  # odd ncpu
                         (100000, 50000, 1, 2, 0),  # max cpu
                         (100000, 1, 1, 1, 99999),  # max cpu
                         ])
def test__setup_checks_npes(ncpu, moc_ntasks, moc_nthreads, moc_pestride, moc_rootpe):

    cmeps_config(ncpu)

    test_runconf = copy.deepcopy(MOCK_IO_RUNCONF)
    test_runconf["PELAYOUT_attributes"].update({
        "moc_ntasks": moc_ntasks,
        "moc_nthreads": moc_nthreads,
        "moc_pestride": moc_pestride,
        "moc_rootpe": moc_rootpe
        })

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)
        model = expt.models[0]

        model.realms = ["moc"]

        model.runconfig = MockRunConfig(test_runconf)

        model._setup_checks()

    teardown_cmeps_config()


@pytest.mark.parametrize("ncpu, moc_ntasks, moc_nthreads, moc_pestride, moc_rootpe", [
                         (1, 1, 1, 1, 1),  # min
                         (4, 5, 1, 1, 0),  # min tasks
                         (4, 2, 2, 2, 1),  # min tasks * threads
                         (2, 1, 2, 1, 1),  # threads > strides
                         (4, 1, 3, 1, 2),  # min threads + rootpe
                         (4, 1, 1, 1, 4),  # max rootpe
                         (13, 4, 1, 4, 1),  # odd ncpu
                         (13, 2, 7, 7, 0),  # odd ncpu
                         (100000, 50001, 1, 2, 0),  # max cpu
                         (100000, 1, 1, 1, 100000),  # max cpu
                         ])
def test__setup_checks_too_many_pes(ncpu, moc_ntasks, moc_nthreads, moc_pestride, moc_rootpe):

    cmeps_config(ncpu)

    test_runconf = copy.deepcopy(MOCK_IO_RUNCONF)
    test_runconf["PELAYOUT_attributes"].update({
        "moc_ntasks": moc_ntasks,
        "moc_nthreads": moc_nthreads,
        "moc_pestride": moc_pestride,
        "moc_rootpe": moc_rootpe
    })

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)
        model = expt.models[0]

        model.realms = ["moc"]

        model.runconfig = MockRunConfig(test_runconf)

        with pytest.raises(ValueError):
            model._setup_checks()

    teardown_cmeps_config()


@pytest.mark.parametrize("ncpu, pio_numiotasks, pio_stride, pio_root, pio_typename", [
                         (1, 1, 1, 0, "netcdf"),  # min
                         (2, 1, 1, 1, "netcdf"),  # max root
                         (2, 2, 1, 0, "netcdf4p"),  # min tasks + rootpe
                         (2, 1, 1, 1, "netcdf4p"),  # max rootpe
                         (5, 3, 2, 0, "netcdf4p"),
                         (100000, 50001, 1, 2, "netcdf4p"),  # odd ncpu
                         ])
def test__setup_checks_io(ncpu, pio_numiotasks, pio_stride, pio_root, pio_typename):

    cmeps_config(ncpu)

    test_runconf = copy.deepcopy(MOCK_IO_RUNCONF)
    test_runconf["PELAYOUT_attributes"].update({
        "moc_ntasks": ncpu
    })
    test_runconf["MOC_modelio"].update(dict(
        pio_numiotasks=pio_numiotasks,
        pio_root=pio_root,
        pio_stride=pio_stride,
        pio_typename=pio_typename,
    ))

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)
        model = expt.models[0]

        model.realms = ["moc"]

        model.runconfig = MockRunConfig(test_runconf)

        model._setup_checks()

    teardown_cmeps_config()


@pytest.mark.parametrize("ncpu, pio_numiotasks, pio_stride, pio_root, pio_typename", [
                         (1, 1, 1, 0, "netcdf4c"),
                         (2, 1, 1, 2, "netcdf"),  # root too big
                         (2, 3, 1, 0, "netcdf4p"),  # too manu tasks
                         (2, 2, 2, 0, "netcdf4p"),  # stride too big
                         (5, 2, 2, 3, "netcdf4p"),  # stride too big
                         (100000, 50000, 2, 2, "netcdf4p"),  # odd ncpu
                         ])
def test__setup_checks_bad_io(ncpu, pio_numiotasks, pio_stride, pio_root, pio_typename):
    cmeps_config(ncpu)

    test_runconf = copy.deepcopy(MOCK_IO_RUNCONF)
    test_runconf["PELAYOUT_attributes"].update({
        "moc_ntasks": ncpu
    })
    test_runconf["MOC_modelio"].update(dict(
        pio_numiotasks=pio_numiotasks,
        pio_root=pio_root,
        pio_stride=pio_stride,
        pio_typename=pio_typename,
    ))

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)
        model = expt.models[0]

        model.realms = ["moc"]

        model.runconfig = MockRunConfig(test_runconf)

        with pytest.raises(ValueError):
            model._setup_checks()

    teardown_cmeps_config()
    