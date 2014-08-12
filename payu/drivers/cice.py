# coding: utf-8
"""
The payu interface for the CICE model
-------------------------------------------------------------------------------
Contact: Marshall Ward <marshall.ward@anu.edu.au>
-------------------------------------------------------------------------------
Distributed as part of Payu, Copyright 2011 Marshall Ward
Licensed under the Apache License, Version 2.0
http://www.apache.org/licenses/LICENSE-2.0
"""

# Python 3 preparation
from __future__ import print_function

# Standard Library
import os
import sys
import shlex
import shutil
import subprocess as sp
import datetime

# Local
import f90nml
from payu.modeldriver import Model
import payu.calendar as cal

class Cice(Model):

    #---
    def __init__(self, expt, name, config):
        super(Cice, self).__init__(expt, name, config)

        self.model_type = 'cice'
        self.default_exec = 'cice'

        # Default repo details
        self.repo_url = 'https://github.com/nicholash/cice.git'
        self.repo_tag = 'access'

        self.modules = ['pbs',
                        'openmpi']

        self.config_files = ['ice_in']

        self.ice_nml_fname = 'ice_in'


    #---
    def set_model_pathnames(self):
        super(Cice, self).set_model_pathnames()

        self.build_exec_path = os.path.join(self.codebase_path,
                                            'build_access-om_360x300_6p')

        ice_nml_path = os.path.join(self.control_path, self.ice_nml_fname)
        self.ice_nmls = f90nml.read(ice_nml_path)

        # Assume local paths are relative to the work path
        setup_nml = self.ice_nmls['setup_nml']

        res_path = os.path.normpath(setup_nml['restart_dir'])
        if not os.path.isabs(res_path):
            res_path = os.path.join(self.work_path, res_path)
        self.work_init_path = res_path
        self.work_restart_path = res_path

        work_out_path = os.path.normpath(setup_nml['history_dir'])
        if not os.path.isabs(work_out_path):
            work_out_path = os.path.join(self.work_path, work_out_path)
        self.work_output_path = work_out_path

        # Determine if there is a work input path
        grid_nml = self.ice_nmls['grid_nml']
        input_path, grid_fname = os.path.split(grid_nml['grid_file'])
        if input_path and not input_path == '.':
            assert not os.path.isabs(input_path)
            self.work_input_path = os.path.join(self.work_path, input_path)

        # Assert that kmt uses the same directory
        kmt_input_path, kmt_fname = os.path.split(grid_nml['kmt_file'])
        assert input_path == kmt_input_path


    #---
    def set_model_output_paths(self):
        super(Cice, self).set_model_output_paths()

        res_dir = self.ice_nmls['setup_nml']['restart_dir']

        # Use the local initialization restarts if present
        # TODO: Check for multiple res_paths across input paths?
        if self.expt.counter == 0:
            for input_path in self.input_paths:
                if os.path.isabs(res_dir):
                    init_res_path = res_dir
                else:
                    init_res_path = os.path.join(input_path, res_dir)
                if os.path.isdir(init_res_path):
                    self.prior_restart_path = init_res_path


    #---
    def get_prior_restart_files(self):
        return [f for f in os.listdir(self.prior_restart_path)
                if f.startswith('iced.')]


    #---
    def setup(self):
        super(Cice, self).setup()

        setup_nml = self.ice_nmls['setup_nml']
        init_date = datetime.date(year=setup_nml['year_init'], month=1, day=1)
            
        if setup_nml['days_per_year'] == 365:
            caltype = cal.NOLEAP
        else:
            caltype = cal.GREGORIAN

        if self.prior_output_path:

            # Generate ice.restart_file
            # TODO: Check the filenames more aggressively
            last_restart_file = sorted(self.get_prior_restart_files())[-1]

            res_ptr_path = os.path.join(self.work_init_path, 'ice.restart_file')
            with open(res_ptr_path, 'w') as res_ptr:
                print(last_restart_file, file=res_ptr)

            # Update input namelist
            setup_nml['runtype'] = 'continue'
            setup_nml['restart'] = True

            prior_nml_path = os.path.join(self.prior_output_path,
                                          self.ice_nml_fname)
            prior_setup_nml = f90nml.read(prior_nml_path)['setup_nml']

            # The total time in seconds since the beginning of
            # the experiment.
            total_runtime = prior_setup_nml['istep0'] + prior_setup_nml['npt']
            total_runtime = total_runtime * prior_setup_nml['dt']
            run_start_date = cal.date_plus_seconds(init_date, total_runtime, caltype)
        else:
            total_runtime = 0
            run_start_date = init_date

        # Set runtime for this run. 
        if self.expt.runtime:
            run_runtime = cal.runtime_from_date(run_start_date, 
                                                self.expt.runtime['years'],
                                                self.expt.runtime['months'],
                                                self.expt.runtime['days'], 
                                                caltype)

        else:
            run_runtime = setup_nml['npt']*setup_nml['dt']

        # Now write out new run start date and total runtime.
        setup_nml['npt'] = run_runtime / setup_nml['dt']
        assert(total_runtime % setup_nml['dt'] == 0)
        setup_nml['istep0'] = int(total_runtime / setup_nml['dt'])

        nml_path = os.path.join(self.work_path, self.ice_nml_fname)
        f90nml.write(self.ice_nmls, nml_path + '~')
        shutil.move(nml_path + '~', nml_path)

    #---
    def archive(self, **kwargs):

        for f in os.listdir(self.work_input_path):
            f_path = os.path.join(self.work_input_path, f)
            if os.path.islink(f_path):
                os.remove(f_path)

        # Archive restart files before processing model output
        cmd = 'mv {src} {dst}'.format(src=self.work_restart_path,
                                      dst=self.restart_path)
        rc = sp.Popen(shlex.split(cmd)).wait()
        assert rc == 0


    #---
    def collate(self):
        pass
