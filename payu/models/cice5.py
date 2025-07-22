"""
The payu interface for the CICE model
-------------------------------------------------------------------------------
Contact: Marshall Ward <marshall.ward@anu.edu.au>
-------------------------------------------------------------------------------
Distributed as part of Payu, Copyright 2011 Marshall Ward
Licensed under the Apache License, Version 2.0
http://www.apache.org/licenses/LICENSE-2.0
"""

from __future__ import print_function

import os

from payu.models.cice import Cice
from payu.fsops import mkdir_p
import payu.calendar as cal
from netCDF4 import Dataset
import cftime

class Cice5(Cice):

    def __init__(self, expt, name, config):
        super(Cice5, self).__init__(expt, name, config)

        self.model_type = 'cice5'
        self.default_exec = 'cice'

        self.config_files = [
            'cice_in.nml',
            'input_ice.nml',
            'input_ice_gfdl.nml',
            'input_ice_monin.nml'
        ]

        self.ice_nml_fname = 'cice_in.nml'

        self.set_timestep = self.set_local_timestep

        self.copy_restarts = True
        self.copy_inputs = True

        # Empty list means no log files will be compressed
        self.logs_to_compress = []

    def set_local_timestep(self, t_step):
        dt = self.ice_in['setup_nml']['dt']
        npt = self.ice_in['setup_nml']['npt']

        self.ice_in['setup_nml']['dt'] = t_step
        self.ice_in['setup_nml']['npt'] = (int(dt) * int(npt)) // int(t_step)

        ice_in_path = os.path.join(self.work_path, self.ice_nml_fname)
        self.ice_in.write(ice_in_path, force=True)

    def setup(self):
        # Force creation of a dump (restart) file at end of run
        self.ice_in['setup_nml']['dump_last'] = True

        use_leap_years = self.ice_in['setup_nml']['use_leap_years']

        if use_leap_years == True :
            self.caltype = cal.GREGORIAN
            self.cal_str = "proleptic_gregorian"
        elif use_leap_years == False :
            self.caltype = cal.NOLEAP
            self.cal_str = "noleap"
        else :
            raise ValueError("use_leap_years invalid")

        super(Cice5, self).setup()

        # Make log dir
        mkdir_p(os.path.join(self.work_path, 'log'))

    def get_prior_restart_files(self):
        """
        Overrides the super method to avoid printing an error if there are no
        prior restart files found
        """
        if self.prior_restart_path is not None:
            return sorted(os.listdir(self.prior_restart_path))
        else:
            return []

    def get_latest_restart_file(self, restart_path):
        """
        Given a restart path, parse the restart files and return the latest in
        that folder. Only used by esm1.6 driver but
        should work in other drivers.
        """
        iced_restart_file = None
        iced_restart_files = [f for f in os.listdir(restart_path) if f.startswith('iced.')]

        if len(iced_restart_files) > 0:
            iced_restart_file = sorted(iced_restart_files)[-1]

        if iced_restart_file is None:
            raise FileNotFoundError(
                f'No iced restart file found in {restart_path}'
            )

        return iced_restart_file

    def set_access_timestep(self, t_step):
        # TODO: Figure out some way to move this to the ACCESS driver
        # Re-read ice timestep and move this over there
        self.set_local_timestep(t_step)

    def get_restart_datetime(self, restart_path):
        """
        Given a restart path, parse the restart files and return a cftime 
        datetime.
        ( esm1.6 is the only model with the "year" attribute in restart files. 
        See https://github.com/ACCESS-NRI/cice5/issues/45 )
        """
        iced_file = self.get_latest_restart_file(restart_path)
        restart_f = os.path.join(restart_path, iced_file)

        iced_nc = Dataset(restart_f)
        restart_date = cftime.datetime(
            year = iced_nc.getncattr('year'),
            month = iced_nc.getncattr('month'),
            day = iced_nc.getncattr('mday') ,
            calendar = self.cal_str
        )
        if iced_nc.getncattr('sec') != 0 :
            msg = (
                f"Restart attribute sec in "
                f"cice restart ({iced_file}) must be 0."
                "All runs must start at midnight."
                )
            raise ValueError(msg)
        iced_nc.close()

        return restart_date

    def _calc_runtime(self):
        """
        Overrides the cice driver method, as CICE5 can store the timing information in restart files does not use
        the timing information in the cice_in.nml namelist.
        """
        pass

    def _make_restart_ptr(self):
        """
        Generate restart pointer which points to the latest iced.YYYYMMDD
        restart file in the prior restart directory.
        """
        if self.prior_restart_path is None:
            raise RuntimeError(
                f"{self.model_type}._make_restart_pointer called with no "
                "available prior restart directory."
            )

        iced_restart_file = self.get_latest_restart_file(self.prior_restart_path)

        res_ptr_path = os.path.join(self.work_init_path,
                                    'ice.restart_file')
        if os.path.islink(res_ptr_path):
            # If we've linked in a previous pointer it should be deleted
            os.remove(res_ptr_path)
        with open(res_ptr_path, 'w') as res_ptr:
            res_dir = self.get_ptr_restart_dir()
            res_ptr.write(os.path.join(res_dir, iced_restart_file))
