import copy
import os
from pathlib import Path
import pdb
import shutil

import f90nml
import pytest
from ruamel.yaml import YAML
yaml = YAML()
yaml.default_flow_style = False

import payu


import payu.models.mitgcm as model

import test.common as common

from test.common import cd, make_random_file, get_manifests
from test.common import tmpdir, ctrldir, labdir, workdir
from test.common import sweep_work, payu_init, payu_setup
from test.common import config as config_orig
from test.common import write_config
from test.common import make_exe, make_inputs, make_restarts, make_all_files

verbose = True

# From tutorial_barotropic_gyre
data_orig = {
    "parm01": {
        "viscah": 400.0,
        "f0": 0.0001,
        "beta": 1e-11,
        "rhoconst": 1000.0,
        "gbaro": 9.81,
        "rigidlid": False,
        "implicitfreesurface": True,
        "tempstepping": False,
        "saltstepping": False
    },
    "parm02": {
        "cg2dtargetresidual": 1e-07,
        "cg2dmaxiters": 1000
    },
    "parm03": {
        "niter0": 0,
        "ntimesteps": 10,
        "deltat": 1200.0,
        "pchkptfreq": 12000.0,
        "chkptfreq": 0.0,
        "dumpfreq": 12000.0,
        "monitorfreq": 1200.0,
        "monitorselect": 2
    },
    "parm04": {
        "usingcartesiangrid": True,
        "delx": [20000.] * 62,
        "dely": [20000.] * 62,
        "xgorigin": -20000.0,
        "ygorigin": -20000.0,
        "delr": 5000.0
    },
    "parm05": {
        "bathyfile": "bathy.bin",
        "zonalwindfile": "windx_cosy.bin",
        "meridwindfile": None
    }
}

config = copy.deepcopy(config_orig)

config['model'] = 'mitgcm'

@pytest.fixture(autouse=True)
def setup_module(setup_test_dir, empty_workdir):
    pass

def make_config_files(data):
    """
    Create files required for test model
    """

    f90nml.namelist.Namelist(data).write(ctrldir/'data', force=True)

@pytest.fixture
def config(setup_test_dir):
    """Write a config file into the control directory.
    This will be automatically cleaned up by `setup_test_dir` fixture after tests."""
    config = copy.deepcopy(config_orig)
    config['model'] = 'mitgcm'
    write_config(config)
    return config

@pytest.fixture
def data():
    return copy.deepcopy(data_orig)


def make_pickup_names(istep):

    return ['pickup.{:010d}.001.001.{}'.format(istep, type)
            for type in ['data', 'meta']]


def test_make_pickup_names():
    assert(make_pickup_names(10) == ['pickup.0000000010.001.001.data',
                                     'pickup.0000000010.001.001.meta'])



def test_init(config):

    # Initialise a payu laboratory
    with cd(ctrldir):
        payu_init(None, None, str(labdir))

    # Check all the correct directories have been created
    for subdir in ['bin', 'input', 'archive', 'codebase']:
        assert((labdir / subdir).is_dir())


def test_setup(config, data):

    # Create some input and executable files
    make_inputs()
    make_exe()

    bindir = labdir / 'bin'
    exe = config['exe']

    make_config_files(data)

    # Run setup
    payu_setup(lab_path=str(labdir))

    assert(workdir.is_symlink())
    assert(workdir.is_dir())
    assert((workdir/exe).resolve() == (bindir/exe).resolve())
    workdirfull = workdir.resolve()

    config_files = ['data']

    for f in config_files + ['config.yaml']:
        assert((workdir/f).is_file())

    data_local = f90nml.read(workdir/'data')

    assert data_local['parm03']['nIter0'] == 0
    assert data_local['parm03']['nTimeSteps'] == 10
    assert data_local['parm03']['deltaT'] == 1200.
    assert data_local['parm03']['starttime'] == 0.
    assert data_local['parm03']['endtime'] == 12000.

    for i in range(1, 4):
        assert((workdir/'input_00{i}.bin'.format(i=i)).stat().st_size
               == 1000**2 + i)

    manifests = get_manifests(ctrldir/'manifests')
    for mfpath in manifests:
        assert((ctrldir/'manifests'/mfpath).is_file())

    # Check manifest in work directory is the same as control directory
    assert(manifests == get_manifests(workdir/'manifests'))

    # Sweep workdir and recreate
    sweep_work()

    assert(not workdir.is_dir())
    assert(not workdirfull.is_dir())

    payu_setup(lab_path=str(labdir))

    assert(manifests == get_manifests(workdir/'manifests'))


def test_setup_restartdir(config, data):

    restartdir = labdir / 'archive' / 'restarts'

    # Set a restart directory in config
    config['restart'] = str(restartdir)
    write_config(config)
    make_config_files(data)

    res_fnames = make_pickup_names(10)

    make_restarts(res_fnames)

    # Run setup
    payu_setup(lab_path=str(labdir))

    mitgcm_restart = {}
    mitgcm_restart['endtime'] = 12000.

    with (restartdir / 'mitgcm.res.yaml').open('w') as file:
        yaml.dump(mitgcm_restart, file)

    manifests = get_manifests(ctrldir/'manifests')
    payu_setup(lab_path=str(labdir))

    # Manifests should not match, as have added restarts
    assert(not manifests == get_manifests(ctrldir/'manifests'))

    data_local = f90nml.read(workdir/'data')

    assert data_local['parm03']['nIter0'] == 10
    assert data_local['parm03']['nTimeSteps'] == 10
    assert data_local['parm03']['deltaT'] == 1200.
    assert data_local['parm03']['starttime'] == 12000.
    assert data_local['parm03']['endtime'] == 24000.


@pytest.mark.parametrize(
    "case",
    [
        {"deltat": 999,
        "ntimesteps": 5,
        "expected": {
            "nIter0": 0,
            "deltaT": 999.0,
            "basetime": 12000.0,
            "starttime": 12000.0,
            "endtime": 16995.0,
            "pickupsuff": "0000000010",},
        },
        {"deltat": 999,
        "ntimesteps": 10,
        "expected": {},
        },
    ],
)
def test_setup_change_deltat_no_start_end(config, data, case):

    restartdir = labdir / 'archive' / 'restarts'

    # Set a restart directory in config
    config['restart'] = str(restartdir)
    write_config(config)

    # deltaT which is not a divisor. Set ntimesteps instead of
    # start and end times
    data['parm03']['deltat'] = case['deltat']
    data['parm03']['ntimesteps'] = case['ntimesteps']

    make_config_files(data)

    res_fnames = make_pickup_names(10)

    make_restarts(res_fnames)

    # Run setup
    payu_setup(lab_path=str(labdir))

    mitgcm_restart = {}
    mitgcm_restart['endtime'] = 12000.

    with (restartdir / 'mitgcm.res.yaml').open('w') as file:
        yaml.dump(mitgcm_restart, file)

    if case['ntimesteps'] == 10:
        # This should throw an error, as it would overwrite the existing
        # pickup files in the work directory, as the nIter is the same
        # matchstr = '.*not integer multiple.*'
        matchstr = '.*Timestep at end identical to previous pickups.*'
        with pytest.raises(SystemExit, match=matchstr) as setup_error:
            payu_setup(lab_path=str(labdir))
        assert setup_error.type == SystemExit
        return

    payu_setup(lab_path=str(labdir))

    data_local = f90nml.read(workdir/'data')

    assert data_local['parm03']['nIter0'] == case['expected']['nIter0']
    assert data_local['parm03']['deltaT'] == case['expected']['deltaT']
    assert data_local['parm03']['basetime'] == case['expected']['basetime']
    assert data_local['parm03']['starttime'] == case['expected']['starttime']
    assert data_local['parm03']['endtime'] == case['expected']['endtime']
    assert data_local['parm03']['pickupsuff'] == case['expected']['pickupsuff']


@pytest.mark.parametrize(
    "case",
    [
        {"deltat": 1200,
        "expected": {"nIter0": 10,
                    "deltaT": 1200.0,
                    "starttime": 12000.0,
                    "endtime": 24000.0,},
        },
        {"deltat": 600,
        "expected": {"nIter0": 20,
                    "deltaT": 600.0,
                    "starttime": 12000.0,
                    "endtime": 24000.0,},
        },
        {"deltat": 2400.0, #should raise error
        "expected": {"nIter0": None,
                    "deltaT": None,
                    "starttime": None,
                    "endtime": None,},
        },
    ],
)
def test_setup_change_deltat_no_ntimesteps(config, data, case):
    restartdir = labdir / 'archive' / 'restarts'

    # Set a restart directory in config
    config['restart'] = str(restartdir)
    write_config(config)

    data['parm03']['deltat'] = case['deltat']
    del data['parm03']['ntimesteps']
    data['parm03']['starttime'] = 0.
    data['parm03']['endtime'] = 12000.

    make_config_files(data)
    res_fnames = make_pickup_names(10)
    make_restarts(res_fnames)

    # Run setup
    payu_setup(lab_path=str(labdir))

    mitgcm_restart = {}
    mitgcm_restart['endtime'] = 12000.

    with (restartdir / 'mitgcm.res.yaml').open('w') as file:
        yaml.dump(mitgcm_restart, file)

    if case['deltat'] == 2400.:
        # This should throw an error, as it would overwrite the existing
        # pickup files in the work directory, as the nIter is the same
        matchstr = '.*Timestep at end identical to previous pickups.*'
        with pytest.raises(SystemExit, match=matchstr) as setup_error:
            payu_setup(lab_path=str(labdir))
        assert setup_error.type == SystemExit
        return

    payu_setup(lab_path=str(labdir))

    data_local = f90nml.read(workdir/'data')

    assert data_local['parm03']['nIter0'] == case['expected']['nIter0']
    assert data_local['parm03']['deltaT'] == case['expected']['deltaT']
    assert data_local['parm03']['starttime'] == case['expected']['starttime']
    assert data_local['parm03']['endtime'] == case['expected']['endtime']


@pytest.mark.parametrize(
    "case",
    [
        {"deltat": 600,
        "ntimesteps": 10,
        "expected": {"nIter0": 20,
                    "nTimeSteps": 10,
                    "deltaT": 600.0,
                    "starttime": 12000.0,
                    "endtime": 18000.0,},
        },
        {"deltat": 2400,
        "ntimesteps": 10,
        "expected": {"nIter0": 5,
                    "nTimeSteps": 10,
                    "deltaT": 2400.0,
                    "starttime": 12000.0,
                    "endtime": 36000.0,},
        },
        {"deltat": 0.001,
        "ntimesteps": 12000000,
        "expected": {"nIter0": 12000000,
                    "nTimeSteps": 12000000,
                    "deltaT": 0.001,
                    "starttime": 12000.0,
                    "endtime": 24000.0,},
        },
    ],
)
def test_setup_change_deltat(config, data, case):

    restartdir = labdir / 'archive' / 'restarts'

    # Set a restart directory in config
    config['restart'] = str(restartdir)
    write_config(config)

    # Halve deltat
    data['parm03']['deltat'] = case['deltat']
    data['parm03']['ntimesteps'] = case['ntimesteps']
    make_config_files(data)

    res_fnames = make_pickup_names(10)

    make_restarts(res_fnames)

    # Run setup
    payu_setup(lab_path=str(labdir))

    mitgcm_restart = {}
    mitgcm_restart['endtime'] = 12000.

    with (restartdir / 'mitgcm.res.yaml').open('w') as file:
        yaml.dump(mitgcm_restart, file)

    payu_setup(lab_path=str(labdir))

    data_local = f90nml.read(workdir/'data')

    # Time step has halved, so nIter0 is doubled
    assert data_local['parm03']['nIter0'] == case['expected']['nIter0']
    assert data_local['parm03']['nTimeSteps'] == case['expected']['nTimeSteps']
    assert data_local['parm03']['deltaT'] == case['expected']['deltaT']
    assert data_local['parm03']['starttime'] == case['expected']['starttime']
    assert data_local['parm03']['endtime'] == case['expected']['endtime']
