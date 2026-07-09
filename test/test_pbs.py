import argparse
from argparse import Namespace
import json
import copy
import os
from pathlib import Path
import re
import shutil
import sys
from unittest.mock import patch

import pdb
import pytest

import payu

from payu.fsops import read_config
from payu.laboratory import Laboratory
from payu.schedulers import pbs
from payu.schedulers import index as scheduler_index
from payu.schedulers.pbs import PBS
import payu.errors as errors

from .common import cd, make_random_file, get_manifests
from .common import tmpdir, ctrldir, labdir, workdir, payudir, archive_dir
from .common import sweep_work, payu_init, payu_setup
from .common import config as original_config
from .common import write_config
from .common import make_exe, make_inputs, make_restarts
from .common import make_payu_exe, make_all_files

verbose = True

config = copy.deepcopy(original_config)

test_storage_groups = ['x00', 'xyz999', 'y00', 'c000', 'mm02', 'm000', 'mm01', 'a000', 'tm70', 'aa30']


def _fake_pbsnodes_dict(nodes):
    """Build a pbsnodes -F json compatible payload."""
    return {"nodes": {name: {"resources_available": ra} for name, ra in nodes.items()}}

def test_get_queue_node_shape_picks_node_shape(monkeypatch):

    payload = _fake_pbsnodes_dict({
        # Matching topology clx
        "node001": {"topology": "cpu-clx", "ncpus": 48, "mem": "201326592KB"},  # 192GB
        "node002": {"topology": "cpu-clx", "ncpus": 48, "mem": "201326592KB"},  # 192GB
        # spr
        "node003": {"topology": "cpu-spr", "ncpus": 104, "mem": "536870912KB"},  # 512GB
        "node004": {"topology": "cpu-spr", "ncpus": 104, "mem": "536870912KB"},  # 512GB

        # Non-matching topology - should be ignored
        "node005": {"topology": "cpu-xyz", "ncpus": 12, "mem": "12582912KB"},  # 12GB
    })
    
    monkeypatch.setattr(pbs, "read_pbsnode_file", lambda: payload)

    ncpus, mem = pbs.PBS.get_queue_node_shape("normal")

    assert ncpus == 48
    assert mem == 192


def test_get_queue_node_shape_no_matching_topology(monkeypatch):

    payload = _fake_pbsnodes_dict({
        # Non-matching topology - should be ignored
        "node001": {"topology": "cpu-clx", "ncpus": 48, "mem": "201326592KB"},  # 192GB
        "node002": {"topology": "cpu-clx", "ncpus": 48, "mem": "201326592KB"},  # 192GB
    })

    monkeypatch.setattr(pbs, "read_pbsnode_file", lambda: payload)

    with pytest.raises(ValueError, match=r"No nodes matched"):
        pbs.PBS.get_queue_node_shape("normalsr")

@pytest.mark.parametrize("file_exist, timestamp, expected_rerun",
    [
        (True, 0, 1),  # No timestamp
        (True, 100, 1),  # Old timestamp
        (True, 9999999999, 0),  # Recent timestamp
        (False, 0, 1),  # File doesn't exist
    ]
)
def test_read_pbsnode_file_different_age(monkeypatch, file_exist, timestamp, expected_rerun):
    """ Test if read_pbsnodes_file will rerun given different aged `pbsnodes.json`. """
    payload = _fake_pbsnodes_dict({
        # Non-matching topology - should be ignored
        "node001": {"topology": "cpu-clx", "ncpus": 48, "mem": "201326592KB"},  # 192GB
        "node002": {"topology": "cpu-clx", "ncpus": 48, "mem": "201326592KB"},  # 192GB
    })

    # Create a fake pbsnodes.json file
    pbsnodes_json_path = archive_dir / "pbs" / "pbsnodes.json"
    pbsnodes_json_path.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv('PAYU_PBSNODES_CACHE', str(pbsnodes_json_path))
    if file_exist:
        data = {
            "timestamp": timestamp,
            "nodes": payload["nodes"]
        }
        with open(pbsnodes_json_path, "w") as f:
            json.dump(data, f)
    else:
        pbsnodes_json_path.unlink(missing_ok=True)

    # Set up a run counter
    run_counter = 0
    def fake_run(*args, **kwargs):
        nonlocal run_counter
        run_counter += 1
        return payload

    monkeypatch.setattr(pbs, "_run_pbsnodes_json", fake_run)
    pbs.PBS.get_queue_node_shape("normal")

    assert run_counter == expected_rerun

@pytest.mark.parametrize("pbsnode_cache, xdg_cache, home_dir, expected_path", 
    [
        # Test with only PAYU_PBSNODES_CACHE set
        (str(tmpdir / "pbs_cache" / "pbsnodes.json"), 
        None, 
        None, 
        tmpdir / "pbs_cache" / "pbsnodes.json"),

        # Test with only XDG_CACHE_HOME set
        (None, 
        str(tmpdir / "xdg_cache"), 
        None, 
        tmpdir / "xdg_cache" / "pbs" / "pbsnodes.json"),

        # Test with PAYU_PBSNODES_CACHE and XDG_CACHE_HOME set
        (str(tmpdir / "pbs_cache" / "pbsnodes.json"), 
        str(tmpdir / "xdg_cache"), 
        None, 
        tmpdir / "pbs_cache" / "pbsnodes.json"),

        # Test with neither set (should default to $HOME/.cache directory)
        (None, 
        None, 
        str(tmpdir), 
        tmpdir / ".cache" / "pbs" / "pbsnodes.json"),
    ]
)
def test_get_pbsnodes_cache_path(monkeypatch, pbsnode_cache, xdg_cache, home_dir, expected_path):
    """ Test if get_pbsnodes_cache_path returns the correct pbsnodes.json path """
    if pbsnode_cache:
        monkeypatch.setenv('PAYU_PBSNODES_CACHE', pbsnode_cache)
    else:
        monkeypatch.delenv('PAYU_PBSNODES_CACHE', raising=False)
    if xdg_cache:
        monkeypatch.setenv('XDG_CACHE_HOME', xdg_cache)
    else:
        monkeypatch.delenv('XDG_CACHE_HOME', raising=False)

    monkeypatch.setenv('HOME', home_dir)
    path = pbs.get_pbsnodes_cache_path()
    assert path == expected_path



def test_mem_convert_requires_kb_suffix():
    with pytest.raises(ValueError, match=r"not in kb format"):
        pbs.PBS._mem_convert_kb_to_gb("192GB")


def test_run_pbsnodes_json_timeout(monkeypatch):
    def fake_run(*args, **kwargs):
        raise pbs.subprocess.TimeoutExpired(cmd=kwargs.get("args", ["pbsnodes"]), timeout=kwargs.get("timeout", 1))

    monkeypatch.setattr(pbs.subprocess, "run", fake_run)

    with pytest.raises(errors.PayuRuntimeError, match=r"timed out"):
        pbs._run_pbsnodes_json(timeout=1)


def test_get_queue_walltime_hours_correct_boundaries():
    assert pbs.PBS.get_queue_walltime_hours("normal", 1) == 48
    assert pbs.PBS.get_queue_walltime_hours("normal", 672) == 48

    assert pbs.PBS.get_queue_walltime_hours("normal", 673) == 24
    assert pbs.PBS.get_queue_walltime_hours("normal", 1440) == 24

    assert pbs.PBS.get_queue_walltime_hours("normal", 1441) == 10
    assert pbs.PBS.get_queue_walltime_hours("normal", 2976) == 10

    assert pbs.PBS.get_queue_walltime_hours("normal", 2977) == 5
    assert pbs.PBS.get_queue_walltime_hours("normal", 20736) == 5


def test_get_queue_walltime_hours_unknown_queue():
    with pytest.raises(ValueError, match=r"Unknown queue"):
        pbs.PBS.get_queue_walltime_hours("nonexistent_queue", 1)


def test_get_queue_walltime_hours_exceeds_max_cpus():
    with pytest.raises(ValueError, match=r"exceed maximum.*normalsr.*10400"):
        pbs.PBS.get_queue_walltime_hours("normalsr", 10504)


@pytest.mark.parametrize(
    "walltime, expected_hours",
    [
        (3600, 1.0),
        (600, 1/6),

        # SS string format only
        ("05", 5/3600),

        # MM:SS
        ("10:00", 10/60),
        ("01:00", 1/60),

        # H:M:S
        ("1:0:0", 1.0),
        ("01:0:0", 1.0),
        ("1:30:00", 1.5),
        ("01:30:00", 1.5),
    ],
)
def test_parse_walltime_valid_inputs(walltime, expected_hours):
    assert pbs.PBS.parse_walltime(walltime) == pytest.approx(expected_hours)


@pytest.mark.parametrize(
    "walltime, limit, raise_error",
    [
        # valid
        ("1:00:00", 2, False),
        ("01:00:00", 1, False),
        ("01:30:00", 1, True),
        (3600, 2, False),
        ("10:00", 0.2, False),
        ("05", 0.01, False),
    ],
)
def test_validate_walltime_with_queue_limits(monkeypatch, walltime, limit, raise_error):
    # Patch get_queue_walltime_hours to avoid dependency on queue config
    def dummy_get_queue_walltime_hours(cls, queue, ncpus):
        return limit

    monkeypatch.setattr(pbs.PBS, "get_queue_walltime_hours",
                        classmethod(dummy_get_queue_walltime_hours)
                        )

    # two dummy variables
    queue = "normalsr"
    ncpus = 120

    if raise_error:
        with pytest.raises(errors.PayuConfigError):
            pbs.PBS.validate_walltime_with_queue_limits(walltime, queue, ncpus)
    else:
        pbs.PBS.validate_walltime_with_queue_limits(walltime, queue, ncpus)


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

@patch("payu.schedulers.pbs.get_user_groups", return_value=test_storage_groups)
# @patch("payu.schedulers.pbs.client")
def test_run(mock_get_user_groups):

    # Use new mechanism to return a scheduler
    sched_name = config.get('scheduler', 'pbs')
    sched_type = scheduler_index[sched_name]
    sched = sched_type()
    # mock_client.submit.return_value = "mock_pbs_job_id"

    payu.schedulers.pbs.check_exe_path = lambda x, y: y

    payu_path = payudir / 'bin'
    # create new path for payu_path to check a000 picked up as storage
    payu_path = Path('/f/data/a000/some/path')
    pbs_vars = {'PAYU_PATH': str(payu_path)}
    # A pretend python interpreter string
    python_exe = '/f/data/m000/python/bin/python'

    # Test pbs generating a PBS command
    with cd(ctrldir):
        job_script = payudir / 'payu-run'
        script_content = 'Running payu-run'
        with open(job_script, 'w') as f:
            f.write(script_content)

        config['storage'] = {}
        config['storage']['test'] = ['x00']
        config['storage']['/f/data'] = ['x00']

        config['control_path'] = '/f/data/xyz999/experiment'
        config['laboratory'] = '/f/data/c000/blah'
        config['shortpath'] = '/f/data/y00'

        config['modules'] = {}
        config['modules']['use'] = ['/f/data/mm01', '/f/data/mm02/test/modules']

        cmd = sched.submit(str(job_script), config, pbs_vars, python_exe, dry_run=True)
        print(f"Generated PBS command: {cmd}")

        with open(cmd.strip().split()[-1], 'r') as f:
            hpcpy_script_content = f.read()
        assert "payu-run" in hpcpy_script_content
        # assert python_exe in hpcpy_script_content
        assert f"-q {config['queue']}" in cmd
    
        assert f"-N {config['jobname']}" in cmd
        assert f"-P {config['project']}" in cmd
        assert f"-l wd" in cmd

        # Check all resources specified in config are correct
        for resource in ['walltime', 'ncpus', 'mem']:
            assert f"-l {resource}={config[resource]}" in cmd

        expected_storage = ['fdata/a000', 'fdata/c000', 'fdata/m000', 'fdata/mm01', 'fdata/mm02', 
                                'fdata/x00', 'fdata/xyz999', 'fdata/y00', 'test/x00']
        storage_in_cmd = re.search(f"storage=([^\s]+)", cmd).group(1).split('+')
        assert sorted(expected_storage) == sorted(storage_in_cmd)

        assert f" -v PAYU_PATH={payu_path}" in cmd
        assert f" -- {python_exe}" in cmd


@patch("payu.schedulers.pbs.check_exe_path", side_effect=lambda x, y: y)
@patch("payu.schedulers.pbs.get_user_groups", return_value=test_storage_groups)
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
    mock_check_exe_path, mock_get_user_groups,
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
                               python_exe="/path/to/python", dry_run=True)

    _, cmd = pbs_cmd.split("--")
    assert cmd.strip() == expected_cmd.format(tmp_path=tmp_path)


def test_tenacity():

    # This should fail and do nothing
    pbs.get_job_info_json()

def test_get_all_job_info(monkeypatch):
    """Test that get_all_job_info correctly parses the results."""
    fake_qstat = {
        "timestamp": "2026-03-03T10:00:00",
        "server": "pbs-server-01",
        "Jobs": {
            "12345": {
                "Job_Name": "test_job_1",
                "job_state": "Q",
            },
            "67890": {
                "Job_Name": "test_job_2",
                "job_state": "R",
            },
        },
    }
    expected = {
        "12345": {
            "timestamp": "2026-03-03T10:00:00",
            "server": "pbs-server-01",
            "Jobs": {
                "12345": {
                    "Job_Name": "test_job_1",
                    "job_state": "Q",
                }
            },
        },
        "67890": {
            "timestamp": "2026-03-03T10:00:00",
            "server": "pbs-server-01",
            "Jobs": {
                "67890": {
                    "Job_Name": "test_job_2",
                    "job_state": "R",
                }
            },
        },
    }

    monkeypatch.setattr(pbs, "get_job_info_json", lambda: fake_qstat)
    result = PBS().get_all_job_info()
    assert result == expected

@patch('os.getgroups')
@patch('grp.getgrgid')
def test_get_user_groups(mock_getgrgid, mock_getgroups):
    """Test that get_user_groups returns the correct list of groups."""
    mock_getgroups.return_value = [1000, 1001, 1002]

    # Create a mock for grp.getgrgid that returns {'gr_name': 'group{gid}'}
    mock_getgrgid.side_effect = lambda gid: type('grp_struct', (object,), {'gr_name': f'group{gid}'})

    assert pbs.get_user_groups() == ['group1000', 'group1001', 'group1002']


@patch('os.getgroups')
@patch('grp.getgrgid')
def test_get_user_groups_error(mock_getgrgid, mock_getgroups):
    """ Test that get_user_groups handles errors from grp.getgrgid."""
    mock_getgroups.return_value = [1000, 1001, 1002]
    mock_getgrgid.side_effect = KeyError("Groupid not found")

    with pytest.raises(errors.PayuRuntimeError, match=r"Error checking group membership for current user: 'Groupid not found'"):
        pbs.get_user_groups()


@pytest.mark.parametrize(
    "storages, user_groups, expected_denied",
    [
        ({"fdata/x00", "fdata/y00"}, ['x00', 'y00', 'z00'], []),  # All storages accessible
        ({"fdata/x00", "fdata/a00"}, ['x00', 'y00', 'z00'], ["fdata/a00"]),  # One storage denied
        ({"fdata/a00", "fdata/b00"}, ['x00', 'y00', 'z00'], ["fdata/a00", "fdata/b00"]),  # All storages denied
    ]
)
def test_check_storage_access(storages, user_groups, expected_denied):
    """Test that check_storage_access correctly identifies denied storages."""
    if len(expected_denied) > 0:
        with pytest.raises(errors.PayuRuntimeError, match="User is not a member of the following required storage projects") as exc_info:
            pbs.check_storage_access(storages, user_groups)
        for denied in expected_denied:
            assert denied in str(exc_info.value)

    else:
        # Test with all storages accessible
        pbs.check_storage_access(storages, user_groups)


@pytest.mark.parametrize(
    "pbs_mem, queue, n_cpus, raise_error",
    [   
        ("1TB", "normalsr", 48, True),  # Exceeds max memory for normalsr
        ("1300GB", "normalsr", 48, True),  # Exceeds max memory for normalsr
        ("100GB", "normalsr", 48, False),  # Valid memory
        ("100MB", "normalsr", 48, False),  # Valid memory
        ("0.1TB", "normalsr", 48, False),  # Valid memory
        ("100000", "normalsr", 48, False),  # Valid memory
        ("192GB", "normalsr", 48, False),  # Exactly at the limit for normalsr
        ("192GB", "normalsr", 20, False),  # Valid memory when requiring fewer CPUs than a node
        ("200GB", "normalsr", 55, False),  # n_cpus exceeds cpus_per_node, but memory is less than 2 nodes
        ("400GB", "normalsr", 55, True),  # n_cpus exceeds cpus_per_node and memory is over 2 nodes
    ]
)
@patch("payu.schedulers.pbs.PBS.get_queue_node_shape", return_value=(48, 192))
def test_validate_memory_with_queue_limits(mock_get_queue_node_shape, pbs_mem, queue, n_cpus, raise_error):
    """Test that an error is raised if the memory request exceeds queue limits."""
    if raise_error:
        with pytest.raises(errors.PayuConfigError, match=fr"You have requested more memory of {pbs_mem}"):
            PBS.validate_memory_with_queue_limits(pbs_mem, queue, n_cpus)
    elif pbs_mem == "100000":
        # Test with no unit suffix - should warn and assume bytes
        with pytest.warns(UserWarning, match=fr"Memory string '{pbs_mem}' has no unit suffix, assuming bytes."):
             PBS.validate_memory_with_queue_limits(pbs_mem, queue, n_cpus)
    else:
        # Test with valid memory request
        PBS.validate_memory_with_queue_limits(pbs_mem, queue, n_cpus)


@pytest.mark.parametrize(
    "pbs_mem",
    [   
        ("100GBs"),  # Invalid unit
        ("100 G"),  # Invalid format with space
        ("100BB"), # Not acceptable unit
    ]
)
@patch("payu.schedulers.pbs.PBS.get_queue_node_shape", return_value=(48, 192))
def test_validate_memory_with_queue_limits_format(mock_get_queue_node_shape, pbs_mem):
    """Test that an error is raised if the memory string format is invalid."""
    with pytest.raises(ValueError, match=fr"Memory string '{pbs_mem}' has invalid format, must end with PB, TB, GB, MB, KB, B, or no unit."):
        PBS.validate_memory_with_queue_limits(pbs_mem, "normalsr", 48) 