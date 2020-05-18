import copy
import os
from pathlib import Path
import pdb
import shutil

import f90nml
import pytest
import yaml

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
data = {
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


def make_config_files():
    """
    Create files required for test model
    """

    f90nml.namelist.Namelist(data).write(ctrldir/'data', force=True)


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
        make_all_files()
    except Exception as e:
        print(e)

    write_config(config)


def teardown_module(module):
    """
    Put any test-wide teardown code in here, e.g. removing test outputs
    """
    if verbose:
        print("teardown_module   module:%s" % module.__name__)

    try:
        # shutil.rmtree(tmpdir)
        print('removing tmp')
    except Exception as e:
        print(e)


def make_pickup_names(istep):

    return ['pickup.{:010d}.001.001.{}'.format(istep, type)
            for type in ['data', 'meta']]


def test_make_pickup_names():
    assert(make_pickup_names(10) == ['pickup.0000000010.001.001.data',
                                     'pickup.0000000010.001.001.meta'])

# These are integration tests. They have an undesirable dependence on each
# other. It would be possible to make them independent, but then they'd
# be reproducing previous "tests", like init. So this design is deliberate
# but compromised. It means when running an error in one test can cascade
# and cause other tests to fail.
#
# Unfortunate but there you go.


def test_init():

    # Initialise a payu laboratory
    with cd(ctrldir):
        payu_init(None, None, str(labdir))

    # Check all the correct directories have been created
    for subdir in ['bin', 'input', 'archive', 'codebase']:
        assert((labdir / subdir).is_dir())


def test_setup():

    # Create some input and executable files
    make_inputs()
    make_exe()

    bindir = labdir / 'bin'
    exe = config['exe']

    make_config_files()

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


def test_setup_restartdir():

    restartdir = labdir / 'archive' / 'restarts'

    # Set a restart directory in config
    config['restart'] = str(restartdir)
    write_config(config)

    res_fnames = make_pickup_names(10)

    make_restarts(res_fnames)

    mitgcm_restart = {}
    mitgcm_restart['endtime'] = 12000.

    with (restartdir / 'mitgcm.res.yaml').open('w') as file:
        file.write(yaml.dump(mitgcm_restart, default_flow_style=False))

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


def test_setup_change_deltat():

    global data

    # Halve deltat
    data['parm03']['deltat'] = 600

    make_config_files()

    payu_setup(lab_path=str(labdir))

    data_local = f90nml.read(workdir/'data')

    # Time step has halved, so nIter0 is doubled
    assert data_local['parm03']['nIter0'] == 20
    assert data_local['parm03']['nTimeSteps'] == 10
    assert data_local['parm03']['deltaT'] == 600.
    assert data_local['parm03']['starttime'] == 12000.
    assert data_local['parm03']['endtime'] == 18000.

    # Double deltaT
    data['parm03']['deltat'] = 2400.

    make_config_files()

    payu_setup(lab_path=str(labdir))

    data_local = f90nml.read(workdir/'data')

    # Time step has halved, so nIter0 is doubled
    assert data_local['parm03']['nIter0'] == 5
    assert data_local['parm03']['nTimeSteps'] == 10
    assert data_local['parm03']['deltaT'] == 2400.
    assert data_local['parm03']['starttime'] == 12000.
    assert data_local['parm03']['endtime'] == 36000.

    # Fractional deltaT
    data['parm03']['deltat'] = 0.001
    data['parm03']['ntimesteps'] = 12000000

    make_config_files()

    payu_setup(lab_path=str(labdir))

    data_local = f90nml.read(workdir/'data')

    # Time step has halved, so nIter0 is doubled
    assert data_local['parm03']['nIter0'] == 12000000
    assert data_local['parm03']['nTimeSteps'] == 12000000
    assert data_local['parm03']['deltaT'] == 0.001
    assert data_local['parm03']['starttime'] == 12000.
    assert data_local['parm03']['endtime'] == 24000.

    # Use start and end time instead of ntimesteps. Normal
    # deltaT
    data['parm03']['deltat'] = 1200.
    del data['parm03']['ntimesteps']
    data['parm03']['starttime'] = 0.
    data['parm03']['endtime'] = 12000.

    make_config_files()

    payu_setup(lab_path=str(labdir))

    data_local = f90nml.read(workdir/'data')

    # Time step normal so nIter0 is 10, but no ntimesteps,
    # instead startime and endtime have been altered
    assert data_local['parm03']['nIter0'] == 10
    assert data_local['parm03']['deltaT'] == 1200.
    assert data_local['parm03']['starttime'] == 12000.
    assert data_local['parm03']['endtime'] == 24000.

    # Halve deltaT
    data['parm03']['deltat'] = 600

    make_config_files()

    payu_setup(lab_path=str(labdir))

    data_local = f90nml.read(workdir/'data')

    # Time step has halved, so nIter0 is doubled
    assert data_local['parm03']['nIter0'] == 20
    assert data_local['parm03']['deltaT'] == 600.
    assert data_local['parm03']['starttime'] == 12000.
    assert data_local['parm03']['endtime'] == 24000.

    # Double deltaT
    data['parm03']['deltat'] = 2400.

    make_config_files()

    # This should throw an error, as it would overwrite the existing
    # pickup files in the work directory, as the nIter is the same
    matchstr = '.*Timestep at end identical to previous pickups.*'
    with pytest.raises(SystemExit, match=matchstr) as setup_error:
        payu_setup(lab_path=str(labdir))
    assert setup_error.type == SystemExit

    # deltaT which is not a divisor. Set ntimesteps instead of
    # start and end times
    data['parm03']['deltat'] = 999.
    data['parm03']['ntimesteps'] = 5.
    del data['parm03']['starttime']
    del data['parm03']['endtime']

    make_config_files()

    payu_setup(lab_path=str(labdir))

    data_local = f90nml.read(workdir/'data')

    # Time step has halved, so nIter0 is doubled
    assert data_local['parm03']['nIter0'] == 0
    assert data_local['parm03']['deltaT'] == 999.
    assert data_local['parm03']['basetime'] == 12000.
    assert data_local['parm03']['starttime'] == 12000.
    assert data_local['parm03']['endtime'] == 16995.
    assert data_local['parm03']['pickupsuff'] == '0000000010'

    # Make same number of timesteps as previous, which should throw
    # an error
    data['parm03']['ntimesteps'] = 10.

    make_config_files()

    # This should throw an error, as it would overwrite the existing
    # pickup files in the work directory, as the nIter is the same
    # matchstr = '.*not integer multiple.*'
    matchstr = '.*Timestep at end identical to previous pickups.*'
    with pytest.raises(SystemExit, match=matchstr) as setup_error:
        payu_setup(lab_path=str(labdir))
    assert setup_error.type == SystemExit
