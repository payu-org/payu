import cftime
import datetime
import pytest

from payu.calendar import parse_date_offset, DatetimeOffset
from payu.calendar import seconds_between_dates, int_to_date
from payu.calendar import runtime_from_date
from payu.calendar import GREGORIAN, NOLEAP

SEC_PER_DAY = 24*60*60


@pytest.mark.parametrize(
    "offset, initial_dt, expected",
    [
        (
            "5YS",
            cftime.datetime(year=2000, month=10, day=31,
                            hour=10, minute=5, second=2,
                            calendar="noleap"),
            cftime.datetime(year=2005, month=1, day=1, calendar="noleap"),
        ),
        (
            "1YS",
            cftime.datetime(year=1700, month=2, day=15,
                            hour=11, minute=5, second=2,
                            calendar="proleptic_gregorian"),
            cftime.datetime(year=1701, month=1, day=1,
                            calendar="proleptic_gregorian"),
        ),
        (
            "20YS",
            cftime.datetime(year=2200, month=2, day=30,
                            hour=1, minute=4, second=20,
                            calendar="360_day"),
            cftime.datetime(year=2220, month=1, day=1, calendar="360_day"),
        ),
    ],
)
def test_year_start_date_offset_add_to_datetime(offset, initial_dt, expected):
    date_offset = parse_date_offset(offset)
    next_dt = date_offset.add_to_datetime(initial_dt)

    assert next_dt == expected


@pytest.mark.parametrize(
    "offset, initial_dt, expected",
    [
        (
            "5MS",
            cftime.datetime(year=2000, month=10, day=1,
                            hour=10, minute=5, second=2,
                            calendar="noleap"),
            cftime.datetime(year=2001, month=3, day=1, calendar="noleap"),
        ),
        (
            "13MS",
            cftime.datetime(year=1500, month=10, day=30,
                            hour=10, minute=5, second=2,
                            calendar="360_day"),
            cftime.datetime(year=1501, month=11, day=1, calendar="360_day"),
        ),
        (
            "24MS",
            cftime.datetime(year=2200, month=1, day=1, calendar="gregorian"),
            cftime.datetime(year=2202, month=1, day=1, calendar="gregorian"),
        ),
    ],
)
def test_month_start_date_offset_add_to_datetime(offset, initial_dt, expected):
    date_offset = parse_date_offset(offset)
    next_dt = date_offset.add_to_datetime(initial_dt)

    assert next_dt == expected


@pytest.mark.parametrize(
    "offset, initial_dt, expected",
    [
        (
            "100S",
            cftime.datetime(year=2000, month=10, day=31,
                            hour=10, minute=5, second=2,
                            calendar="julian"),
            cftime.datetime(year=2000, month=10, day=31,
                            hour=10, minute=6, second=42,
                            calendar="julian"),
        ),
        (
            "25H",
            cftime.datetime(year=1500, month=10, day=30,
                            hour=10, minute=5, second=2,
                            calendar="360_day"),
            cftime.datetime(year=1500, month=11, day=1,
                            hour=11, minute=5, second=2,
                            calendar="360_day")
        ),
        (
            "3W",
            cftime.datetime(year=2200, month=1, day=1),
            cftime.datetime(year=2200, month=1, day=22),
        ),
        (
            "4T",
            cftime.datetime(
                year=2200, month=1, day=1, hour=0, minute=0, second=0
            ),
            cftime.datetime(
                year=2200, month=1, day=1, hour=0, minute=4, second=0
            ),
        ),
        (
            "30D",
            cftime.datetime(year=2200, month=2, day=1,  calendar="noleap"),
            cftime.datetime(year=2200, month=3, day=3, calendar="noleap"),
        ),
    ],
)
def test_timedelta_date_offset_add_to_datetime(offset, initial_dt, expected):
    # Week, Day, Minute, Hour, Second offsets
    date_offset = parse_date_offset(offset)
    next_dt = date_offset.add_to_datetime(initial_dt)

    assert next_dt == expected


def test_date_offset_add_to_datetime_invalid_dt():
    initial_dt = "stringInput"
    datetime_offset = DatetimeOffset(unit="YS", magnitude=2)

    with pytest.raises(TypeError) as exc_info:
        datetime_offset.add_to_datetime(initial_dt)

    expected_error = (
        "Invalid initial datetime type: <class 'str'>. "
        "Expected type: cftime.datetime"
    )
    assert str(exc_info.value) == expected_error


def test_date_offset_unsupported_offset():
    with pytest.raises(ValueError) as exc_info:
        DatetimeOffset(unit="Y", magnitude=2)

    expected_error = (
        "Unsupported datetime offset: Y. "
        "Supported offsets: YS, MS, W, D, H, T, S"
    )
    assert str(exc_info.value) == expected_error


def test_parse_date_offset_no_offset_magnitude():
    with pytest.raises(ValueError) as exc_info:
        parse_date_offset("YS")

    expected_error = "No numerical value given for offset: YS"
    assert str(exc_info.value) == expected_error


@pytest.mark.parametrize(
        "start_date, end_date, caltype_int, expected",
        [
            (
                datetime.datetime(year=4, month=1, day=1),
                datetime.datetime(year=5, month=1, day=1),
                GREGORIAN,
                366 * SEC_PER_DAY
            ),
            (
                datetime.datetime(year=4, month=1, day=1),
                datetime.datetime(year=5, month=1, day=1),
                NOLEAP,
                365 * SEC_PER_DAY
            ),
            (
                datetime.datetime(year=300, month=1, day=1),
                datetime.datetime(year=301, month=1, day=1),
                GREGORIAN,
                365 * SEC_PER_DAY
            ),
            (
                datetime.datetime(year=400, month=1, day=1),
                datetime.datetime(year=400, month=12, day=31),
                GREGORIAN,
                365 * SEC_PER_DAY
            ),
            (
                datetime.datetime(year=12, month=7, day=22),
                datetime.datetime(year=23, month=3, day=15),
                GREGORIAN,
                (10 * 365 + 238) * SEC_PER_DAY
            ),
            (
                datetime.datetime(year=1, month=1, day=1),
                datetime.datetime(year=9999, month=1, day=1),
                GREGORIAN,
                (9998 * 365 + 2424) * SEC_PER_DAY
            )
        ]
)
def test_seconds_between_dates(start_date, end_date, caltype_int, expected):
    assert seconds_between_dates(start_date, end_date, caltype_int) == expected


@pytest.mark.parametrize(
        "date_int, expected",
        [
            (10101, datetime.date(1, 1, 1)),
            (100321, datetime.date(10, 3, 21)),
            (99991231, datetime.date(9999, 12, 31))
        ]
)
def test_int_to_date(date_int, expected):
    """
    Check that integers typically read in from namelists
    are correctly converted to datetime.date objects.
    """
    converted_date = int_to_date(date_int)
    assert converted_date == expected


@pytest.mark.parametrize(
        "bad_date_int",
        [0, 100000000, 101, -5, 11119153]
)
def test_int_to_date_failures(bad_date_int):
    """
    Check that int_to_date does not allow non existent
    or out of range dates.
    """
    with pytest.raises(ValueError):
        int_to_date(bad_date_int)


@pytest.mark.parametrize(
        "start_date, years, months, days, seconds, caltype, expected",
        [
            # Normal year
            (datetime.date(101, 1, 1), 1, 0, 0, 0, GREGORIAN, 365*SEC_PER_DAY),
            (datetime.date(101, 1, 1), 1, 0, 0, 0, NOLEAP, 365*SEC_PER_DAY),
            # Leap year
            (datetime.date(4, 1, 1), 1, 0, 0, 0, GREGORIAN, 366*SEC_PER_DAY),
            (datetime.date(4, 1, 1), 1, 0, 0, 0, NOLEAP, 365*SEC_PER_DAY),
            # Non-leap year due to 100 year rule
            (datetime.date(100, 1, 1), 1, 0, 0, 0, GREGORIAN, 365*SEC_PER_DAY),
            (datetime.date(100, 1, 1), 1, 0, 0, 0, NOLEAP, 365*SEC_PER_DAY),
            # Leap year due to 400 year rule
            (datetime.date(400, 1, 1), 1, 0, 0, 0, GREGORIAN, 366*SEC_PER_DAY),
            (datetime.date(500, 1, 1), 1, 0, 0, 0, NOLEAP, 365*SEC_PER_DAY),
            # February in leap years
            (datetime.date(40, 2, 8), 0, 1, 0, 0, GREGORIAN, 29*SEC_PER_DAY),
            (datetime.date(40, 2, 8), 0, 1, 0, 0, NOLEAP, 28*SEC_PER_DAY),
            # Misc
            (datetime.date(1, 1, 1), 0, 0, 0, 86400,
             GREGORIAN, 86400),
            # Max & min limits
            (datetime.date(1, 1, 1), 9998, 11, 30, 0,
             NOLEAP, (9998 * 365 + 364) * SEC_PER_DAY),
            (datetime.date(1, 1, 1), 9998, 11, 30, 0,
             GREGORIAN, (9998 * 365 + 2424 + 364) * SEC_PER_DAY),
            (datetime.date(1, 1, 1), 0, 0, 0, 1,
             GREGORIAN, 1),
            (datetime.date(1, 1, 1), 0, 0, 0, 1,
             NOLEAP, 1),
        ]
)
def test_runtime_from_date(
        start_date,
        years,
        months,
        days,
        seconds,
        caltype,
        expected):
    """
    Test that the number of seconds calculated for run lengths is correct.
    """
    runtime = runtime_from_date(start_date,
                                years,
                                months,
                                days,
                                seconds,
                                caltype)

    assert runtime == expected
