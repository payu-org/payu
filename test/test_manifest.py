import os
from pathlib import Path
import shutil

import pytest
import yaml

import payu

import pdb

# Namespace clash if import setup_cmd.runcmd as setup. For
# consistency use payu_ prefix for all commands
from payu.subcommands.init_cmd import runcmd as payu_init
from payu.subcommands.setup_cmd import runcmd as payu_setup_orignal
from payu.subcommands.sweep_cmd import runcmd as payu_sweep

import payu.models.test

from common import cd, make_random_file, get_manifests


verbose = True

tmpdir = Path().cwd() / Path('test') / 'tmp'
ctrldir = tmpdir / 'ctrl'
labdir = tmpdir / 'lab'
workdir = ctrldir / 'work'

print(tmpdir)
print(ctrldir)
print(labdir)

config = {
            'shortpath': '..',
            'laboratory': 'lab',
            'queue': 'normal',
            'project': 'aa30',
            'walltime': '0:30:00',
            'ncpus': 64,
            'mem': '64GB',
            'jobname': 'testrun',
            'model': 'test',
            'exe': 'test.exe',
            'input': 'testrun_1',
            'manifest': {
                        'scaninputs': False,
                        'reproduce': {
                                        'input': False,
                                        'exe': False
                                        }
                        }
            }


def sweep_work(hard_sweep=False):
    # Sweep workdir
    with cd(ctrldir):
        payu_sweep(model_type=None,
                   config_path=None,
                   hard_sweep=hard_sweep,
                   lab_path=str(labdir))


def payu_setup(model_type=None,
               config_path=None,
               lab_path=None,
               force_archive=None,
               reproduce=None):
    """
    Wrapper around original setup command to provide default arguments
    and run in ctrldir
    """
    with cd(ctrldir):
        payu_sweep(model_type=None,
                   config_path=None,
                   hard_sweep=False,
                   lab_path=str(labdir))
        payu_setup_orignal(model_type,
                           config_path,
                           lab_path,
                           force_archive,
                           reproduce)


def write_config():
    with (ctrldir / 'config.yaml').open('w') as file:
        file.write(yaml.dump(config, default_flow_style=False))


def make_exe():
    # Create a fake executable file
    bindir = labdir / 'bin'
    bindir.mkdir(parents=True, exist_ok=True)
    exe = config['exe']
    exe_size = 199
    make_random_file(bindir/exe, exe_size)


def make_inputs():
    # Create some fake input files
    inputdir = labdir / 'input' / config['input']
    inputdir.mkdir(parents=True, exist_ok=True)
    for i in range(1, 4):
        make_random_file(inputdir/'input_00{i}.bin'.format(i=i),
                         1000**2 + i)


def make_restarts():
    # Create some fake restart files
    restartdir = labdir / 'archive' / 'restarts'
    restartdir.mkdir(parents=True, exist_ok=True)
    for i in range(1, 4):
        make_random_file(restartdir/'restart_00{i}.bin'.format(i=i),
                         5000**2 + i)


def make_all_files():
    make_inputs()
    make_exe()
    make_restarts()


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
    except Exception as e:
        print(e)

    write_config()


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

    config_files = payu.models.test.config_files
    for file in config_files:
        make_random_file(ctrldir/file, 29)

    # Run setup
    payu_setup(lab_path=str(labdir))

    assert(workdir.is_symlink())
    assert(workdir.is_dir())
    assert((workdir/exe).resolve() == (bindir/exe).resolve())
    workdirfull = workdir.resolve()

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
    write_config()

    make_restarts()

    manifests = get_manifests(ctrldir/'manifests')
    payu_setup(lab_path=str(labdir))

    # Manifests should not match, as have added restarts
    assert(not manifests == get_manifests(ctrldir/'manifests'))


def test_exe_reproduce():

    # Set reproduce exe to True
    config['manifest']['reproduce']['exe'] = True
    write_config()
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
    write_config()

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
    write_config()

    # Run setup with changed exe but reproduce exe set to False
    payu_setup(lab_path=str(labdir))

    # Check manifests have changed as expected
    assert(not manifests == get_manifests(ctrldir/'manifests'))


def test_input_reproduce():

    inputdir = labdir / 'input' / config['input']
    inputdir.mkdir(parents=True, exist_ok=True)

    # Set reproduce input to True
    config['manifest']['reproduce']['exe'] = False
    config['manifest']['reproduce']['input'] = True
    write_config()
    manifests = get_manifests(ctrldir/'manifests')

    # Run setup with unchanged input reproduce input set to True
    # to make sure works with no changes
    payu_setup(lab_path=str(labdir))
    assert(manifests == get_manifests(ctrldir/'manifests'))

    # Delete input directory from config, should still work from
    # manifest with input reproduce True
    input = config['input']
    write_config()
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
    write_config()

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
    write_config()
    payu_setup(lab_path=str(labdir))


def test_input_scaninputs():

    inputdir = labdir / 'input' / config['input']
    inputdir.mkdir(parents=True, exist_ok=True)

    # Set scaninputs input to True
    config['manifest']['scaninputs'] = True
    write_config()

    # Run setup with unchanged input
    payu_setup(lab_path=str(labdir))
    manifests = get_manifests(ctrldir/'manifests')

    # Set scaninputs input to False
    config['manifest']['scaninputs'] = False
    write_config()

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
    write_config()

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
    write_config()
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
    write_config()

    # Run setup with modified restarts reproduce set to False
    payu_setup(lab_path=str(labdir))

    # Manifests should have changed
    assert(not manifests == get_manifests(ctrldir/'manifests'))


def test_all_reproduce():

    # Remove reproduce options from config
    del(config['manifest']['reproduce'])
    write_config()

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


def test_hard_sweep():

    # Sweep workdir
    sweep_work(hard_sweep=True)

    # Check all the correct directories have been removed
    assert(not (labdir / 'archive' / 'ctrl').is_dir())
    assert(not (labdir / 'work' / 'ctrl').is_dir())
