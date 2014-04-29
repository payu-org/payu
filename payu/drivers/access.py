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

                    # Calculate start date of the run, and update the total
                    # experiment runtime. 
                    prior_cpl_fpath = os.path.join(model.prior_output_path,
                                                   cpl_fname)
                    prior_cpl_nml = f90nml.read(prior_cpl_fpath)
                    cpl_nml_grp = prior_cpl_nml[cpl_group]
                    # The total time in seconds since the beginning of
                    # the experiment.
                    exp_runtime = float(cpl_nml_grp[runtime0_key]
                                     + cpl_nml_grp['runtime'])
                    exp_runtime = datetime.timedelta(seconds=exp_runtime)

                    # experiment start date.
                    exp_init_date = int_to_date(prior_cpl_nml[cpl_group]['init_date'])
                    # run start date.
                    run_init_date = exp_init_date + exp_runtime

                    # Skip ahead if using a NOLEAP calendar
                    if cpl_nml_grp['caltype'] == 0:
                        dt_leap = get_leapdays(exp_init_date,
                                               exp_init_date + exp_runtime)
                        run_init_date += dt_leap

                else:
                    run_init_date = int_to_date(cpl_nml[cpl_group]['init_date'])
                    exp_runtime = datetime.timedelta(seconds=0)

                # If there is a leap day in this run then increase runtime.
                run_runtime = cpl_nml[cpl_group]['runtime']
                leap_days = get_leapdays(run_init_date, run_init_date +
                                         datetime.timedelta(seconds=run_runtime))
                run_runtime += (leap_days.total_seconds())
                cpl_nml[cpl_group]['runtime'] = run_runtime

                cpl_nml[cpl_group]['inidate'] = date_to_int(run_init_date)
                cpl_nml[cpl_group][runtime0_key] = exp_runtime.total_seconds()

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


def int_to_date(date):
    """
    Convert an int of form yyyymmdd to a python date object.
    """

    year = date / 10**4
    month = date % 10**4 / 10**2
    day = date % 10**2

    return datetime.date(year, month, day)

def date_to_int(date):

    return (date.year * 10**4 + date.month * 10**2 + date.day)


def includes_leap_day(init_date, runtime):

    assert(date.day == 1)

    if (calendar.isleap(date.year) and 
        ((date.month == 1 and runtime >= 60*86400) or
        (date.month == 2 and runtime >= 29*86400))):
        return  True
    
    return False


def get_leapdays(init_date, final_date):
    """
    Find the number of leap days between arbitrary dates.

    FIXME: calculate this instead of iterating. 
    """

    curr_date = init_date 
    leap_days = 0

    while curr_date != final_date:

        if curr_date.month == 2 and curr_date.day == 29:
            leap_days += 1

        curr_date += datetime.timedelta(days=1)

    return datetime.timedelta(days=leap_days)
