import copy
import os
import shutil

import pytest
import cftime

import payu

from test.common import cd
from test.common import tmpdir, ctrldir, labdir
from test.common import config as config_orig
from test.common import write_config
from test.common import make_all_files
from test.common import list_expt_archive_dirs
from test.common import make_expt_archive_dirs, remove_expt_archive_dirs


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


def make_ocean_restart_files(init_dt_array,
                             run_dt_arrays,
                             calendar,
                             additional_path=None):
    restart_paths = make_expt_archive_dirs(dir_type='restart',
                                           num_dirs=len(run_dt_arrays),
                                           additional_path=additional_path)

    for index, run_dt_array in enumerate(run_dt_arrays):
        # Create ocean_solo.res file
        make_ocean_solo_file(restart_paths[index],
                             init_dt_array,
                             run_dt_array,
                             calendar)


def make_ocean_solo_file(restart_path, init_dt_array, run_dt_array, calendar):
    "Create test ocean_solo.res files in restart directories"
    lines = (f"{calendar:6d}        "
             "(Calendar: no_calendar=0, thirty_day_months=1, julian=2, "
             "gregorian=3, noleap=4)\n")

    init_dt_desc = "Model start time:   year, month, day, hour, minute, second"
    lines += format_ocean_solo_datetime_line(init_dt_array, init_dt_desc)

    run_dt_desc = "Current model time: year, month, day, hour, minute, second"
    lines += format_ocean_solo_datetime_line(run_dt_array, run_dt_desc)

    ocean_solo_path = os.path.join(restart_path, "ocean_solo.res")
    with open(ocean_solo_path, "w") as ocean_solo_file:
        ocean_solo_file.write(lines)


def format_ocean_solo_datetime_line(dt_array, description):
    year, month, day, hour, minute, second = dt_array
    return (
        f"{year:6d}{month:6d}{day:6d}{hour:6d}{minute:6d}{second:6d}"
        f"        {description}\n"
    )


@pytest.mark.parametrize(
    "run_dt_arrays, calendar, expected_cftimes",
    [
        (
            [[1900, 2, 1, 0, 0, 0], [1900, 3, 1, 0, 0, 0]],
            4,
            [
                cftime.datetime(1900, 2, 1, calendar="noleap"),
                cftime.datetime(1900, 3, 1, calendar="noleap"),
            ],
        ),
        (
            [[1900, 6, 1, 0, 0, 0], [1901, 1, 1, 0, 0, 0]],
            3,
            [
                cftime.datetime(1900, 6, 1, calendar="proleptic_gregorian"),
                cftime.datetime(1901, 1, 1, calendar="proleptic_gregorian"),
            ],
        )
    ])
def test_mom_get_restart_datetime(run_dt_arrays, calendar, expected_cftimes):
    # Create mom restart files
    init_dt_array = [1900, 1, 1, 0, 0, 0]
    make_ocean_restart_files(init_dt_array, run_dt_arrays, calendar)

    # Write config
    test_config = config
    test_config['model'] = 'mom'
    write_config(test_config)

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)

    restart_paths = list_expt_archive_dirs(dir_type='restart')

    for index, expected_cftime in enumerate(expected_cftimes):
        restart_path = restart_paths[index]
        run_dt = expt.model.get_restart_datetime(restart_path)
        assert run_dt == expected_cftime
