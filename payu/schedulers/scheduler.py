"""Generic interface for job scheduler control.

:copyright: Copyright 2020 Marshall Ward, see AUTHORS for details
:license: Apache License, Version 2.0, see LICENSE for details
"""

# TODO: This class is currently just a stub.  I would hope that it will be
# expanded to provide greater functionality in the future.


from typing import Any, Dict, Optional


class Scheduler(object):
    """Abstract scheduler class."""

    def __init__(self):
        # TODO
        pass

    def submit(self, pbs_script, pbs_config, pbs_vars=None, python_exe=None):
        raise NotImplementedError

    def get_job_info(self) -> Optional[Dict[str, Any]]:
        """Get information about the currently running job

        Returns
        ----------
        Optional[Dict[str, Any]]
            Dictionary of information queried from the scheduler
        """
        pass

    def get_job_id(self, short: bool = True) -> Optional[str]:
        """Get scheduler-specific job ID

        Parameters
        ----------
        short: bool, default True
            Return shortened form of the job ID

        Returns
        ----------
        Optional[str]
            Job id if defined, None otherwise
        """
        pass
