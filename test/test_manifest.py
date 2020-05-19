import copy
import os
from pathlib import Path
import pdb
import pytest
import shutil
import yaml

import payu
import payu.models.test

from .common import cd, make_random_file, get_manifests
from .common import tmpdir, ctrldir, labdir, workdir
from .common import sweep_work, payu_init, payu_setup
from .common import config as config_orig
from .common import write_config
from .common import make_exe, make_inputs, make_restarts, make_all_files

verbose = True

config = copy.deepcopy(config_orig)

def make_config_files():
    """
    Create files required for test model
    """

    config_files = payu.models.test.config_files
    for file in config_files:
        make_random_file(ctrldir/file, 29)


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

    config_files = payu.models.test.config_files

    for f in config_files + ['config.yaml']:
        assert((workdir/f).is_file())

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

    make_restarts()

    manifests = get_manifests(ctrldir/'manifests')
    payu_setup(lab_path=str(labdir))

    # Manifests should not match, as have added restarts
    assert(not manifests == get_manifests(ctrldir/'manifests'))


def test_exe_reproduce():

    # Set reproduce exe to True
    config['manifest']['reproduce']['exe'] = True
    write_config(config)
    manifests = get_manifests(ctrldir/'manifests')

    # Run setup with unchanged exe but reproduce exe set to True.
    # Should run without error
    payu_setup(lab_path=str(labdir))

    assert(manifests == get_manifests(ctrldir/'manifests'))

    bindir = labdir / 'bin'
    exe = config['exe']

    # Update the modification time of the executable, should run ok
    (bindir/exe).touch()

    # Run setup with changed exe but reproduce exe set to False
    payu_setup(lab_path=str(labdir))

    # Manifests will have changed as fasthash is altered
    assert(not manifests == get_manifests(ctrldir/'manifests'))

    # Reset manifests "truth"
    manifests = get_manifests(ctrldir/'manifests')

    # Delete exe path from config, should get it from manifest
    del(config['exe'])
    write_config(config)

    # Run setup with changed exe but reproduce exe set to False
    payu_setup(lab_path=str(labdir))

    # Manifests will not have changed
    assert(manifests == get_manifests(ctrldir/'manifests'))
    assert((workdir/exe).resolve() == (bindir/exe).resolve())

    # Reinstate exe path
    config['exe'] = exe

    # Recreate fake executable file
    make_exe()

    # Run setup again, which should raise an error due to changed executable
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        # Run setup with unchanged exe but reproduce exe set to True
        payu_setup(lab_path=str(labdir))

        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1

    # Change reproduce exe back to False
    config['manifest']['reproduce']['exe'] = False
    write_config(config)

    # Run setup with changed exe but reproduce exe set to False
    payu_setup(lab_path=str(labdir))

    # Check manifests have changed as expected
    assert(not manifests == get_manifests(ctrldir/'manifests'))

    # Reset manifests "truth"
    manifests = get_manifests(ctrldir/'manifests')

    # Make exe in config.yaml unfindable by giving it a non-existent
    # path but crucially the same name as the proper executable
    config['exe'] = '/bogus/test.exe'

    # Change reproduce exe back to True
    config['manifest']['reproduce']['exe'] = True

    write_config(config)

    # Run setup with changed exe but reproduce exe set to True. Should
    # work fine as the exe path is in the manifest
    payu_setup(lab_path=str(labdir))

    assert(manifests == get_manifests(ctrldir/'manifests'))


def test_input_reproduce():

    inputdir = labdir / 'input' / config['input']
    inputdir.mkdir(parents=True, exist_ok=True)

    # Set reproduce input to True
    config['manifest']['reproduce']['exe'] = False
    config['manifest']['reproduce']['input'] = True
    config['exe'] = config_orig['exe']
    write_config(config)
    manifests = get_manifests(ctrldir/'manifests')

    # Run setup with unchanged input reproduce input set to True
    # to make sure works with no changes
    payu_setup(lab_path=str(labdir))
    assert(manifests == get_manifests(ctrldir/'manifests'))

    # Delete input directory from config, should still work from
    # manifest with input reproduce True
    input = config['input']
    write_config(config)
    del(config['input'])

    # Run setup, should work
    payu_setup(lab_path=str(labdir))

    assert(manifests == get_manifests(ctrldir/'manifests'))

    # Update modification times for input files
    for i in range(1, 4):
        (inputdir/'input_00{i}.bin'.format(i=i)).touch()

    # Run setup, should work as only fasthash will differ, code then
    # checks full hash and updates fasthash if fullhash matches
    payu_setup(lab_path=str(labdir))

    # Manifests should no longer match as fasthashes have been updated
    assert(not manifests == get_manifests(ctrldir/'manifests'))

    # Reset manifest "truth"
    manifests = get_manifests(ctrldir/'manifests')

    # Re-create input files. Have to set input path for this purpose
    # but not written to config.yaml, so doesn't affect payu commands
    config['input'] = input
    make_inputs()
    del(config['input'])

    # Run setup again, which should raise an error due to changed inputs
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        payu_setup(lab_path=str(labdir))

        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1

    # Change reproduce input back to False
    config['manifest']['reproduce']['input'] = False
    write_config(config)

    # Run setup with changed inputs but reproduce input set to False
    payu_setup(lab_path=str(labdir))

    # Check manifests have changed as expected and input files
    # linked in work
    assert(not manifests == get_manifests(ctrldir/'manifests'))
    for i in range(1, 4):
        assert((workdir/'input_00{i}.bin'.format(i=i)).is_file())

    # Reset manifest "truth"
    manifests = get_manifests(ctrldir/'manifests')

    # Delete input manifest
    (ctrldir/'manifests'/'input.yaml').unlink()

    # Setup with no input dir and no manifest. Should work ok
    payu_setup(lab_path=str(labdir))

    # Check there are no linked inputs
    for i in range(1, 4):
        assert(not (workdir/'input_00{i}.bin'.format(i=i)).is_file())

    # Set input path back and recreate input manifest
    config['input'] = input
    write_config(config)
    payu_setup(lab_path=str(labdir))


def test_input_scaninputs():

    # Re-create input files
    make_config_files()
    make_inputs()

    inputdir = labdir / 'input' / config['input']
    inputdir.mkdir(parents=True, exist_ok=True)

    # Set scaninputs input to True
    config['manifest']['scaninputs'] = True
    write_config(config)

    # Run setup with unchanged input
    payu_setup(lab_path=str(labdir))
    manifests = get_manifests(ctrldir/'manifests')

    # Set scaninputs input to False
    config['manifest']['scaninputs'] = False
    write_config(config)

    # Run setup, should work and manifests unchanged
    payu_setup(lab_path=str(labdir))
    assert(manifests == get_manifests(ctrldir/'manifests'))

    # Update modification times for input files
    for i in range(1, 4):
        (inputdir/'input_00{i}.bin'.format(i=i)).touch()

    # Run setup, should work as only fasthash will differ, code then
    # checks full hash and updates fasthash if fullhash matches
    payu_setup(lab_path=str(labdir))

    # Manifests should no longer match as fasthashes have been updated
    assert(not manifests == get_manifests(ctrldir/'manifests'))

    # Reset manifest "truth"
    manifests = get_manifests(ctrldir/'manifests')

    # Re-create input files
    make_inputs()

    # Run setup again. Should be fine, but manifests changed
    payu_setup(lab_path=str(labdir))
    assert(not manifests == get_manifests(ctrldir/'manifests'))

    # Reset manifest "truth"
    manifests = get_manifests(ctrldir/'manifests')

    # Make a new input file
    (inputdir/'lala').touch()

    # Run setup again. Should be fine, manifests unchanged as
    # scaninputs=False
    payu_setup(lab_path=str(labdir))
    assert(manifests == get_manifests(ctrldir/'manifests'))

    # Set scaninputs input to True
    config['manifest']['scaninputs'] = True
    write_config(config)

    # Run setup again. Should be fine, but manifests changed now
    # as scaninputs=False
    payu_setup(lab_path=str(labdir))
    assert(not manifests == get_manifests(ctrldir/'manifests'))
    assert((workdir/'lala').is_file())

    # Delete silly input file
    (inputdir/'lala').unlink()

    # Re-run after removing silly input file
    payu_setup(lab_path=str(labdir))

    # Reset manifest "truth"
    manifests = get_manifests(ctrldir/'manifests')


def test_restart_reproduce():

    # Set reproduce restart to True
    config['manifest']['reproduce']['input'] = False
    config['manifest']['reproduce']['restart'] = True
    del(config['restart'])
    write_config(config)
    manifests = get_manifests(ctrldir/'manifests')

    # Run setup with unchanged restarts
    payu_setup(lab_path=str(labdir))
    assert(manifests == get_manifests(ctrldir/'manifests'))

    restartdir = labdir / 'archive' / 'restarts'
    # Change modification times on restarts
    for i in range(1, 4):
        (restartdir/'restart_00{i}.bin'.format(i=i)).touch()

    # Run setup with touched restarts, should work with modified
    # manifest
    payu_setup(lab_path=str(labdir))

    # Manifests should have changed
    assert(not manifests == get_manifests(ctrldir/'manifests'))

    # Reset manifest "truth"
    manifests = get_manifests(ctrldir/'manifests')

    # Modify restart files
    make_restarts()

    # Run setup again, which should raise an error due to changed restarts
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        # Run setup with unchanged exe but reproduce exe set to True
        payu_setup(lab_path=str(labdir))

    # Set reproduce restart to False
    config['manifest']['reproduce']['restart'] = False
    write_config(config)

    # Run setup with modified restarts reproduce set to False
    payu_setup(lab_path=str(labdir))

    # Manifests should have changed
    assert(not manifests == get_manifests(ctrldir/'manifests'))


def test_all_reproduce():

    # Remove reproduce options from config
    del(config['manifest']['reproduce'])
    write_config(config)

    # Run setup
    payu_setup(lab_path=str(labdir))

    manifests = get_manifests(ctrldir/'manifests')

    make_all_files()

    # Run setup with reproduce=True, which should raise an error as
    # all files changed
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        # Run setup with unchanged exe but reproduce exe set to True
        payu_setup(lab_path=str(labdir), reproduce=True)

    # Run setup
    payu_setup(lab_path=str(labdir))

    # Manifests should have changed
    assert(not manifests == get_manifests(ctrldir/'manifests'))


def test_get_all_fullpaths():

    make_all_files()
    make_config_files()

    # Run setup
    payu_setup(lab_path=str(labdir))

    manifests = get_manifests(ctrldir/'manifests')

    sweep_work()

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)
        expt.setup()
        files = expt.manifest.get_all_fullpaths()

    allfiles = []
    for mf in manifests:
        for f in manifests[mf]:
            allfiles.append(manifests[mf][f]['fullpath'])

    assert(set(files) == set(allfiles))


def test_get_hashes():

    make_all_files()
    make_config_files()

    # Run setup
    payu_setup(lab_path=str(labdir))

    manifests = get_manifests(ctrldir/'manifests')

    sweep_work()

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)
        expt.setup()
        hashes = expt.manifest.manifests['input'].get_hashes('md5')

    allhashes = []
    for f in manifests['input.yaml']:
        allhashes.append(manifests['input.yaml'][f]['hashes']['md5'])

    assert(set(hashes) == set(allhashes))


def test_set_hash():

    # Revert to original config
    config = copy.deepcopy(config_orig)
    write_config(config)

    make_all_files()
    make_config_files()

    # Run setup
    payu_setup(lab_path=str(labdir))

    manifests = get_manifests(ctrldir/'manifests')

    sweep_work()

    # Remove existing manifests. Don't support changing
    # hashes and retaining manifests
    shutil.rmtree(ctrldir/'manifests')

    # Change full hash from md5 to sha256
    config['manifest']['fullhash'] = 'sha256'
    write_config(config)

    # Run setup
    payu_setup(lab_path=str(labdir))

    assert(not manifests == get_manifests(ctrldir/'manifests'))

    manifests = get_manifests(ctrldir/'manifests')

    for mf in manifests:
        for f in manifests[mf]:
            assert(manifests[mf][f]['hashes']['sha256'])
            assert(len(manifests[mf][f]['hashes']['sha256']) == 64)

    sweep_work()

    # Remove existing manifests. Don't support changing
    # hashes and retaining manifests
    shutil.rmtree(ctrldir / 'manifests')

    # Change full hash from md5 to binhash
    config['manifest']['fullhash'] = 'binhash'
    write_config(config)

    # Run setup
    payu_setup(lab_path=str(labdir))

    manifests = get_manifests(ctrldir/'manifests')

    for mf in manifests:
        for f in manifests[mf]:
            assert(list(manifests[mf][f]['hashes'].keys()) == ['binhash'])

def test_hard_sweep():

    # Sweep workdir
    sweep_work(hard_sweep=True)

    # Check all the correct directories have been removed
    assert(not (labdir / 'archive' / 'ctrl').is_dir())
    assert(not (labdir / 'work' / 'ctrl').is_dir())
