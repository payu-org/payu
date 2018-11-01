"""payu.namcouple
   ==============

   OASIS Namcouple parser

   :copyright: Copyright 2014 Nicholas Hannah
"""

import re
import sys


class Namcouple:
    """
    Class to represent an OASIS namcouple file.

    Allows fields to be modified.

    Presently only supports $RUNTIME and ocean timestep.
    """

    def __init__(self, filename, model):
        self.filename = filename
        self.model = model
        with open(filename, 'r') as f:
            self.str = f.read()

    def set_runtime(self, runtime):

        m = re.search(r"^[ \t]*\$RUNTIME.*?^[ \t]*(\d+)", self.str,
                      re.MULTILINE | re.DOTALL)
        assert m is not None
        self.str = self.str[:m.start(1)] + str(runtime) + self.str[m.end(1):]

    def substitute_timestep(self, regex, timestep):
        """
        Substitute a new timestep value using regex.
        """

        # Make one change at a time, each change affects subsequent matches.
        timestep_changed = False
        while True:
            matches = re.finditer(regex, self.str, re.MULTILINE | re.DOTALL)
            none_updated = True
            for m in matches:
                if m.group(1) == timestep:
                    continue
                else:
                    self.str = (self.str[:m.start(1)] + timestep +
                                self.str[m.end(1):])
                    none_updated = False
                    timestep_changed = True
                    break

            if none_updated:
                break

        if not timestep_changed:
            sys.stderr.write('WARNING: no update with {0}.\n'.format(regex))

    def set_ice_timestep(self, timestep):

        self.substitute_timestep(r"\w{4} \w{4} LAG=\+(\d+)", timestep)

    def set_ice_ocean_coupling_timestep(self, timestep):

        self.substitute_timestep(r"\d+ (\d+) \d+ i2o.nc", timestep)
        self.substitute_timestep(r"\d+ (\d+) \d+ o2i.nc", timestep)

    def write(self):
        with open(self.filename, 'w') as f:
            f.write(self.str)
