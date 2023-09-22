import copy
import shutil
import re

import pytest

import payu

from test.common import cd
from test.common import tmpdir, ctrldir, labdir
from test.common import config as config_orig
from test.common import write_config
from test.common import make_all_files
from test.common import remove_expt_archive_dirs
from test.models.test_mom import make_ocean_restart_files

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
    remove_expt_archive_dirs(dir_type='restart')


@pytest.mark.parametrize(
    "restart_freq, restart_history, expected_pruned_restarts_indices",
    [
        ("1MS", 1, []),
        ("2MS", 5, [1, 3, 5, 7, 9, 11, 13, 15, 17, 19]),
        ("12MS",
         1,
         [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11,
          13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23]),
        ("1YS",
         1,
         [1, 2, 3, 4, 5, 6, 7, 8, 9, 10,
          12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22]),
        (1, 1, []),
        (5, 5, [1, 2, 3, 4, 6, 7, 8, 9, 11, 12, 13, 14, 16, 17, 18, 19])
    ])
def test_prune_restarts(restart_freq,
                        restart_history,
                        expected_pruned_restarts_indices):

    # Create 2 years + 1 month worth of mom restarts directories
    # with 1 month runtimes - starting from 1900/02/01 to 1902/02/01
    # e.g   (run_date, restart_directory)
    # (1900/02/01, restart000)
    # (1900/03/01, restart001)
    #  ...
    # (1902/02/01, restart024)
    restart_dts = []
    for year in [1900, 1901, 1902]:
        for month in range(1, 13):
            if (year == 1900 and month == 1) or (year == 1902 and month > 2):
                # Ignore the first date and dates from 1902/03/01 onwards
                continue
            restart_dts.append([year, month, 1, 0, 0, 0])

    make_ocean_restart_files(
        init_dt_array=[1900, 1, 1, 0, 0, 0],
        run_dt_arrays=restart_dts,
        calendar=4,
        additional_path='ocean')

    # Set up config
    test_config = config
    test_config['model'] = 'access-om2'
    test_config['submodels'] = [
        {'name': 'atmosphere', 'model': 'yatm'},
        {'name': 'ocean', 'model': 'mom'}
    ]
    test_config['restart_freq'] = restart_freq
    test_config['restart_history'] = restart_history
    write_config(test_config)

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)

        # Function to test
        restarts_to_prune = expt.prune_restarts()

    # Extract out index from the full paths
    restarts_to_prune_indices = [
        int(re.search("[0-9]+$", restart_path).group())
        for restart_path in restarts_to_prune
    ]

    assert restarts_to_prune_indices == expected_pruned_restarts_indices
