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
import errno
import os
import stat
import sys
import shlex
import shutil
import subprocess as sp
import datetime

# Extensions
import f90nml

# Local
import payu.calendar as cal
from payu.fsops import make_symlink
from payu.models.model import Model
from payu.namcouple import Namcouple


class Cice(Model):

    def __init__(self, expt, name, config):
        super(Cice, self).__init__(expt, name, config)

        self.model_type = 'cice'
        self.default_exec = 'cice'

        # Default repo details
        self.repo_url = 'https://github.com/CWSL/cice4.git'
        self.repo_tag = 'access'

        self.config_files = ['ice_in']

        self.ice_nml_fname = 'ice_in'

        self.set_timestep = self.set_local_timestep

    def set_model_pathnames(self):
        super(Cice, self).set_model_pathnames()

        self.build_exec_path = os.path.join(self.codebase_path,
                                            'build_access-om_360x300_6p')

        ice_nml_path = os.path.join(self.control_path, self.ice_nml_fname)
        self.ice_in = f90nml.read(ice_nml_path)

        # Assume local paths are relative to the work path
        setup_nml = self.ice_in['setup_nml']

        res_path = os.path.normpath(setup_nml['restart_dir'])
        input_dir = setup_nml.get('input_dir', None)

        if input_dir is None:
            # Default to reading and writing inputs/restarts in-place
            input_path = res_path
        else:
            input_path = os.path.normpath(input_dir)

        # Determine if there is a work input path from grid path
        grid_nml = self.ice_in['grid_nml']
        path, _ = os.path.split(grid_nml['grid_file'])
        if path and not path == os.path.curdir:
            assert not os.path.isabs(path)
            path = os.path.normpath(path)
            # Get input_dir from grid_file path unless otherwise specified
            if input_dir is None:
                input_path = path

        # Check for consistency in input paths due to cice having the same
        # information in multiple locations
        if path != input_path:
            print('payu: error: '
                  'Grid file path in {nmlfile} ({gridpath}) does not match '
                  'input path ({inputpath})'.format(
                    nmlfile=self.ice_nml_fname,
                    gridpath=path,
                    inputpath=input_path))
            sys.exit(1)

        # Check paths are consistent in namelist
        tmp_path, _ = os.path.split(self.ice_in['grid_nml'].get('kmt_file'))
        tmp_path = os.path.normpath(tmp_path)
        if not path == tmp_path:
            print('payu: error: '
                  'Paths for kmt_file ({varpath}) and grid_file '
                  '({gridpath}) in {nmlfile} do not '
                  'match'.format(varpath=tmp_path,
                                 gridpath=path,
                                 nmlfile=self.ice_nml_fname))
            sys.exit(1)

        # Check paths are consistent in namelist
        tmp_path, _ = os.path.split(self.ice_in['setup_nml'].get('pointer_file'))
        tmp_path = os.path.normpath(tmp_path)
        if not path == tmp_path:
            print('payu: warning: '
                  'Paths for pointer_file ({varpath}) and grid_file '
                  '({gridpath}) in {nmlfile} do not '
                  'match'.format(varpath=tmp_path,
                                 gridpath=path,
                                 nmlfile=self.ice_nml_fname))

        if not os.path.isabs(input_path):
            input_path = os.path.join(self.work_path, input_path)
        self.work_input_path = input_path
        self.work_init_path = self.work_input_path

        if not os.path.isabs(res_path):
            res_path = os.path.join(self.work_path, res_path)
        self.work_restart_path = res_path

        work_out_path = os.path.normpath(setup_nml['history_dir'])

        if not os.path.isabs(work_out_path):
            work_out_path = os.path.join(self.work_path, work_out_path)
        self.work_output_path = work_out_path

    def set_model_output_paths(self):
        super(Cice, self).set_model_output_paths()

        res_dir = self.ice_in['setup_nml']['restart_dir']

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

    def get_prior_restart_files(self):
        restart_files = [f for f in os.listdir(self.prior_restart_path)
                         if f.startswith('iced.')]
        return [sorted(restart_files)[-1]]

    def get_ptr_restart_dir(self):
        return os.path.relpath(self.work_input_path, self.work_path)

    def get_access_ptr_restart_dir(self):
        # The ACCESS build of CICE assumes that restart_dir is 'RESTART'
        # TODO: Move to ACCESS driver
        return '.'

    def setup(self):
        super(Cice, self).setup()

        # Change perms of restart files, these get overwritten so much be
        # writable.
        for fname in ['o2i.nc', 'i2o.nc', 'u_star.nc', 'grid.nc', 'kmt.nc',
                      'monthly_sstsss.nc', 'mice.nc']:
            path = os.path.join(self.work_input_path, fname)
            if os.path.exists(path):
                perm = (stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
                        | stat.S_IWUSR)
                os.chmod(path, perm)

        setup_nml = self.ice_in['setup_nml']
        init_date = datetime.date(year=setup_nml['year_init'], month=1, day=1)

        if setup_nml['days_per_year'] == 365:
            caltype = cal.NOLEAP
        else:
            caltype = cal.GREGORIAN

        if self.prior_restart_path:
            # Generate ice.restart_file
            # TODO: better check of restart filename
            iced_restart_file = None
            for f in self.get_prior_restart_files():
                if 'iced.' in f:
                    iced_restart_file = f

            if iced_restart_file is None:
                print('payu: error: No restart file available.')
                sys.exit(errno.ENOENT)

            res_ptr_path = os.path.join(self.work_input_path,
                                        'ice.restart_file')
            with open(res_ptr_path, 'w') as res_ptr:
                res_dir = self.get_ptr_restart_dir()
                print(os.path.join(res_dir, iced_restart_file), file=res_ptr)

            # Update input namelist
            setup_nml['runtype'] = 'continue'
            setup_nml['restart'] = True

            prior_nml_path = os.path.join(self.prior_restart_path,
                                          self.ice_nml_fname)

            # With later versions this file exists in the prior restart path,
            # but this was not always the case, so check, and if not there use
            # prior output path
            if not os.path.exists(prior_nml_path) and self.prior_output_path:
                prior_nml_path = os.path.join(self.prior_output_path,
                                              self.ice_nml_fname)

            # If we cannot find a prior namelist, then we cannot determine
            # the start time and must abort the run.
            if not os.path.exists(prior_nml_path):
                print('payu: error: Cannot find prior namelist {nml}'.format(
                    nml=self.ice_nml_fname))
                sys.exit(errno.ENOENT)

            prior_setup_nml = f90nml.read(prior_nml_path)['setup_nml']

            # The total time in seconds since the beginning of the experiment
            total_runtime = prior_setup_nml['istep0'] + prior_setup_nml['npt']
            total_runtime = total_runtime * prior_setup_nml['dt']
            run_start_date = cal.date_plus_seconds(init_date, total_runtime,
                                                   caltype)
        else:
            # Locate and link any restart files (if required)
            if not setup_nml['ice_ic'] in ('none', 'default'):
                self.link_restart(setup_nml['ice_ic'])

            if setup_nml['restart']:
                self.link_restart(setup_nml['pointer_file'])

            # Initialise runtime
            total_runtime = 0
            run_start_date = init_date

        # Set runtime for this run.
        if self.expt.runtime:
            run_runtime = cal.runtime_from_date(
                run_start_date,
                self.expt.runtime['years'],
                self.expt.runtime['months'],
                self.expt.runtime['days'],
                self.expt.runtime.get('seconds', 0),
                caltype
            )
        else:
            run_runtime = setup_nml['npt']*setup_nml['dt']

        # Now write out new run start date and total runtime.
        setup_nml['npt'] = run_runtime / setup_nml['dt']
        assert(total_runtime % setup_nml['dt'] == 0)
        setup_nml['istep0'] = int(total_runtime / setup_nml['dt'])

        # Force creation of a dump (restart) file at end of run
        setup_nml['dump_last'] = True

        nml_path = os.path.join(self.work_path, self.ice_nml_fname)
        self.ice_in.write(nml_path, force=True)

    def set_local_timestep(self, t_step):
        dt = self.ice_in['setup_nml']['dt']
        npt = self.ice_in['setup_nml']['npt']

        self.ice_in['setup_nml']['dt'] = t_step
        self.ice_in['setup_nml']['npt'] = (int(dt) * int(npt)) // int(t_step)

        ice_in_path = os.path.join(self.work_path, self.ice_nml_fname)
        self.ice_in.write(ice_in_path, force=True)

    def set_access_timestep(self, t_step):
        # TODO: Figure out some way to move this to the ACCESS driver
        # Re-read ice timestep and move this over there
        self.set_local_timestep(t_step)

        input_ice_path = os.path.join(self.work_path, 'input_ice.nml')
        input_ice = f90nml.read(input_ice_path)

        input_ice['coupling_nml']['dt_cice'] = t_step

        input_ice.write(input_ice_path, force=True)

    def set_oasis_timestep(self, t_step):
        # TODO: Move over to access driver
        for model in self.expt.models:
            if model.model_type == 'oasis':
                namcpl_path = os.path.join(model.work_path, 'namcouple')
                namcpl = Namcouple(namcpl_path, 'access')
                namcpl.set_ice_timestep(str(t_step))
                namcpl.write()

    def archive(self, **kwargs):

        for f in os.listdir(self.work_input_path):
            f_path = os.path.join(self.work_input_path, f)
            if os.path.islink(f_path):
                os.remove(f_path)

        os.rename(self.work_restart_path, self.restart_path)

    def collate(self):
        pass

    def link_restart(self, fpath):

        input_work_path = os.path.join(self.work_path, fpath)

        # Exit if the restart file already exists
        if os.path.isfile(input_work_path):
            return

        input_path = None
        for i_path in self.input_paths:
            test_path = os.path.join(i_path, fpath)
            if os.path.isfile(test_path):
                input_path = test_path
                break
        assert input_path

        make_symlink(input_path, input_work_path)
