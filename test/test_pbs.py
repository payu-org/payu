import argparse
from argparse import Namespace
import copy
import os
from pathlib import Path
import shutil
import sys
from unittest.mock import patch

import pdb
import pytest
import yaml

import payu

from payu.fsops import read_config
from payu.laboratory import Laboratory
from payu.schedulers import pbs
from payu.schedulers import index as scheduler_index

from .common import cd, make_random_file, get_manifests
from .common import tmpdir, ctrldir, labdir, workdir, payudir
from .common import sweep_work, payu_init, payu_setup
from .common import config as original_config
from .common import write_config
from .common import make_exe, make_inputs, make_restarts
from .common import make_payu_exe, make_all_files

verbose = True

config = copy.deepcopy(original_config)


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
        payudir.mkdir()
        make_payu_exe()
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


def test_encode_mount():

    assert(pbs.encode_mount('/test/a') == 'testa')
    assert(pbs.encode_mount('test/a') == 'testa')
    assert(pbs.encode_mount('test/b') == 'testb')


def test_make_mount_string():

    assert(pbs.make_mount_string('testa', 'x00') == 'testa/x00')


def test_find_mounts():

    paths = ['/f/data/x00/', '/tmp/y11/']
    mounts = ['/f/data', '/tmp']

    assert(pbs.find_mounts(paths, mounts) == set(['fdata/x00', 'tmp/y11']))

    # Only return where a match is found
    mounts = ['/f/data']

    assert(pbs.find_mounts(paths, mounts) == set(['fdata/x00', ]))

    # Test with more mounts than there are paths
    paths = ['/f/data/x00/']
    mounts = ['/f/data', '/tmp']

    assert(pbs.find_mounts(paths, mounts) == set(['fdata/x00', ]))

    # Test with duplicate paths
    paths = ['/f/data/x00/', '/f/data/x00/']
    mounts = ['/f/data', '/tmp']

    assert(pbs.find_mounts(paths, mounts) == set(['fdata/x00', ]))

    # Test with longer path
    paths = ['/f/data/x00/fliberty/gibbet', ]
    mounts = ['/f/data', '/tmp']

    assert(pbs.find_mounts(paths, mounts) == set(['fdata/x00', ]))

    # Test without leading slash
    paths = ['f/data/x00/fliberty/gibbet', ]
    mounts = ['f/data', '/tmp']

    assert(pbs.find_mounts(paths, mounts) == set(['fdata/x00', ]))

    # Test without leading slash
    paths = ['/f/data/x00', ]
    mounts = ['f/data', ]

    assert(pbs.find_mounts(paths, mounts) == set())

    # Test without trailing slash
    paths = ['/f/data/x00', ]
    mounts = ['/f/data', ]

    assert(pbs.find_mounts(paths, mounts) == set(['fdata/x00', ]))

    # Test legacy naming that allows for extra characters at the
    # end of mount path
    paths = ['/f/data1a/x00', ]
    mounts = ['/f/data', ]

    assert(pbs.find_mounts(paths, mounts) == set(['fdata/x00', ]))


def test_run():

    # Use new mechanism to return a scheduler
    sched_name = config.get('scheduler', 'pbs')
    sched_type = scheduler_index[sched_name]
    sched = sched_type()

    # Monkey patch pbs_env_init as we don't have a
    # functioning PBS install in travis
    payu.schedulers.pbs.pbs_env_init = lambda: True

    payu.schedulers.pbs.check_exe_path = lambda x, y: y

    # payu_path = os.path.join(os.environ['PWD'], 'bin')
    payu_path = payudir / 'bin'
    # create new path for payu_path to check a000 picked up as storage
    payu_path = Path('/f/data/a000/some/path')
    pbs_vars = {'PAYU_PATH': str(payu_path)}
    # A pretend python interpreter string
    python_exe = '/f/data/m000/python/bin/python'

    # Test pbs generating a PBS command
    with cd(ctrldir):

        payu_cmd = 'payu-run'

        config['storage'] = {}
        config['storage']['test'] = ['x00']
        config['storage']['/f/data'] = ['x00']

        config['control_path'] = '/f/data/xyz999/experiment'
        config['laboratory'] = '/f/data/c000/blah'
        config['shortpath'] = '/f/data/y00'

        config['modules'] = {}
        config['modules']['use'] = ['/f/data/mm01', '/f/data/mm02/test/modules']

        cmd = sched.submit(payu_cmd, config, pbs_vars, python_exe)

        print(cmd)

        # Create test parser
        parser = argparse.ArgumentParser(description='Test')

        # Add the arguments
        parser.add_argument('-q', type=str, required=True)
        parser.add_argument('-P', type=str, required=True)
        parser.add_argument('-N', type=str, required=True)
        parser.add_argument('-v', metavar='KEY-VALUE',
                            nargs='+', required=True)
        parser.add_argument('-j', type=str, required=True)
        parser.add_argument('-l', metavar='KEY=VALUE',
                            nargs='+', action='append', required=True)
        parser.add_argument('remaining', nargs=argparse.REMAINDER)

        args = parser.parse_args(cmd.split()[1:])

        assert(args.N == config['jobname'])
        assert(args.P == config['project'])
        assert(args.q == config['queue'])

        resources = []
        for resource in args.l:
            resources.extend(resource)

        other_resources = {'wd': True}

        resources_found = {}
        for resource in resources:
            try:
                k, v = resource.split('=')
            except ValueError:
                k, v = (resource, True)
            resources_found[k] = v

        # Check all resources specified in config are correct
        for resource in ['walltime', 'ncpus', 'mem']:
            assert(resources_found[resource] == str(config[resource]))

        assert(resources_found['storage'] ==
               ('fdata/a000+fdata/c000+fdata/m000+fdata/mm01+fdata/mm02+' +
                'fdata/x00+fdata/xyz999+fdata/y00+test/x00'))

        # Check other auto-added resources are present
        for resource in other_resources:
            assert(other_resources[resource] == resources_found[resource])

        env = {}
        for env_var in args.v:
            k, v = env_var.split('=')
            env[k] = v

        assert('PAYU_PATH' in env)
        assert(env['PAYU_PATH'] == str(payu_path))

        assert(args.remaining[-2].endswith('python'))
        assert(args.remaining[-1].endswith(payu_cmd))


@patch("payu.schedulers.pbs.pbs_env_init", return_value=True)
@patch("payu.schedulers.pbs.check_exe_path", side_effect=lambda x, y: y)
@pytest.mark.parametrize(
    "env_exists,file_exists,file_exe,expected_cmd",
    [
        # Test backwards compatibility with no launcher script
        (False, False, False, "/path/to/python payu-run"),
        # With only launcher script env set
        (True, False, False, "/path/to/python payu-run"),
        # With launch script env and file exists
        (True, True, False, "/path/to/python payu-run"),
        # With launch script env, file exists, and file is executable
        (True, True, True, "{tmp_path}/launcher.sh /path/to/python payu-run")
    ],
)
def test_submit_launcher_script_setting(
    mock_pbs_env_init, mock_check_exe_path,
    env_exists, file_exists, file_exe, expected_cmd, tmp_path, monkeypatch
):
    config = {
        "control_path": "/path/to/experiment"
    }

    # Setup based on test parameters
    if env_exists:
        monkeypatch.setenv("ENV_LAUNCHER_SCRIPT_PATH",
                           f"{tmp_path}/launcher.sh")
    if file_exists:
        launcher_script_path = tmp_path / "launcher.sh"
        launcher_script_path.write_text("#!/bin/bash\necho 'Running...'\n")
        if file_exe:
            launcher_script_path.chmod(0o755)

    # Generate the qsub command
    pbs_cmd = pbs.PBS().submit("payu-run", config,
                               python_exe="/path/to/python")

    _, cmd = pbs_cmd.split("--")
    assert cmd.strip() == expected_cmd.format(tmp_path=tmp_path)


def test_tenacity():

    # This should fail and do nothing
    pbs.get_qstat_info()
