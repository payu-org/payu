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


class Cice5(Cice):

    def __init__(self, expt, name, config):
        super(Cice5, self).__init__(expt, name, config)

        self.model_type = 'cice5'
        self.default_exec = 'cice'

        # Default repo details
        self.repo_url = 'https://github.com/OceansAus/cice5.git'
        self.repo_tag = 'master'

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

        super(Cice5, self).setup()

        # Make log dir
        mkdir_p(os.path.join(self.work_path, 'log'))

    def get_prior_restart_files(self):
        if self.prior_restart_path is not None:
            return sorted(os.listdir(self.prior_restart_path))
        else:
            return []

    def set_access_timestep(self, t_step):
        # TODO: Figure out some way to move this to the ACCESS driver
        # Re-read ice timestep and move this over there
        self.set_local_timestep(t_step)
