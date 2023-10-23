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
from test.common import make_expt_archive_dir, remove_expt_archive_dirs


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

    # Write config
    test_config = config
    test_config['model'] = 'mom'
    write_config(test_config)


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


def make_ocean_restart_dir(start_dt,
                           run_dt,
                           calendar,
                           restart_index=0,
                           additional_path=None):
    """Create tests restart directory with ocean_solo.res file"""
    # Create restart directory
    restart_path = make_expt_archive_dir(type='restart',
                                         index=restart_index,
                                         additional_path=additional_path)

    # Create ocean_solo.res file
    lines = (f"{calendar:6d}        "
             "(Calendar: no_calendar=0, thirty_day_months=1, julian=2, "
             "gregorian=3, noleap=4)\n")

    init_dt_desc = "Model start time:   year, month, day, hour, minute, second"
    lines += format_ocean_solo_datetime_line(start_dt, init_dt_desc)

    run_dt_desc = "Current model time: year, month, day, hour, minute, second"
    lines += format_ocean_solo_datetime_line(run_dt, run_dt_desc)

    ocean_solo_path = os.path.join(restart_path, "ocean_solo.res")
    with open(ocean_solo_path, "w") as ocean_solo_file:
        ocean_solo_file.write(lines)


def format_ocean_solo_datetime_line(dt_string, description):
    """Format datetime string to match actual output files"""
    dt_array = convert_date_string_to_array(dt_string)
    year, month, day, hour, minute, second = dt_array
    return (
        f"{year:6d}{month:6d}{day:6d}{hour:6d}{minute:6d}{second:6d}"
        f"        {description}\n"
    )


def convert_date_string_to_array(dt_string):
    """Convert string of YYYY-MM-DD hh:mm:ss to array of integers of
    [year, month, day, hour, minute, second] format"""
    date, time = dt_string.split(' ')
    year, month, day = map(int, date.split('-'))
    hour, minute, second = map(int, time.split(':'))
    return [year, month, day, hour, minute, second]


@pytest.mark.parametrize(
    "run_dt, calendar, expected_cftime",
    [
        (
            "1900-02-01 00:00:00",
            4,
            cftime.datetime(1900, 2, 1, calendar="noleap")
        ),
        (
            "1900-06-01 00:00:00",
            3,
            cftime.datetime(1900, 6, 1, calendar="proleptic_gregorian")
        ),
        (
            "1000-11-12 12:23:34",
            2,
            cftime.datetime(1000, 11, 12, 12, 23, 34,
                            calendar="julian")
        ),
        (
            "1900-02-30 00:00:00",
            1,
            cftime.datetime(1900, 2, 30, calendar="360_day")
        ),
    ])
def test_mom_get_restart_datetime(run_dt, calendar, expected_cftime):
    # Create 1 mom restart directory
    start_dt = "1900-01-01 00:00:00"
    make_ocean_restart_dir(start_dt, run_dt, calendar)

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)

    restart_path = list_expt_archive_dirs()[0]
    parsed_run_dt = expt.model.get_restart_datetime(restart_path)
    assert parsed_run_dt == expected_cftime
