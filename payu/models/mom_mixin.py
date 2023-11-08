"""Mixin class for MOM and MOM6 drivers

:copyright: Copyright 2011 Marshall Ward, see AUTHORS for details
:license: Apache License, Version 2.0, see LICENSE for details
"""

import os

import cftime


class MomMixin:

    def get_restart_datetime(self, restart_path):
        """Given a restart path, parse the restart files and
        return a cftime datetime (for date-based restart pruning)"""
        # Check for ocean_solo.res file
        ocean_solo_path = os.path.join(restart_path, 'ocean_solo.res')
        if not os.path.exists(ocean_solo_path):
            raise FileNotFoundError(
                'Cannot find ocean_solo.res file, which is required for '
                'date-based restart pruning')

        with open(ocean_solo_path, 'r') as ocean_solo:
            lines = ocean_solo.readlines()

        calendar_int = int(lines[0].split()[0])
        cftime_calendars = {
            1: "360_day",
            2: "julian",
            3: "proleptic_gregorian",
            4: "noleap"
        }
        calendar = cftime_calendars[calendar_int]

        last_date_line = lines[-1].split()
        date_values = [int(i) for i in last_date_line[:6]]
        year, month, day, hour, minute, second = date_values
        return cftime.datetime(year, month, day, hour, minute, second,
                               calendar=calendar)
