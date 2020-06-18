"""Generic interface for job scheduler control.

:copyright: Copyright 2020 Marshall Ward, see AUTHORS for details
:license: Apache License, Version 2.0, see LICENSE for details
"""

# TODO: This class is currently just a stub.  I would hope that it will be
# expanded to provide greater functionality in the future.


class Scheduler(object):
    """Abstract scheduler class."""

    def __init__(self):
        # TODO
        pass

    def submit(self, pbs_script, pbs_config, pbs_vars=None, python_exe=None):
        raise NotImplementedError
