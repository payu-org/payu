import cftime
import pytest

from payu.calendar import parse_date_offset, DatetimeOffset


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
