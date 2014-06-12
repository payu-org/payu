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

# Standard Library
import datetime
import fileinput
import imp
import os
import shutil

# Local
from payu.fsops import mkdir_p, make_symlink
from payu.modeldriver import Model
from payu.fnamelist import FortranNamelist
import payu.calendar as cal

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
                             'CONTCNTL', 'errflag', 'exstat',
                             'ftxx', 'ftxx.new', 'ftxx.vars',
                             'hnlist', 'ihist', 'INITHIS',
                             'namelists', 'PPCNTL', 'prefix.PRESM_A',
                             'SIZES', 'STASHC', 'UAFILES_A', 'UAFLDS_A',
                             'parexe', 'cable.nml']

        self.restart = 'restart_dump.astart'


    #---
    def set_model_pathnames(self):
        super(UnifiedModel, self).set_model_pathnames()

        self.work_input_path = os.path.join(self.work_path, 'INPUT')


    #---
    def archive(self):

        mkdir_p(self.restart_path)

        # Need to figure out the end date of the model.
        nml_path = os.path.join(self.work_path, 'namelists')
        nml = FortranNamelist(nml_path)

        resubmit_inc = nml.get_value('NLSTCALL','RUN_RESUBMIT_INC')
        resubmit_inc = map(int, resubmit_inc.split(','))
        runtime = um_time_to_time(resubmit_inc)
        runtime = datetime.timedelta(seconds=runtime)

        basis_time = nml.get_value('NLSTCALL','MODEL_BASIS_TIME')
        basis_time = map(int, basis_time.split(','))
        init_date = um_date_to_date(basis_time)

        end_date = date_to_um_dump_date(init_date + runtime)

        restart_dump = os.path.join(self.work_path,
                                    'aiihca.da{}'.format(end_date))
        f_dst = os.path.join(self.restart_path, self.restart)
        shutil.copy(restart_dump, f_dst)


    #---
    def collate(self):
        pass


    #---
    def setup(self):
        super(UnifiedModel, self).setup()

        # Stage the UM restart file.
        if self.prior_restart_path:
            f_src = os.path.join(self.prior_restart_path, self.restart)
            f_dst = os.path.join(self.work_input_path, self.restart)

            if os.path.isfile(f_src):
                make_symlink(f_src, f_dst)

        # Set up environment variables needed to run UM.
        # Look for a python file in the config directory.
        um_env = imp.load_source('um_env',
                os.path.join(self.control_path, 'um_env.py'))
        vars = um_env.vars

        assert len(self.input_paths) == 1

        # Set paths in environment variables.
        for k in vars.keys():
            vars[k] = vars[k].format(input_path=self.input_paths[0],
                                     work_path=self.work_path)
        os.environ.update(vars)

        # The above needs to be done in parexe also.
        # FIXME: a better way to do this or remove.
        parexe = os.path.join(self.work_path, 'parexe')
        for line in fileinput.input(parexe, inplace=True):
            line = line.format(input_path=self.input_paths[0],
                               work_path=self.work_path)

            print(line, end='')


        # FIXME: The UM does some ugly things with namelists, e.g. it will
        # repeat the same namelist (with different contents) multiple times
        # in the same file and rely on file advancement to read it multiple
        # times. At present f90nml doesn't have support for this so we use
        # a regex search and replace approach.
        work_nml_path = os.path.join(self.work_path, 'namelists')
        work_nml = FortranNamelist(work_nml_path)

        # Modify namelists for a continuation run.
        if self.prior_output_path:

            prior_nml_path = os.path.join(self.prior_output_path, 'namelists')
            prior_nml = FortranNamelist(prior_nml_path)

            basis_time = prior_nml.get_value('NLSTCALL', 'MODEL_BASIS_TIME')
            basis_time = map(int, basis_time.split(','))
            init_date = um_date_to_date(basis_time)
            resubmit_inc = prior_nml.get_value('NLSTCALL', 'RUN_RESUBMIT_INC')
            resubmit_inc = map(int, resubmit_inc.split(','))
            runtime = um_time_to_time(resubmit_inc)

            run_start_date = cal.date_plus_seconds(init_date,
                                                   runtime,
                                                   cal.GREGORIAN)

            # Write out and save new calendar information. 
            run_start_date_um = date_to_um_date(run_start_date)
            run_start_date_um = str(run_start_date_um)[1:-1]
            work_nml.set_value('NLSTCALL', 'MODEL_BASIS_TIME',
                               run_start_date_um)
            work_nml.set_value('NLSTCALL', 'ANCIL_REFTIME',
                               run_start_date_um)

            # Tell CABLE that this is a continuation run.
            # FIXME: can't use f90nml here because it does not support '%'
            cable_nml_path = os.path.join(self.work_path, 'cable.nml')
            cable_nml = FortranNamelist(cable_nml_path)
            cable_nml.set_value('cable', 'cable_user%CABLE_RUNTIME_COUPLED',
                                '.FALSE.')
            cable_nml.write()

        else:
            run_start_date = work_nml.get_value('NLSTCALL', 'MODEL_BASIS_TIME')
            run_start_date = map(int, run_start_date.split(','))
            run_start_date = um_date_to_date(run_start_date)
            

        # Set the runtime for this run. 
        if self.expt.runtime:
            run_runtime = cal.runtime_from_date(run_start_date, 
                                                self.expt.runtime['years'],
                                                self.expt.runtime['months'],
                                                self.expt.runtime['days'], 
                                                cal.GREGORIAN)
            run_runtime = time_to_um_time(run_runtime)
            # Convert to str.
            run_runtime = str(run_runtime)[1:-1]
            work_nml.set_value('NLSTCALL', 'RUN_RESUBMIT_INC', run_runtime)
            work_nml.set_value('NLSTCALL', 'RUN_TARGET_END', run_runtime)
            work_nml.set_value('STSHCOMP', 'RUN_TARGET_END', run_runtime)
                               
 
        work_nml.write()


#---
def date_to_um_dump_date(date):
    """
    Convert a time date object to a um dump format date which is yymd0

    To accomodate two digit months and days the UM uses letters. e.g. 1st oct
    is writting 01a10.
    """

    assert(date.month <= 12)
    month = hex(date.month)[2:]

    return (str(date.year).zfill(2) + month + str(date.day) + str(0))


#---
def date_to_um_date(date):
    """
    Convert a date object to 'year, month, day, hour, minute, second.'
    """

    assert date.hour == 0 and date.minute == 0 and date.second == 0

    return [date.year, date.month, date.day, 0, 0, 0]


#---
def um_date_to_date(d):
    """
    Convert a string with format 'year, month, day, hour, minute, second'
    to a datetime date.
    """

    return datetime.datetime(year=d[0], month=d[1], day=d[2],
                             hour=d[3], minute=d[4], second=d[5])


#---
def um_time_to_time(d):
    """
    Convert a list with format [year, month, day, hour, minute, second]
    to a number of seconds.

    Only days are supported.
    """

    assert d[0] == 0 and d[1] == 0 and d[3] == 0 and d[4] == 0 and d[5] == 0

    return d[2]*86400

def time_to_um_time(seconds):
    """
    Convert a number of seconds to a list with format [year, month, day, hour,
       minute, second]

    Only days are supported.
    """

    assert(seconds % 86400 == 0)

    return [0, 0, seconds / 86400, 0, 0, 0]
