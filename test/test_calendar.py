import datetime

import cftime
import pytest

from payu.calendar import parse_date_offset, DatetimeOffset

def assert_add_date_offset(initial_dt, test_data):
    """Arguments:
        - initial_dt - initial datetime,
        - test_data which dictionary mapping date-offset strings to expected datetime values"""
    for date_offset_str, expected_next_dt in test_data.items():
        date_offset = parse_date_offset(date_offset_str)

        next_dt = date_offset.add_to_datetime(initial_dt)
        
        assert next_dt == expected_next_dt


def test_date_offset_add_to_datetime_cftime_no_leap():
    # "noleap" cftime calendar
    initial_dt = cftime.datetime(year=2000, month=10, day=31, hour=10, minute=5, second=2,
                                 calendar='noleap')

    test_data = {
        '5Y': cftime.datetime(year=2005, month=10, day=31, hour=10, minute=5, second=2,
                                 calendar='noleap'),
        '5YS': cftime.datetime(year=2005, month=1, day=1, hour=0, minute=0, second=0,
                                 calendar='noleap'),
        '5M': cftime.datetime(year=2001, month=3, day=31, hour=10, minute=5, second=2,
                              calendar='noleap'),
        '5MS': cftime.datetime(year=2001, month=3, day=1, hour=0, minute=0, second=0,
                               calendar='noleap'),
        '4M': cftime.datetime(year=2001, month=2, day=28, hour=10, minute=5, second=2,
                              calendar='noleap')
    }

    assert_add_date_offset(initial_dt, test_data)


def test_date_offset_add_to_datetime_cftime_all_leap():
    # "all_leap" cftime calendar 
    initial_dt = cftime.datetime(year=2000, month=10, day=31, hour=10, minute=5, second=2,
                                 calendar='all_leap')

    test_data = {
        '5Y': cftime.datetime(year=2005, month=10, day=31, hour=10, minute=5, second=2,
                                 calendar='all_leap'),
        '5YS': cftime.datetime(year=2005, month=1, day=1, hour=0, minute=0, second=0,
                                 calendar='all_leap'),
        '5M': cftime.datetime(year=2001, month=3, day=31, hour=10, minute=5, second=2,
                              calendar='all_leap'),
        '5MS': cftime.datetime(year=2001, month=3, day=1, hour=0, minute=0, second=0,
                               calendar='all_leap'),
        '4M': cftime.datetime(year=2001, month=2, day=29, hour=10, minute=5, second=2,
                              calendar='all_leap')
    }

    assert_add_date_offset(initial_dt, test_data)


def test_date_offset_add_to_datetime_cftime_360_day():
    # "360_day" cftime calendar 
    initial_dt = cftime.datetime(year=2000, month=10, day=30, hour=10, minute=5, second=2,
                                 calendar='360_day')

    test_data = {
        '5Y': cftime.datetime(year=2005, month=10, day=30, hour=10, minute=5, second=2,
                                 calendar='360_day'),
        '5YS': cftime.datetime(year=2005, month=1, day=1, calendar='360_day'),
        '5M': cftime.datetime(year=2001, month=3, day=30, hour=10, minute=5, second=2,
                              calendar='360_day'),
        '5MS': cftime.datetime(year=2001, month=3, day=1, calendar='360_day')
    }

    assert_add_date_offset(initial_dt, test_data)

def test_date_offset_add_to_datetime_standard():
    # Standard datetime and cftime standard calendar 
    initial_dts = [
        cftime.datetime(year=2000, month=10, day=31, hour=10, minute=5, second=2,
                                 calendar='standard'),
        datetime.datetime(year=2000, month=10, day=31, hour=10, minute=5, second=2)
    ]

    test_data = {
        '5Y': datetime.datetime(year=2005, month=10, day=31, hour=10, minute=5, second=2),
        '5YS': datetime.datetime(year=2005, month=1, day=1),
        '5M': datetime.datetime(year=2001, month=3, day=31, hour=10, minute=5, second=2),
        '5MS': datetime.datetime(year=2001, month=3, day=1)
    }

    for initial_dt in initial_dts:
        assert_add_date_offset(initial_dt, test_data)


def test_date_offset_add_to_datetime_unsupported_calendar():
    # Currently Julian calendar isn't supported for Y, M offsets
    initial_dt = cftime.datetime(year=2000, month=10, day=31, hour=10, minute=5, second=2,
                                 calendar='julian')
    
    for unit in ['Y', 'M']:
        datetime_offset = DatetimeOffset(unit=unit, magnitude=1)
        with pytest.raises(ValueError) as exc_info:
            datetime_offset.add_to_datetime(initial_dt)
        
        assert str(exc_info.value) == f"Calendar type julian is unsupported for given date offset {unit}"


def test_date_offset_add_to_datetime_invalid_dt():
    initial_dt = "stringInput"
    
    datetime_offset = DatetimeOffset(unit='Y', magnitude=2)
    with pytest.raises(TypeError) as exc_info:
        datetime_offset.add_to_datetime(initial_dt)
    
    expected_error = "Invalid initial datetime type: <class 'str'>. Expected types: cftime.datetime or datetime.datetime"
    assert str(exc_info.value) == expected_error
      

def test_date_offset_add_to_datetime_using_timedelta():
    initial_dt = datetime.datetime(year=2000, month=10, day=31, hour=10, minute=5, second=2)

    test_data = {
        "100S": datetime.datetime(year=2000, month=10, day=31, hour=10, minute=6, second=42),
        "2H": datetime.datetime(year=2000, month=10, day=31, hour=12, minute=5, second=2),
        "3W": datetime.datetime(year=2000, month=11, day=21, hour=10, minute=5, second=2),
        "4T": datetime.datetime(year=2000, month=10, day=31, hour=10, minute=9, second=2),
        "5D": datetime.datetime(year=2000, month=11, day=5, hour=10, minute=5, second=2)
    }

    assert_add_date_offset(initial_dt, test_data)