"""payu.models.cable
   ================

   Driver interface to CABLE

   :copyright: Copyright 2021 Marshall Ward, see AUTHORS for details
   :license: Apache License, Version 2.0, see LICENSE for details
"""

# Standard Library
import glob
import os
import shutil

# Extensions
import f90nml
import yaml

# Local
from payu.fsops import mkdir_p
from payu.models.model import Model


def _get_forcing_path(variable, year, input_dir, offset=None, repeat=None):
    """Return the met forcing file path for a given variable and year.
    
    Parameters
    ----------
    variable : str
        Variable name.
    year : int
        Year value.
    input_dir : str
        Path to work input directory.
    offset : list of int, optional
        Offset the current simulation year from `offset[0]` to `offset[1]`
        before inferring the met forcing path.
    repeat : list of int, optional
        Constrain the current simulation year between `repeat[0]` and
        `repeat[1]` (inclusive) before inferring the met forcing path. If the
        year is outside the interval, the constrained year repeats over the
        interval.

    Returns
    -------
    path : str
        Path (relative to control directory) to the inferred met forcing file.

    Raises
    ------
    FileNotFoundError
        If unable to infer met forcing path.
    """
    if offset:
        year += offset[1] - offset[0]
    if repeat:
        year = repeat[0] + ((year - repeat[0]) % (repeat[1] - repeat[0] + 1))
    pattern = os.path.join(input_dir, f"*{variable}*{year}*.nc")
    for path in glob.glob(pattern):
        return path
    msg = f"Unable to infer met forcing path for variable {variable} for year {year}."
    raise FileNotFoundError(msg)


class Cable(Model):

    def __init__(self, expt, name, config):
        super(Cable, self).__init__(expt, name, config)

        self.model_type = 'cable'
        self.default_exec = 'cable'

        self.cable_nml_fname = 'cable.nml'

        self.config_files = [
            self.cable_nml_fname,
            'cable_soilparm.nml',
            'pft_params.nml',
        ]

        self.forcing_year_config = 'cable.forcing_year.yaml'
        self.optional_config_files = [self.forcing_year_config]

        self.met_forcing_vars = [
            "Rainf",
            "Snowf",
            "LWdown",
            "SWdown",
            "PSurf",
            "Qair",
            "Tair",
            "Wind",
        ]

    def set_model_pathnames(self):
        super(Cable, self).set_model_pathnames()

        # TODO: Check for path in filename%type
        self.work_input_path = os.path.join(self.work_path, 'INPUT')
        self.work_init_path = self.work_input_path
        # TODO: Check for path in filename%restart_out
        self.work_restart_path = os.path.join(self.work_path, 'RESTART')

        self.restart_calendar_file = self.model_type + '.res.yaml'
        self.restart_calendar_path = os.path.join(self.work_init_path,
                                                  self.restart_calendar_file)

        self.cable_nml_path = os.path.join(self.work_path,
                                           self.cable_nml_fname)

    def setup(self):
        super(Cable, self).setup()

        self.cable_nml = f90nml.read(self.cable_nml_path)
        if self.prior_restart_path:
            with open(self.restart_calendar_path, 'r') as restart_file:
                self.restart_info = yaml.safe_load(restart_file)
        else:
            self.restart_info = {'year': self.cable_nml['cable']['ncciy']}

        year = self.cable_nml['cable']['ncciy'] = self.restart_info['year']

        self.cable_nml['cable']['filename']['restart_in'] = (
            os.path.join('INPUT', 'restart.nc')
        )
        self.cable_nml['cable']['filename']['restart_out'] = (
            os.path.join('RESTART', 'restart.nc')
        )
        self.cable_nml['cable']['output']['restart'] = True

        forcing_year_config_path = os.path.join(self.work_path, self.forcing_year_config)
        if os.path.exists(forcing_year_config_path):
            with open(forcing_year_config_path, 'r') as file:
                conf = yaml.safe_load(file)
                forcing_year_config = conf if conf else {}
            for var in self.met_forcing_vars:
                path = _get_forcing_path(
                    var, year, self.work_input_path, **forcing_year_config
                )
                self.cable_nml["cable"]["gswpfile"][var] = (
                    os.path.relpath(path, start=self.work_path)
                )

        # Write modified namelist file to work dir
        self.cable_nml.write(
            os.path.join(self.work_path, self.cable_nml_fname),
            force=True
        )

    def archive(self, **kwargs):

        # Save model time to restart next run
        with open(os.path.join(self.restart_path,
                  self.restart_calendar_file), 'w') as restart_file:
            restart = {'year': self.restart_info['year'] + 1}
            restart_file.write(yaml.dump(restart, default_flow_style=False))

        super(Cable, self).archive()

        # Archive the restart files
        mkdir_p(self.restart_path)

        restart_files = [f for f in os.listdir(self.work_restart_path)
                         if f.endswith('restart.nc')]

        for f in restart_files:
            f_src = os.path.join(self.work_restart_path, f)
            shutil.move(f_src, self.restart_path)

        os.rmdir(self.work_restart_path)

        # Move all logs into a logs subdir
        log_path = os.path.join(self.work_path, 'logs')
        mkdir_p(log_path)
        log_files = [f for f in os.listdir(self.work_path)
                     if f.startswith('cable_log')]
        for f in log_files:
            f_src = os.path.join(self.work_path, f)
            shutil.move(f_src, log_path)

    def collate(self):
        pass
