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

component_config_files = {
    "mom6": [
        "input.nml",
        "MOM_input",
        "diag_table",
    ],
    "cice6": ["ice_in"],
    "ww3": ["wav_in"],
    "datm": [
        "datm_in",
        "datm.streams.xml",
    ],
    "drof": [
        "drof_in",
        "drof.streams.xml"
    ]
}

component_optional_config_files = {
    "mom6": ["MOM_override"]
}

class Cesm(Model):

    def __init__(self, expt, name, config):
        super(Cesm, self).__init__(expt, name, config)

        self.model_type = 'Cesm'
        self.default_exec = 'cesm'

        # Hardcoded by CMEPS driver
        self.restart_template = ".*.r.*.nc"
        self.restart_pointer_template = "rpointer.*"

        self.config_files, self.optional_config_files = self.get_component_config_files()

    def get_component_config_files(self):
        components = self.expt.config.get('components')

        assert components is not None, "Model components must be specified when running cesm"

        # Driver config files always present
        config_files = [
            "drv_in",
            "fd.yaml",
            "nuopc.runconfig",
            "nuopc.runseq"
        ]
        optional_config_files = []
        for component in components:
            config_files.extend(component_config_files[component])
            try:
                optional_config_files.extend(component_optional_config_files[component])
            except KeyError:
                pass

        return config_files, optional_config_files

    def set_model_pathnames(self):

        super(Cesm, self).set_model_pathnames()

        self.work_input_path = os.path.join(self.work_path, 'input')
        
    def setup(self):
        super(Cesm, self).setup()

        runconfig = Runconfig(os.path.join(self.work_path, 'nuopc.runconfig'))

        self.case_name = runconfig.get("ALLCOMP_attributes", "case_name")

        if self.prior_restart_path and not self.expt.repeat_run:
            start_type = 'continue'

            # Overwrite restart pointer symlinks with copies
            pointers = glob.glob(
                os.path.join(
                    self.work_path, 
                    self.restart_pointer_template,
                    )
                )
            for f_dst in pointers:
                f_src = os.readlink(f_dst)
                os.remove(f_dst)
                shutil.copy(f_src, f_dst)
        else:
            start_type = 'startup'
            
        runconfig.set("ALLCOMP_attributes", "start_type", start_type)

        # Check pelayout makes sense
        components = ["atm", "cpl", "glc", "ice", "lnd", "ocn", "rof", "wav"]
        cpucount = int(
            self.expt.config.get('ncpus', multiprocessing.cpu_count())
            )
        for comp in components:
            ntasks = int(runconfig.get("PELAYOUT_attributes", f"{comp}_ntasks"))
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
        # The mod_def input file needs to be in work_path and called mod_def.ww3
        if "ww3" in self.expt.config.get("components"):
            files =  glob.glob(
                os.path.join(self.work_input_path, "*mod_def.ww3*"),
                recursive=False
            )
            if files:
                assert len(files) == 1, "Multiple mod_def.ww3 files found in input directory"
                f_dst = os.path.join(self.work_path, "mod_def.ww3")
                shutil.copy(files[0], f_dst)
            else:
                print('payu: error: Unable to find mod_def.ww3 file in input directory')

    def archive(self):
        super(Cesm, self).archive()

        mkdir_p(self.restart_path)

        restart_files = glob.glob(
            os.path.join(
                self.work_path, 
                f"{self.case_name}{self.restart_template}"
                )
            )
        restart_pointers = glob.glob(
            os.path.join(
                self.work_path, 
                self.restart_pointer_template,
                )
            )
        if not restart_files:
            print('payu: error: Model has not produced any restart files')
        if not restart_pointers:
            print('payu: error: Model has not produced any restart pointer files')
        
        for f_src in restart_files + restart_pointers:
            name = os.path.basename(f_src)
            f_dst = os.path.join(self.restart_path, name)
            shutil.move(f_src, f_dst)


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
    