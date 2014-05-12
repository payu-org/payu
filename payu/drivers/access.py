# coding: utf-8
"""
The payu interface for the ACCESS coupled climate model
-------------------------------------------------------------------------------
Contact: Marshall Ward <marshall.ward@anu.edu.au>
-------------------------------------------------------------------------------
Distributed as part of Payu, Copyright 2011 Marshall Ward
Licensed under the Apache License, Version 2.0
http://www.apache.org/licenses/LICENSE-2.0
"""

# Standard Library
import datetime
import errno
import os
import shutil

# Extensions
import f90nml

# Local
from payu.modeldriver import Model

class Access(Model):

    #---
    def __init__(self, expt, name, config):
        super(Access, self).__init__(expt, name, config)

        self.model_type = 'access'

        self.modules = ['pbs',
                        'openmpi']

        for model in self.expt.models:
            if model.model_type == 'cice':
                model.config_files = ['cice_in.nml',
                                      'input_ice.nml',
                                      'input_ice_gfdl.nml',
                                      'input_ice_monin.nml']

                model.ice_nml_fname = 'cice_in.nml'

                model.access_restarts = ['u_star.nc', 'sicemass.nc']

    #---
    def setup(self):

        cpl_keys = {'cice': ('input_ice.nml', 'coupling_nml', 'runtime0'),
                    'matm': ('input_atm.nml', 'coupling', 'truntime0')}

        for model in self.expt.models:

            if model.model_type == 'cice':

                # Stage the supplemental input files
                if model.prior_restart_path:
                    for f_name in model.access_restarts:
                        f_src = os.path.join(model.prior_restart_path, f_name)
                        f_dst = os.path.join(model.work_input_path, f_name)

                        if os.path.isfile(f_src):

                            try:
                                os.symlink(f_src, f_dst)
                            except OSError as ec:
                                if ec.errno == errno.EEXIST:
                                    os.remove(f_dst)
                                    os.symlink(f_src, f_dst)
                                else:
                                    raise


            if model.model_type in ('cice', 'matm'):

                # Update the supplemental OASIS namelists
                cpl_fname, cpl_group, runtime0_key = cpl_keys[model.model_type]

                cpl_fpath = os.path.join(model.work_path, cpl_fname)
                cpl_nml = f90nml.read(cpl_fpath)

                if model.prior_output_path:
                    prior_cpl_fpath = os.path.join(model.prior_output_path,
                                                   cpl_fname)
                    prior_cpl_nml = f90nml.read(prior_cpl_fpath)

                    # Calculate initial runtime (runtime0, in seconds)
                    cpl_nml_grp = prior_cpl_nml[cpl_group]
                    runtime0 = float(cpl_nml_grp[runtime0_key]
                                     + cpl_nml_grp['runtime'])
                    # runtime (without the 0) is the runtime of the current run.
                    runtime = cpl_nml_grp['runtime']

                    prior_idate = prior_cpl_nml[cpl_group]['init_date']

                    prior_year = prior_idate / 10**4
                    prior_month = (prior_idate % 10**4 / 10**2)
                    prior_day = (prior_idate % 10**2)

                    init_date = datetime.date(prior_year, prior_month,
                                              prior_day)

                    dt_run = datetime.timedelta(seconds=runtime0)
                    t_new = init_date + dt_run

                    # Skip ahead if using a NOLEAP calendar
                    if cpl_nml_grp['caltype'] == 0:
                        dt_leap = get_leapdays(init_date, init_date + dt_run)
                        t_new += dt_leap

                    t_new = init_date + dt_run
                    inidate = (t_new.year * 10**4 + t_new.month * 10**2
                               + t_new.day)

                    def includes_leap_day(date, runtime):
                        assert(date.day == 1)
                    
                        if (calendar.isleap(date.year) and 
                            ((date.month == 1 and runtime >= 60*86400) or
                            (date.month == 2 and runtime >= 29*86400))):
                            return  True
                        
                        return False
                        
                    # If the new inidate is a leap year, then we need to
                    # extend the runtime.
                    if includes_leap_day(t_new, runtime):
                        runtime += 86400

                    cpl_nml[cpl_group]['runtime'] = runtime

                else:
                    inidate = cpl_nml[cpl_group]['init_date']
                    runtime0 = 0.

                cpl_nml[cpl_group]['inidate'] = inidate
                cpl_nml[cpl_group][runtime0_key] = runtime0

                if model.model_type == 'cice':
                    cpl_nml[cpl_group]['jobnum'] = 1 + self.expt.counter

                nml_work_path = os.path.join(model.work_path, cpl_fname)
                f90nml.write(cpl_nml, nml_work_path + '~')
                shutil.move(nml_work_path + '~', nml_work_path)


    #---
    def archive(self):

        for model in self.expt.models:
            if model.model_type == 'cice':

                # Move supplemental restart files to RESTART path
                for f_name in model.access_restarts:
                    f_src = os.path.join(model.work_path, f_name)
                    f_dst = os.path.join(model.restart_path, f_name)

                    shutil.move(f_src, f_dst)


    #---
    def collate(self):
        raise NotImplementedError


def get_leapdays(init_date, final_date):

    # Julian leap days
    n_days = (final_date.year - 1) // 4 - (init_date.year - 1) // 4

    # Gregorian correction
    n_days -= (final_date.year - 1) // 100 - (init_date.year - 1) // 100
    n_days += (final_date.year - 1) // 400 - (init_date.year - 1) // 400

    # TODO: Internal date correction

    return datetime.timedelta(days=n_days)
