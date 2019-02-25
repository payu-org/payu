from dateutil.relativedelta import relativedelta
import datetime

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
