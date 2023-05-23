# coding: utf-8
"""
The payu interface for CESM model configurations using CMEPS/NUOPC
-------------------------------------------------------------------------------
Contact: Marshall Ward <marshall.ward@anu.edu.au>
-------------------------------------------------------------------------------
Distributed as part of Payu, Copyright 2011 Marshall Ward
Licensed under the Apache License, Version 2.0
http://www.apache.org/licenses/LICENSE-2.0
"""
from __future__ import print_function

# Standard Library
import os
import re
import glob
import shutil
import multiprocessing

# Local
from payu.fsops import mkdir_p
from payu.models.model import Model
from payu.models.fms import fms_collate

component_info = {
    "mom6": {
        "realm": "ocn",
        "config_files": [
            "input.nml",
            "MOM_input",
            "diag_table",
        ],
        "optional_config_files" : ["MOM_override"]
    },
    "cice6": {
        "realm": "ice",
        "config_files": ["ice_in"],
    },
    "ww3": {
        "realm": "wav",
        "config_files": ["wav_in"],
    },
    "datm": {
        "realm": "atm",
        "config_files": [
            "datm_in",
            "datm.streams.xml",
        ],
    },
    "docn": {
        "realm": "ocn",
        "config_files": [
            "docn_in",
            "docn.streams.xml",
        ],
    },
    "drof": {
        "realm": "rof",
        "config_files": [
            "drof_in",
            "drof.streams.xml"
        ]
    },
}

class CesmCmepsBase(Model):

    def __init__(self, components, expt, name, config):
        super().__init__(expt, name, config)

        self.model_type = 'cesm-cmeps'

        self.components = components
        self.realms = ["cpl"] + [
            component_info[component]["realm"] for component in self.components
            ]
        self.config_files, self.optional_config_files = self.get_component_config_files()

    def get_component_config_files(self):

        assert self.components is not None, "Model components must be specified for CesmCmepsBase"

        # Driver config files always present
        config_files = [
            "drv_in",
            "fd.yaml",
            "nuopc.runconfig",
            "nuopc.runseq"
        ]
        optional_config_files = []
        for component in self.components:
            config_files.extend(component_info[component]["config_files"])
            try:
                optional_config_files.extend(
                    component_info[component]["optional_config_files"]
                    )
            except KeyError:
                pass

        return config_files, optional_config_files

    def set_model_pathnames(self):

        super().set_model_pathnames()

        self.work_input_path = os.path.join(self.work_path, 'input')
        
    def setup(self):
        super().setup()

        runconfig = Runconfig(os.path.join(self.work_path, 'nuopc.runconfig'))

        self.case_name = runconfig.get("ALLCOMP_attributes", "case_name")

        if self.prior_restart_path and not self.expt.repeat_run:
            start_type = 'continue'

            # Overwrite restart pointer symlinks with copies
            pointer_files = [
                os.path.join(
                    self.work_path, f"rpointer.{realm}",
                    ) for realm in self.realms
            ]
            for f_dst in pointer_files:
                f_src = os.readlink(f_dst)
                os.remove(f_dst)
                shutil.copy(f_src, f_dst)
        else:
            start_type = 'startup'

        runconfig.set("ALLCOMP_attributes", "start_type", start_type)

        # Check pelayout makes sense
        all_realms = ["atm", "cpl", "glc", "ice", "lnd", "ocn", "rof", "wav"]
        cpucount = int(
            self.expt.config.get('ncpus', multiprocessing.cpu_count())
            )
        for realm in all_realms:
            ntasks = int(runconfig.get("PELAYOUT_attributes", f"{realm}_ntasks"))
            assert cpucount >= ntasks, "Insufficient cpus for the pelayout in nuopc.runconfig"
        
        # Ensure that restarts will be written at the end of each run
        stop_n = runconfig.get("CLOCK_attributes", "stop_n")
        stop_option = runconfig.get("CLOCK_attributes", "stop_option")
        runconfig.set("CLOCK_attributes", "restart_n", stop_n)
        runconfig.set("CLOCK_attributes", "restart_option", stop_option)
        
        mkdir_p(os.path.join(self.work_path, 'log'))
        mkdir_p(os.path.join(self.work_path, 'timing'))

        runconfig.write()

        # TODO: Need a better way to do this
        # The ww3 mod_def input needs to be in work_path and called mod_def.ww3
        if "ww3" in self.components:
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
        # WW3 looks for a <case_name>.ww3.r.<date> file despite this not  being specified in wav_in.
        # I guess the driver specifies this somewhere based on the cpl restart file name?
        if "ww3" in self.components:
            cpl_pointer = os.path.join(
                self.work_path, f"rpointer.cpl",
                )
            with open(cpl_pointer, "r") as f:
                cpl_restart = f.readline().rstrip()
                wav_restart = cpl_restart.replace("cpl", "ww3").removesuffix(".nc")
            wav_pointer = os.path.join(
                self.work_path, f"rpointer.wav",
                )
            with open(wav_pointer, 'w') as f:
                f.write(wav_restart)

        # Get names of restarts from restart pointer files
        pointer_files = [
                os.path.join(
                    self.work_path, f"rpointer.{realm}",
                    ) for realm in self.realms
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


class AccessOm3(CesmCmepsBase):

    def __init__(self, expt, name, config):

        components = ["mom6", "cice6", "ww3", "datm", "drof"]
        
        super().__init__(components, expt, name, config)

    def collate(self):
        fms_collate(self)


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