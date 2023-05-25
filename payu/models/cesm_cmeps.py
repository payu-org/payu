# coding: utf-8
"""
The payu interface for CESM model configurations using CMEPS and the CESM CMEPS driver
--------------------------------------------------------------------------------------
Contact: Marshall Ward <marshall.ward@anu.edu.au>
--------------------------------------------------------------------------------------
Distributed as part of Payu, Copyright 2011 Marshall Ward
Licensed under the Apache License, Version 2.0
http://www.apache.org/licenses/LICENSE-2.0
"""
from __future__ import print_function

import os
import re
import errno
import glob
import shutil
import multiprocessing

from payu.fsops import mkdir_p
from payu.models.model import Model
from payu.models.fms import fms_collate

# Add as needed
component_info = {
    "mom": {
        "config_files": [
            "input.nml",
            "MOM_input",
            "diag_table",
        ],
        "optional_config_files" : ["MOM_override"]
    },
    "cice": {
        "config_files": ["ice_in"],
    },
    "ww3dev": {
        "config_files": ["wav_in"],
    },
    "datm": {
        "config_files": [
            "datm_in",
            "datm.streams.xml",
        ],
    },
    "docn": {
        "config_files": [
            "docn_in",
            "docn.streams.xml",
        ],
    },
    "drof": {
        "config_files": [
            "drof_in",
            "drof.streams.xml"
        ]
    },
}

class CesmCmeps(Model):

    def __init__(self, expt, name, config):
        super().__init__(expt, name, config)

        self.model_type = 'cesm-cmeps'

        # Driver config files should always be present
        self.config_files = [
            "drv_in",
            "fd.yaml",
            "nuopc.runconfig",
            "nuopc.runseq"
        ]

        self.realms = ["ocn", "ice", "wav", "atm", "rof", "cpl"]
        self.runconfig = None # nuopc.runconfig. Can't read this yet as paths haven't necessarily been set
        self.components = {} # To be read from nuopc.runconfig
        self.rpointers = [] # To be inferred from nuopc.runconfig

    def get_runconfig(self, path):
        self.runconfig = Runconfig(os.path.join(path, 'nuopc.runconfig'))
        
    def get_components(self):
        """Get components from nuopc.runconfig"""

        self.components = {}
        self.rpointers = ["rpointer.cpl"]
        for realm in self.realms:
            if realm != "cpl":
                component = self.runconfig.get("ALLCOMP_attributes", f"{realm.upper()}_model")
                if not component.startswith("s"): # TODO: better check for stub component?
                    self.components[realm] = component
                    self.rpointers.append(f"rpointer.{realm}")

        for component in self.components.values():
            if component in component_info:
                self.config_files.extend(component_info[component]["config_files"])
                try:
                    self.optional_config_files.extend(
                        component_info[component]["optional_config_files"]
                        )
                except KeyError:
                    pass
            else:
                raise ValueError(f"There is no component info entry for {component}")

    def set_model_pathnames(self):

        super().set_model_pathnames()

        self.work_input_path = os.path.join(self.work_path, 'input')
        
    def setup(self):
        super().setup()

        # Read components from nuopc.runconfig and copy component configuration files
        self.get_runconfig(self.work_path)
        self.get_components()
        for f_name in self.config_files:
            f_path = os.path.join(self.control_path, f_name)
            shutil.copy(f_path, self.work_path)

        for f_name in self.optional_config_files:
            f_path = os.path.join(self.control_path, f_name)
            try:
                shutil.copy(f_path, self.work_path)
            except IOError as exc:
                if exc.errno == errno.ENOENT:
                    pass
                else:
                    raise
        
        if self.prior_restart_path and not self.expt.repeat_run:
            start_type = 'continue'

            # Overwrite restart pointer symlinks with copies
            pointer_files = [
                os.path.join(
                    self.work_path, pointer,
                    ) for pointer in self.rpointers
            ]
            for f_dst in pointer_files:
                f_src = os.readlink(f_dst)
                os.remove(f_dst)
                shutil.copy(f_src, f_dst)
        else:
            start_type = 'startup'

        self.runconfig.set("ALLCOMP_attributes", "start_type", start_type)

        # Check pelayout makes sense
        all_realms = self.realms + ["glc", "lnd"]
        cpucount = int(
            self.expt.config.get('ncpus', multiprocessing.cpu_count())
            )
        for realm in all_realms:
            ntasks = int(self.runconfig.get("PELAYOUT_attributes", f"{realm}_ntasks"))
            assert cpucount >= ntasks, "Insufficient cpus for the pelayout in nuopc.runconfig"
        
        # Ensure that restarts will be written at the end of each run
        stop_n = self.runconfig.get("CLOCK_attributes", "stop_n")
        stop_option = self.runconfig.get("CLOCK_attributes", "stop_option")
        self.runconfig.set("CLOCK_attributes", "restart_n", stop_n)
        self.runconfig.set("CLOCK_attributes", "restart_option", stop_option)
        
        mkdir_p(os.path.join(self.work_path, 'log'))
        mkdir_p(os.path.join(self.work_path, 'timing'))

        self.runconfig.write()

        # TODO: Should have a better way to do this
        # The ww3 mod_def input needs to be in work_path and called mod_def.ww3
        if "ww3dev" in self.components.values():
            files =  glob.glob(
                os.path.join(self.work_input_path, "*mod_def.ww3*"),
                recursive=False
            )
            if files:
                assert len(files) == 1, "Multiple mod_def.ww3 files found in input directory"
                f_dst = os.path.join(self.work_path, "mod_def.ww3")
                shutil.copy(files[0], f_dst)
            else:
                # TODO: copied this from other models. Surely we want to exit here or something
                print('payu: error: Unable to find mod_def.ww3 file in input directory')

    def archive(self):
        super().archive()

        mkdir_p(self.restart_path)

        # WW3 doesn't generate a rpointer file. Write one so that all components can be generally
        # handled in the same way.
        # Note, I don't actually know how WW3 knows what restart to use. The normal approach to
        # providing restarts to WW3 is to add a restart.ww3 file to the run directory. However, here
        # WW3 looks for a <case_name>.ww3.r.<date> file despite this not being specified in wav_in.
        # I guess the driver specifies this somewhere based on the cpl restart file name?
        if "ww3dev" in self.components.values():
            cpl_pointer = os.path.join(
                self.work_path, "rpointer.cpl",
                )
            with open(cpl_pointer, "r") as f:
                cpl_restart = f.readline().rstrip()
            wav_restart = cpl_restart.replace("cpl", "ww3").removesuffix(".nc")
            wav_pointer = os.path.join(
                self.work_path, "rpointer.wav",
                )
            with open(wav_pointer, 'w') as f:
                f.write(wav_restart)

        # Get names of restarts from restart pointer files
        pointer_files = [
                os.path.join(
                    self.work_path, pointer,
                    ) for pointer in self.rpointers
            ]
        restart_files = []
        for pointer in pointer_files:
            try:
                with open(pointer,"r") as f:
                    restart = f.readline().rstrip()
                    restart_files.append(
                        os.path.join(
                            self.work_path, restart,
                            )
                        )
            except FileNotFoundError:
                # TODO: copied this from other models. Surely we want to exit here or something
                print(f"payu: error: Model has not produced pointer file {pointer}")
        
        for f_src in restart_files + pointer_files:
            name = os.path.basename(f_src)
            f_dst = os.path.join(self.restart_path, name)
            shutil.move(f_src, f_dst)

    def collate(self):
        
        # .setup is not run when collate is called so need to get components
        self.get_runconfig(self.output_path)
        self.get_components()
        
        if "mom" in self.components.values():
            fms_collate(self)
        else:
            super().collate()


class AccessOm3(CesmCmeps):

    def get_components(self):
        super().get_components()

        assert self.components["atm"] == "datm", (
            "Access-OM3 comprises a data atmosphere model, but the atmospheric model in nuopc.runconfig is set "
            f"to {self.components['atm']}."
        )
        assert self.components["rof"] == "drof", (
            "Access-OM3 comprises a data runoff model, but the runoff model in nuopc.runconfig is set "
            f"to {self.components['rof']}."
        )


class Runconfig:
    """ Simple class for parsing and editing nuopc.runconfig """

    def __init__(self, file):
        self.file = file
        with open(self.file, 'r+') as f:
            self.contents = f.read()

    def _get_variable_span(self, section, variable):
        m = re.search(
            r"(?<={}\:\:)(.*?)(?=\:\:)".format(section),
            self.contents,
            re.DOTALL,
        )
        assert m is not None, f"Cannot find section {section} in nuopc.runconfig"
        section_start = m.start(1)
        section_end = m.end(1)
        m = re.search(
            r"{}\s*=\s*(.*)".format(variable),
            self.contents[section_start:section_end],
        )
        assert m is not None, (
            f"Cannot find variable {variable} in section {section} in nuopc.runconfig"
        )
        return section_start + m.start(1), section_start + m.end(1)

    def get(self, section, variable):
        start, end = self._get_variable_span(section, variable)
        return self.contents[start:end]

    def set(self, section, variable, new_value):
        start, end = self._get_variable_span(section, variable)
        self.contents = self.contents[:start] + new_value + self.contents[end:]

    def write(self):
        with open(self.file, 'w') as f:
            f.write(self.contents)