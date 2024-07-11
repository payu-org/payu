"""payu.models.cable
   ================

   Driver interface to CABLE-POP_TRENDY branch

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
# import xarray

# Local
from payu.fsops import mkdir_p
from payu.models.model import Model

class CablePOP(Model):

    def __init__(self, expt, name, config):
        super(CablePOP, self).__init__(expt, name, config)

        self.model_type = 'cable_POP'
        self.default_exec = 'cable'

        self.config_files = ['cable.nml', 'cru.nml', 'luc.nml', 'met_names.nml', 'cable_config.yaml']
        self.optional_config_files = []

    def setup(self):
        super(CablePOP, self).setup()

        with open(self.config_files[3]) as cable_config_file:
            self.cable_config = yaml.safe_load(cable_config_file)

        os.makedirs(os.path.join(self.work_input_path, "logs"), exist_ok = True)
        os.makedirs(os.path.join(self.work_input_path, "restart"), exist_ok = True)
        os.makedirs(os.path.join(self.work_input_path, "outputs"), exist_ok = True)
        # self._prepare_landmask(self.cable_config["landmask"])

    def collate(self):
        pass

    # def _prepare_landmask(self, landmask_config):
        # """Prepare the landmask for the run from the global landmask, using the information in cable_config.yaml."""

        # # Read the base landmask using xarray and extract the land variable
        # base_landmask = xarray.open_dataset(landmask_config["file"])["land"]

        # # Select a portion of the landmask based on the specified domain
        # # Domain can either be "global", or a list specifying the
        # # [lat_min, lat_max, lon_min, lon_max]
        # if landmask_config["domain"] == "global":
            # domain_landmask = base_landmask.sortby("latitude")

        # elif isinstance(landmask_config["domain"], list):
            # sorted_landmask = base_landmask.sortby("latitude")
            # lat_slice = slice(landmask_config["domain"][0], landmask_config["domain"][1])
            # lon_slice = slice(landmask_config["domain"][2], landmask_config["domain"][3])
            # domain_landmask = sorted_landmask.sel(latitude = lat_slice, longitude = lon_slice).reindex_like(base_landmask, fill_value = 0)
        
        # else:
            # raise ValueError("Value provided for the landmask domain is invalid.")

        # # Now write the landmask to file
        # domain_landmask.to_netcdf(self.work_input_path)
        
    def _climate_spinup_namelist(self):
        """Set the namelist for the climate spinup namelist."""
        pass

    def _zero_biomass_namelist(self):
        pass

