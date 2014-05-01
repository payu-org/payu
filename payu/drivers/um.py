# coding: utf-8
"""
The payu interface for the UM atmosphere model
-------------------------------------------------------------------------------
Contact: Marshall Ward <marshall.ward@anu.edu.au>
-------------------------------------------------------------------------------
Distributed as part of Payu, Copyright 2011 Marshall Ward
Licensed under the Apache License, Version 2.0
http://www.apache.org/licenses/LICENSE-2.0
"""

from __future__ import print_function

from payu.modeldriver import Model
import os
import imp
import glob
import datetime
import shutil
import fileinput
import f90nml

from ..fsops import mkdir_p

class UnifiedModel(Model):

    #---
    def __init__(self, expt, name, config):
        super(UnifiedModel, self).__init__(expt, name, config)

        self.model_type = 'um'
        self.default_exec = 'um'

        self.modules = ['pbs',
                        'openmpi']

        # TODO: many of these can probably be ignored.
        self.config_files = ['CNTLALL', 'prefix.CNTLATM', 'prefix.CNTLGEN',
                             'prefix.CONTCNTL', 'errflag', 'exstat',
                             'ftxx', 'ftxx.new', 'ftxx.vars',
                             'hnlist', 'ihist', 'INITHIS',
                             'namelists', 'PPCNTL', 'prefix.PRESM_A',
                             'SIZES', 'STASHC', 'UAFILES_A', 'UAFLDS_A',
                             'parexe', 'cable.nml']

        self.restart = 'restart_dump.astart'

    def set_model_pathnames(self):
        super(UnifiedModel, self).set_model_pathnames()

        self.work_input_path = os.path.join(self.work_path, 'INPUT')

    #---
    def archive(self):

        mkdir_p(self.restart_path)

        # Need to figure out the end date of the model.
        nml_path = os.path.join(self.work_path, 'namelists')
        nml = f90nml.read(nml_path)
        runtime = um_time_to_time(nml['NLSTCALL']['RUN_RESUBMIT_INC'])
        init_date = um_date_to_date(nml['NLSTCALL']['MODEL_BASIS_TIME'])

        end_date = date_to_um_dump_date(init_date + runtime)
       
        restart_dump = os.path.join(self.work_path,
                                    'aiihca.da{}'.format(end_date))
        f_dst = os.path.join(self.restart_path, self.restart)
        shutil.copy(restart_dump, f_dst)

    #---
    def collate(self):
        raise NotImplementedError

    #---
    def setup(self):
        super(UnifiedModel, self).setup()

        # Stage the UM restart file.
        if self.prior_restart_path:
            f_src = os.path.join(self.prior_restart_path, self.restart)
            f_dst = os.path.join(self.work_path, self.restart)

            if os.path.isfile(f_src):
                try:
                    os.symlink(f_src, f_dst)
                except OSError as ec:
                    if ec.errno == errno.EEXIST:
                        os.remove(f_dst)
                        os.symlink(f_src, f_dst)
                    else:
                        raise

        # Set up environment variables needed to run UM. 
        # Look for a python file in the config directory.
        um_env = imp.load_source('um_env',
                os.path.join(self.control_path, 'um_env.py'))
        vars = um_env.vars

        assert len(self.input_paths) == 1

        # Set some paths
        for k in vars.keys():
            vars[k] = vars[k].format(input_path=self.input_paths[0],
                                     work_path=self.work_path)

        # Paths need to be set in parexe also.
        parexe = os.path.join(self.work_path, 'parexe')
        for line in fileinput.input(parexe, inplace=True):
            line = line.format(input_path=self.input_paths[0],
                               work_path=self.work_path)
            print(line, end='')

        # Put all in the current environment. 
        os.environ.update(vars)

        # Modify namelists for a continuation run.
        if self.prior_output_path:

            nml_path = os.path.join(self.work_path, 'namelists')
            nml = f90nml.read(nml_path)

            runtime = um_time_to_time(nml['NLSTCALL']['RUN_RESUBMIT_INC'])
            init_date = um_date_to_date(nml['NLSTCALL']['MODEL_BASIS_TIME'])

            new_init_date = init_date + runtime

            nml['NLSTCALL']['MODEL_BASIS_TIME'] = date_to_um_date(new_init_date)
            nml['NLSTCALL']['ANCIL_REFTIME'] = date_to_um_date(new_init_date)

            f90nml.write(nml, nml_path + '~')
            shutil.move(nml_path + '~', nml_path)

            # Tell CABLE that this is a continuation run.
            # FIXME: can't use f90nml here because it does not support '%'
            nml_path = os.path.join(self.work_path, 'cable.nml')
            for line in fileinput.input(nml_path, inplace=True):
                line = line.replace('cable_user%CABLE_RUNTIME_COUPLED = .FALSE.', 
                                    'cable_user%CABLE_RUNTIME_COUPLED = .TRUE.')
                print(line, end='')


def date_to_um_dump_date(date):
    """
    Convert a time date object to a um dump format date which is yymd0
    
    To accomodate two digit months and days the UM uses letters. e.g. 1st oct 
    is writting 01a10.
    """

    assert(date.month <= 12)

    month = str(date.month)
    if date.month == 10:
        month = 'a'
    elif date.month == 11:
        month = 'b'
    elif date.month == 12:
        month = 'c'

    return (str(date.year).zfill(2) + month + str(date.day) + str(0))


def date_to_um_date(date):
    """
    Convert a date object to 'year, month, day, hour, minute, second.'
    """

    assert date.day == 1 and date.hour == 0 and date.minute == 0 and date.second == 0

    return [date.year, date.month, date.day, 0, 0, 0] 

def um_date_to_date(d):
    """
    Convert a string with format 'year, month, day, hour, minute, second'
    to a datetime date.
    """

    return datetime.datetime(year=d[0], month=d[1], day=d[2],
                             hour=d[3], minute=d[4], second=d[5])

def um_time_to_time(d):
    """
    Convert a string with format 'year, month, day, hour, minute, second'
    to a datetime timedelta object.

    Only days are supported. 
    """

    assert d[0] == 0 and d[1] == 0 and d[3] == 0 and d[4] == 0 and d[5] == 0

    return datetime.timedelta(days=d[2])
