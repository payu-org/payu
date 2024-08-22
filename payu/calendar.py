import datetime
import re

from dateutil.relativedelta import relativedelta
import cftime

NOLEAP, GREGORIAN = range(2)


def int_to_date(date):
    """
    Convert an int of form yyyymmdd to a python date object.
    """

    year = date // 10**4
    month = date % 10**4 // 10**2
    day = date % 10**2

    return datetime.date(year, month, day)


def date_to_int(date):
    return date.year * 10**4 + date.month * 10**2 + date.day


def runtime_from_date(start_date, years, months, days, seconds, caltype):
    """
    Get the number of seconds from start date to start date + date_delta.

    Ignores Feb 29 for caltype == NOLEAP.
    """

    end_date = start_date + relativedelta(
        years=years, months=months, days=days
    )
    runtime = end_date - start_date

    if caltype == NOLEAP:
        runtime -= get_leapdays(start_date, end_date)

    return int(runtime.total_seconds() + seconds)


def date_plus_seconds(init_date, seconds, caltype):
    """
    Get a new_date = date + seconds.

    Ignores Feb 29 for no-leap days.
    """

    end_date = init_date + datetime.timedelta(seconds=seconds)

    if caltype == NOLEAP:
        end_date += get_leapdays(init_date, end_date)
        if end_date.month == 2 and end_date.day == 29:
            end_date += datetime.timedelta(days=1)

    return end_date


def get_leapdays(init_date, final_date):
    """
    Find the number of leap days between arbitrary dates. Returns a
    timedelta object.

    FIXME: calculate this instead of iterating.
    """

    curr_date = init_date
    leap_days = 0

    while curr_date != final_date:
        if curr_date.month == 2 and curr_date.day == 29:
            leap_days += 1

        curr_date += datetime.timedelta(days=1)

    return datetime.timedelta(days=leap_days)


def calculate_leapdays(init_date, final_date):
    """Currently unsupported, it only works for differences in years."""

    leap_days = (final_date.year - 1) // 4 - (init_date.year - 1) // 4
    leap_days -= (final_date.year - 1) // 100 - (init_date.year - 1) // 100
    leap_days += (final_date.year - 1) // 400 - (init_date.year - 1) // 400

    # TODO: Internal date correction (e.g. init_date is 1-March or later)

    return datetime.timedelta(days=leap_days)


# TODO: The caltype logic could be simplified if we switched
# to using just a string as the caltype input. Might require reworking of other
# functions for consistency.
def seconds_between_dates(start_date, end_date, caltype_int):
    """
    Calculate the number of seconds between two datetime objects
    with a specified calender type by using cftime datetime objects
    as intermiaries.

    Parameters
    ----------
    start_date: datetime.date
    end_date: datetime.date
    caltype: Integer, either GREGORIAN or NOLEAP

    Returns
    -------
    seconds: Number of seconds between start_date and end_date.
    """
    # Get the cftime string corresponding to the caltype integer

    # TODO: Is it confusing that GREGORIAN means proleptic gregorian?
    if caltype_int == GREGORIAN:
        calendar_str = "proleptic_gregorian"
    elif caltype_int == NOLEAP:
        calendar_str = "noleap"
    else:
        raise ValueError(f"Unrecognized caltype integer {caltype_int}")

    delta = (date_to_cftime(end_date, calendar_str)
             - date_to_cftime(start_date, calendar_str))

    return int(delta.total_seconds())


def date_to_cftime(date, calendar):
    """
    Convert a datetime.datetime object to a cftime.datetime object which
    has the same year, month, day, hour, minute, second values.

    Parameters
    ----------
    date: datetime.date object
    calendar: string specifying a valid cftime calendar type

    Returns
    -------
    date_cf: cftime.datetime object.
    """
    date_cf = cftime.datetime(
        year=date.year,
        month=date.month,
        day=date.day,
        hour=0,
        minute=0,
        second=0,
        calendar=calendar
    )

    return date_cf


def add_year_start_offset_to_datetime(initial_dt, n):
    """Return a cftime datetime at the start of the year, that is n years
    from the initial datetime"""
    return cftime.datetime(
        year=initial_dt.year + n,
        month=1,
        day=1,
        hour=0,
        minute=0,
        second=0,
        calendar=initial_dt.calendar,
    )


def add_month_start_offset_to_datetime(initial_dt, n):
    """Return a cftime datetime of the start of the month, that is n months
    from the initial datetime"""
    years_to_add = (initial_dt.month + n - 1) // 12
    months_to_add = n - years_to_add * 12

    return cftime.datetime(
        year=initial_dt.year + years_to_add,
        month=initial_dt.month + months_to_add,
        day=1,
        hour=0,
        minute=0,
        second=0,
        calendar=initial_dt.calendar,
    )


def add_timedelta_fn(timedelta):
    """Returns a function that takes initial datetime and multiplier n,
    and returns a datetime that is n * offset from the initial datetime"""
    return lambda initial_dt, n: initial_dt + n * timedelta


class DatetimeOffset:
    """A utility class for adding various time offsets to cftime datetimes.

    Parameters:
        unit (str): The unit of the time offset. Supported units are:
            - "YS" for years (start of the year)
            - "MS" for months (start of the month)
            - "W" for weeks
            - "D" for days
            - "H" for hours
            - "T" for minutes
            - "S" for seconds
        magnitude (int): The magnitude of the time offset.

    Methods:
        - `add_to_datetime(initial_dt: cftime.datetime) -> cftime.datetime`:
          Adds the specified time offset to the given cftime datetime and
          returns the resulting datetime.

    Attributes:
        - unit (str): The unit of the time offset.
        - magnitude (int): The magnitude of the time offset.
    """

    def __init__(self, unit, magnitude):
        supported_datetime_offsets = {
            "YS": add_year_start_offset_to_datetime,
            "MS": add_month_start_offset_to_datetime,
            "W": add_timedelta_fn(datetime.timedelta(weeks=1)),
            "D": add_timedelta_fn(datetime.timedelta(days=1)),
            "H": add_timedelta_fn(datetime.timedelta(hours=1)),
            "T": add_timedelta_fn(datetime.timedelta(minutes=1)),
            "S": add_timedelta_fn(datetime.timedelta(seconds=1)),
        }
        if unit not in supported_datetime_offsets:
            raise ValueError(
                f"Unsupported datetime offset: {unit}. "
                "Supported offsets: YS, MS, W, D, H, T, S"
            )
        self.unit = unit
        self.magnitude = magnitude
        self._add_offset_to_datetime = supported_datetime_offsets[unit]

    def add_to_datetime(self, initial_dt):
        """Takes an initial cftime datetime,
        and returns a datetime with the offset added"""

        if not (isinstance(initial_dt, cftime.datetime)):
            raise TypeError(
                f"Invalid initial datetime type: {type(initial_dt)}. "
                "Expected type: cftime.datetime"
            )

        return self._add_offset_to_datetime(
            initial_dt=initial_dt, n=self.magnitude
        )


def parse_date_offset(offset):
    """Parse a given string date offset string and return an DatetimeOffset"""
    match = re.search("[0-9]+", offset)
    if match is None:
        raise ValueError(
            f"No numerical value given for offset: {offset}"
        )
    n = match.group()
    unit = offset.lstrip(n)
    return DatetimeOffset(unit=unit, magnitude=int(n))
