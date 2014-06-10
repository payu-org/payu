
import re
import sys

class Namcouple:
    """
    Class to represent an OASIS namcouple file. 

    Allows fields to be modified.

    Presently only supports $RUNTIME
    """

    def __init__(self, filename, model):
        self.filename = filename
        self.model = model
        with open(filename, 'r') as f:
            self.str = f.read()

    def set_runtime(self, runtime):

        m = re.search(r"^[ \t]*\$RUNTIME.*?^[ \t]*(\d+)", self.str, re.MULTILINE | re.DOTALL)
        assert(m is not None)
        self.str = self.str[:m.start(1)] + str(runtime) + self.str[m.end(1):]

    def set_ocean_timestep(self, timestep):

        def substitute_timestep(regex):
            """
            Make one change at a time, each change affects subsequent matches.
            """
            timestep_changed = False
            while True:
                matches = re.finditer(regex, self.str, re.MULTILINE | re.DOTALL)
                none_updated = True
                for m in matches:
                    if m.group(1) == timestep:
                        continue
                    else:
                        self.str = self.str[:m.start(1)] + timestep + self.str[m.end(1):]
                        none_updated = False
                        timestep_changed = True
                        break

                if none_updated:
                    break

            if not timestep_changed:
                sys.stderr.write('WARNING: no timstep values were updated.\n')

        if self.model == 'auscom':
            substitute_timestep(r"nt62 cice LAG=\+(\d+) ")
            substitute_timestep(r"cice nt62 LAG=\+(\d+) ")
            substitute_timestep(r"\d+ (\d+) \d+ INPUT/i2o.nc EXPORTED")
            substitute_timestep(r"\d+ (\d+) \d+ INPUT/o2i.nc EXPORTED")
        else:
            substitute_timestep(r"cice um1t LAG=\+(\d+) ")
            substitute_timestep(r"cice um1u LAG=\+(\d+) ")
            substitute_timestep(r"cice um1v LAG=\+(\d+) ")
            substitute_timestep(r"\d+ (\d+) \d+ i2o.nc IGNORED")
            substitute_timestep(r"\d+ (\d+) \d+ o2i.nc IGNORED")

    def write(self):
        with open(self.filename, 'w') as f:
            f.write(self.str)


class FortranNamelist:
    """
    Class to represent a Fortran namelist file.

    Can be used to modify fields.
    """

    def __init__(self, filename):
        self.filename = filename
        with open(filename, 'r') as f:
            self.str = f.read()

    def _get_value(self, record, variable):
        """
        Return the value, start index and end index.
        """

        # The %% is to escape the format character '%'
        regex = r"%s[ \t]*=[ \t]*(.*?)(?=\s+,?\s*(?:[%%\w]+[ \t]*=)|(?:/))"
        m = re.search((r"&%s.*?" + regex) % (record, variable), self.str, re.MULTILINE | re.DOTALL)
        assert(m is not None)

        return (m.group(1), m.start(1), m.end(1) if m.group(1)[-1] != '\n' else m.end(1) - 1)

    def get_value(self, record, variable):
        """
        Return the value.
        """

        value, _, _ = self._get_value(record, variable)

        return value

    def set_value(self, record, variable, value):

        (_, start, end) = self._get_value(record, variable)

        self.str = self.str[:start] + str(value) + self.str[end:]

    def write(self):
        with open(self.filename, 'w') as f:
            f.write(self.str)

