
import re
import sys

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
        m = re.search((r"&%s.*?" + regex) % (record, variable), self.str,
                      re.MULTILINE | re.DOTALL)
        assert(m is not None)

        return (m.group(1), m.start(1),
                m.end(1) if m.group(1)[-1] != '\n' else m.end(1) - 1)

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

