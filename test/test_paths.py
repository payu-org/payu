import os
from pathlib import Path
import shutil

import pdb
import pytest
import yaml

import payu

from payu.laboratory import Laboratory
from payu.schedulers.pbs import find_mounts


from .common import cd, make_random_file, get_manifests
from .common import tmpdir, ctrldir, labdir, workdir
from .common import config, sweep_work, payu_init, payu_setup
from .common import write_config
from .common import make_exe, make_inputs, make_restarts, make_all_files

verbose = True


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

    write_config(config)


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


def test_laboratory_basepath():

    # Test instantiating a Laboratory object
    with cd(ctrldir):
        lab = Laboratory(None, None, None)

        assert(Path(lab.basepath).parts[0] == '..')
        assert(Path(lab.basepath).parts[2] == 'lab')

    # Set a PROJECT env variable to get reproducible paths
    os.environ['PROJECT'] = 'x00'

    # Repeat, but remove shortpath definition
    # in config, so will fall through to default
    # depending on platform
    del(config['shortpath'])
    write_config(config)
    with cd(ctrldir):
        lab = Laboratory(None, None, None)

        shortpath = '.'
        for path in ['/short', '/scratch']:
            if Path(path).exists():
                shortpath = path
                break

        assert(list(Path(lab.basepath).parents)[2] == Path(shortpath))
        assert(Path(lab.basepath).parts[-3] == os.environ['PROJECT'])
        assert(Path(lab.basepath).parts[-1] == 'lab')

def test_laboratory_path():

    # Set a PROJECT env variable to get reproducible paths
    os.environ['PROJECT'] = 'x00'

    # Set a relative laboratory name
    labname = 'testlab'
    config['laboratory'] = labname
    write_config(config)
    with cd(ctrldir):
        lab = Laboratory(None, None, None)

        shortpath = '.'
        for path in ['/short', '/scratch']:
            if Path(path).exists():
                shortpath = path
                break

        assert(Path(lab.basepath).parts[-1] == labname)
