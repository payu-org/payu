import copy
import shutil

import pytest

import payu

from test.common import cd
from test.common import tmpdir, ctrldir, labdir, expt_archive_dir
from test.common import config as config_orig
from test.common import write_config
from test.common import make_all_files
from test.common import remove_expt_archive_dirs, make_expt_archive_dir
from test.models.test_mom_mixin import make_ocean_restart_dir

verbose = True

# Global config
config = copy.deepcopy(config_orig)


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


@pytest.fixture(autouse=True)
def teardown():
    # Run test
    yield

    # Remove any created restart files
    remove_expt_archive_dirs(type='restart')

    # Remove experiment archive
    expt_archive_dir.rmdir()


def create_test_2Y_1_month_frequency_restarts():
    """Create 2 years + 1 month worth of mom restarts directories
    with 1 month runtimes - starting from 1900/02/01 to 1902/02/01
    e.g (run_date, restart_directory)
    (1900/02/01, restart000)
    (1900/03/01, restart001)
     ...
    (1902/02/01, restart024)"""
    restart_dts = []
    for year in [1900, 1901, 1902]:
        for month in range(1, 13):
            if (year == 1900 and month == 1) or (year == 1902 and month > 2):
                # Ignore the first date and dates from 1902/03/01 onwards
                continue
            restart_dts.append(f"{year}-{month}-01 00:00:00")

    for index, run_dt in enumerate(restart_dts):
        make_ocean_restart_dir(start_dt="1900-01-01 00:00:00",
                               run_dt=run_dt,
                               calendar=4,
                               restart_index=index,
                               additional_path='ocean')


def write_test_config(restart_freq=None, restart_history=None):
    test_config = copy.deepcopy(config)
    test_config['model'] = 'access-om2'
    test_config['submodels'] = [
        {'name': 'atmosphere', 'model': 'yatm'},
        {'name': 'ocean', 'model': 'mom'}
    ]
    if restart_freq:
        test_config['restart_freq'] = restart_freq
    if restart_history:
        test_config['restart_history'] = restart_history

    write_config(test_config)


@pytest.mark.parametrize(
    "restart_freq, restart_history, expected_pruned_restarts_indices",
    [
        ("1MS", None, []),
        ("2MS", None, [1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23]),
        ("2MS", 5, [1, 3, 5, 7, 9, 11, 13, 15, 17, 19]),
        ("12MS", None,
         [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11,
          13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23]),
        ("1YS", None,
         [1, 2, 3, 4, 5, 6, 7, 8, 9, 10,
          12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22]),
        (1, 1, []),
        (5, 3, [1, 2, 3, 4, 6, 7, 8, 9, 11, 12, 13, 14, 16, 17, 18, 19, 21]),
        (5, 7, [1, 2, 3, 4, 6, 7, 8, 9, 11, 12, 13, 14, 16, 17]),
        (5, None, [1, 2, 3, 4, 6, 7, 8, 9, 11, 12, 13, 14, 16, 17, 18, 19])
    ])
def test_force_prune_restarts(restart_freq,
                              restart_history,
                              expected_pruned_restarts_indices):
    # Test --force-prune-restarts with varying restart_freq and restart_history

    # Create restart files 1900/02/01-restart000 to 1902/02/01-restart024
    create_test_2Y_1_month_frequency_restarts()

    # Set up config
    write_test_config(restart_freq, restart_history)

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)

        # Function to test
        restarts_to_prune = expt.get_restarts_to_prune(force=True)

    # Extract out index
    restarts_to_prune_indices = [
        int(restart.lstrip('restart')) for restart in restarts_to_prune
    ]

    assert restarts_to_prune_indices == expected_pruned_restarts_indices


@pytest.mark.parametrize(
    "restarts, restart_freq, restart_history, expected_restart_indices",
    [
        ([
            (0, "1901-01-01 00:00:00"),
            (3, "1904-01-01 00:00:00"),
            (4, "1905-01-01 00:00:00"),
            (5, "1906-01-01 00:00:00"),
            (6, "1907-01-01 00:00:00")
        ], "3YS", None, [4, 5]),
        ([
            (0, "1901-01-01 00:00:00"),
            (3, "1904-01-01 00:00:00"),
            (4, "1905-01-01 00:00:00"),
            (5, "1906-01-01 00:00:00"),
            (6, "1907-01-01 00:00:00")
        ], "3YS", 2, [4]),
        ([
            (0, "1901-01-01 00:00:00"),
            (1, "1902-01-01 00:00:00"),
            (2, "1903-01-01 00:00:00"),
            (3, "1904-01-01 00:00:00"),
            (4, "1905-01-01 00:00:00")
        ], "2YS", 1, []),
        ([
            (0, "1901-01-01 00:00:00"),
            (1, "1902-01-01 00:00:00"),
            (2, "1903-01-01 00:00:00"),
            (3, "1904-01-01 00:00:00"),
            (4, "1905-01-01 00:00:00")
        ], "2YS", None, []),
        ([
            (0, "1901-01-01 00:00:00"),
            (2, "1903-01-01 00:00:00"),
            (3, "1904-01-01 00:00:00"),
        ], 2, None, []),
        ([
            (0, "1901-01-01 00:00:00"),
            (2, "1903-01-01 00:00:00"),
            (3, "1904-01-01 00:00:00"),
            (4, "1905-01-01 00:00:00"),
        ], 2, None, [3]),
        ([
            (2, "1903-01-01 00:00:00"),
            (4, "1905-01-01 00:00:00"),
            (6, "1907-01-01 00:00:00"),
            (8, "1909-01-01 00:00:00"),
        ], 4, None, []),
    ])
def test_prune_restarts(restarts,
                        restart_freq,
                        restart_history,
                        expected_restart_indices):
    # Create restart files
    for index, datetime in restarts:
        make_ocean_restart_dir(start_dt="1900-01-01 00:00:00",
                               run_dt=datetime,
                               calendar=4,
                               restart_index=index,
                               additional_path='ocean')

    # Set up config
    write_test_config(restart_freq, restart_history)

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)

        # Function to test - Note: with force=False which is default
        restarts_to_prune = expt.get_restarts_to_prune()

    # Extract out index
    restarts_to_prune_indices = [
        int(restart.lstrip('restart')) for restart in restarts_to_prune
    ]

    assert restarts_to_prune_indices == expected_restart_indices


def test_prune_restarts_ignores_empty_restart_dirs():
    # Test that in date-based restart pruning ignores any empty restart dirs

    write_test_config(restart_freq='1YS')

    # Create restart files
    restart_datetimes = [(4, "1903-01-01 00:00:00"),
                         (5, "1903-06-01 00:00:00"),
                         (6, "1905-01-01 00:00:00")]
    for index, datetime in restart_datetimes:
        make_ocean_restart_dir(start_dt="1900-01-01 00:00:00",
                               run_dt=datetime,
                               calendar=4,
                               restart_index=index,
                               additional_path='ocean')

    # Create empty restart dirs
    make_expt_archive_dir(type='restart', index=0)
    make_expt_archive_dir(type='restart', index=2)

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)

        # Function to test
        restarts_to_prune = expt.get_restarts_to_prune()

    # Extract out index
    restarts_to_prune_indices = [
        int(restart.lstrip('restart')) for restart in restarts_to_prune
    ]

    assert restarts_to_prune_indices == [5]


def test_restart_history_with_empty_archive():
    write_test_config(restart_history=3)
    expt_archive_dir.mkdir()

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)

        # Function to test
        restarts_to_prune = expt.get_restarts_to_prune()

    assert restarts_to_prune == []
