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

    return (date.year * 10**4 + date.month * 10**2 + date.day)


def runtime_from_date(start_date, years, months, days, seconds, caltype):
    """
    Get the number of seconds from start date to start date + date_delta.

    Ignores Feb 29 for caltype == NOLEAP.
    """

    end_date = start_date + relativedelta(years=years, months=months,
                                          days=days)
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


def add_year_offset_to_datetime(initial_dt, n):
    """Return a datetime n years from the initial datetime"""
    if isinstance(initial_dt, datetime.datetime):  # Standard datetime Calendar
        return initial_dt + relativedelta(years=n)
    
    if isinstance(initial_dt, cftime.datetime):  # Non-standard Calendars
        return initial_dt.replace(year=initial_dt.year + n)


def add_year_start_offset_to_datetime(initial_dt, n):
    """Return a datetime at the start of the year - n years from the initial datetime"""
    if isinstance(initial_dt, datetime.datetime):
        return initial_dt + relativedelta(years=n, month=1, day=1, hour=0, minute=0, second=0)
    
    if isinstance(initial_dt, cftime.datetime):
        return initial_dt.replace(year=initial_dt.year + n, month=1, day=1, hour=0, minute=0, second=0)


def add_month_start_offset_to_datetime(initial_dt, n):
    """Return a datetime of the start of the month - n months from the initial datetime"""
    if isinstance(initial_dt, datetime.datetime):
        return initial_dt + relativedelta(months=n, day=1, hour=0, minute=0, second=0)
    
    if isinstance(initial_dt, cftime.datetime):
        year = initial_dt.year + ((initial_dt.month + n - 1) // 12)
        month = (initial_dt.month + n - 1) % 12 + 1
        
        return initial_dt.replace(year=year, month=month, day=1, hour=0, minute=0, second=0)


def add_month_offset_to_datetime(initial_dt, n):
    """Return a datetime n months from the initial datetime"""
    if isinstance(initial_dt, datetime.datetime):
        return initial_dt + relativedelta(months=n)
    
    if isinstance(initial_dt, cftime.datetime):
        year = initial_dt.year + ((initial_dt.month + n - 1) // 12)
        month = (initial_dt.month + n - 1) % 12 + 1
        day = initial_dt.day
        
        max_day_in_month = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}
        if initial_dt.calendar == "noleap":
            day = initial_dt.day if initial_dt.day <= max_day_in_month[month] else max_day_in_month[month]
        
        if initial_dt.calendar == "all_leap":
            max_day_in_month[2] = 29 # Every year is a leap year
            day = initial_dt.day if initial_dt.day <= max_day_in_month[month] else max_day_in_month[month]
        
        return initial_dt.replace(year=year, month=month, day=day)
        

def add_timedelta_fn(timedelta):
    """Returns a function that adds a timedelta - n times to an initial datetime"""
    # Standard and cftime datetimes supports timedelta operations
    return lambda initial_dt, n: initial_dt + n * timedelta


class DatetimeOffset:
    
    def __init__(self, unit, magnitude):
        # Dictionary of 'offset units' to functions which takes an initial_dt (Standard or cftime datetime)
        # and n (multiplier of the offset unit), and returns the next datetime with the offset added
        supported_datetime_offsets = {
            'Y': add_year_offset_to_datetime,
            'YS': add_year_start_offset_to_datetime,
            'M': add_month_offset_to_datetime,
            'MS': add_month_start_offset_to_datetime,
            'W': add_timedelta_fn(datetime.timedelta(weeks=1)),
            'D': add_timedelta_fn(datetime.timedelta(days=1)),
            'H': add_timedelta_fn(datetime.timedelta(hours=1)),
            'T': add_timedelta_fn(datetime.timedelta(minutes=1)),
            'S': add_timedelta_fn(datetime.timedelta(seconds=1))
        }
        assert unit in supported_datetime_offsets, f"payu: error: unsupported datetime offset: {unit}"
        self.unit = unit
        self.magnitude = magnitude
        self.add_offset_to_datetime = supported_datetime_offsets[unit]


    def add_to_datetime(self, initial_dt):
        """Takes a datetime object (standard or cftime datetime),
        and returns a datetime with the offset added if possible, returns None otherwise"""

        if self.unit in ['M', 'Y'] and isinstance(initial_dt, cftime.datetime):    
            if initial_dt.datetime_compatible:
                # Transform cftime datetime to standard datetime
                initial_dt = datetime.datetime(initial_dt.year, initial_dt.month, initial_dt.day,
                                        initial_dt.hour, initial_dt.minute, initial_dt.second)
            elif initial_dt.calendar not in ["360_day", "noleap", "all_leap"]:
                raise ValueError(f"Calendar type {initial_dt.calendar} is unsupported for given date offset {self.unit}")
        
        if not (isinstance(initial_dt, cftime.datetime) or isinstance(initial_dt, datetime.datetime)):
            raise TypeError(f"Invalid initial datetime type: {type(initial_dt)}. Expected types: cftime.datetime or datetime.datetime")

        return self.add_offset_to_datetime(initial_dt=initial_dt, n=self.magnitude)


def parse_date_offset(offset):
    """Parse a given string date offset string, and returns an DatetimeOffset"""
    match = re.search('[0-9]+', offset)
    assert match is not None, f"payu: error: no numerical value given for offset: {offset}"
    n = match.group()
    unit = offset.lstrip(n)
    return DatetimeOffset(unit=unit, magnitude=int(n))