import copy
import os
import shutil

from collections import namedtuple

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


# Mimic cftime.datetime objects in order to provide invalid dates
# to make_ocean_restart_dir
DateTuple = namedtuple("DateTuple", "year month day hour minute second calendar")


def make_ocean_restart_dir(start_dt,
                           run_dt,
                           restart_index=0,
                           additional_path=None):
    """Create tests restart directory with ocean_solo.res file"""
    if start_dt.calendar != run_dt.calendar:
        raise ValueError(f"Inconsistent calendars for start_dt: {start_dt.calendar}"
                         f" and run_dt: {run_dt.calendar}")
    calendar = run_dt.calendar

    cal_id = {
        "": 0,
        "360_day": 1,
        "julian": 2,
        "proleptic_gregorian": 3,
        "noleap": 4
    }

    try:
        cal_int = cal_id[calendar]
    except KeyError:
        # Allow for invalid calendars to be specified
        cal_int = calendar

    # Create restart directory
    restart_path = make_expt_archive_dir(type='restart',
                                         index=restart_index,
                                         additional_path=additional_path)

    # Create ocean_solo.res file
    lines = (f"{cal_int:6d}        "
             "(Calendar: no_calendar=0, thirty_day_months=1, julian=2, "
             "gregorian=3, noleap=4)\n")

    init_dt_desc = "Model start time:   year, month, day, hour, minute, second"
    lines += format_ocean_solo_datetime_line(start_dt, init_dt_desc)

    run_dt_desc = "Current model time: year, month, day, hour, minute, second"
    lines += format_ocean_solo_datetime_line(run_dt, run_dt_desc)

    ocean_solo_path = os.path.join(restart_path, "ocean_solo.res")
    with open(ocean_solo_path, "w") as ocean_solo_file:
        ocean_solo_file.write(lines)


def format_ocean_solo_datetime_line(dt, description):
    """Format datetime string to match actual output files"""
    return (
        f"{dt.year:6d}{dt.month:6d}{dt.day:6d}{dt.hour:6d}{dt.minute:6d}{dt.second:6d}"
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
    "run_dt",
    [
        cftime.datetime(1900, 2, 1, calendar="noleap"),
        cftime.datetime(1900, 6, 1, calendar="proleptic_gregorian"),
        cftime.datetime(1000, 11, 12, 12, 23, 34, calendar="julian"),
        cftime.datetime(1900, 2, 30, calendar="360_day"),
        cftime.datetime(1, 1, 1, calendar="noleap"),
        cftime.datetime(9999, 12, 31, calendar="noleap"),
        cftime.datetime(1, 1, 1, calendar="proleptic_gregorian"),
        cftime.datetime(9999, 12, 31, calendar="proleptic_gregorian"),
        cftime.datetime(1, 1, 1, calendar="julian"),
        cftime.datetime(9999, 12, 31, calendar="julian"),
        cftime.datetime(1, 1, 1, calendar="360_day"),
        cftime.datetime(9999, 12, 30, calendar="360_day")
    ])
def test_mom_get_restart_datetime(run_dt):
    # Create 1 mom restart directory
    start_dt = cftime.datetime(1900, 1, 1, calendar=run_dt.calendar)
    make_ocean_restart_dir(start_dt, run_dt)

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)

    restart_path = list_expt_archive_dirs()[0]
    parsed_run_dt = expt.model.get_restart_datetime(restart_path)
    assert parsed_run_dt == run_dt


@pytest.mark.parametrize(
    "run_dt,expected_error",
    [
        (DateTuple(1, 2, 31, 0, 0, 0, "proleptic_gregorian"),
         ValueError),  # Bad day of month
        (DateTuple(534, 13, 1, 0, 0, 0, "proleptic_gregorian"),
         ValueError),  # Bad month
        (DateTuple(1, 1, 1, 0, 0, 0, 21),
         KeyError),  # Bad calendar
        (DateTuple(1, 1, 1, 0, 0, 0, -1),
         KeyError)  # Bad calendar

    ])
def test_mom_bad_get_restart_datetime(run_dt, expected_error):
    """
    Test that get_restart_datetime fails when reading invalid dates.
    """
    # Create 1 mom restart directory
    start_dt = DateTuple(1900, 1, 1, 0, 0, 0, run_dt.calendar)
    make_ocean_restart_dir(start_dt, run_dt)

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)

    restart_path = list_expt_archive_dirs()[0]
    with pytest.raises(expected_error):
        expt.model.get_restart_datetime(restart_path)
