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

from payu.modeldriver import Model
import os
import imp
import datetime
import shutil
import fileinput
import f90nml

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

        self.restart = ['restart_dump.astart']

    def set_model_pathnames(self):
        super(UnifiedModel, self).set_model_pathnames()

        self.work_input_path = os.path.join(self.work_path, 'INPUT')

    #---
    def archive(self):
        raise NotImplementedError
        
        #f_src = os.path.join(model.work_path, self.restart)
        #f_dst = os.path.join(model.restart_path, self.restart)
        #shutil.move(f_src, f_dst)

    #---
    def collate(self):
        raise NotImplementedError

    #---
    def setup(self):
        super(UnifiedModel, self).setup()

        # Stage the UM restart file. What about the CABLE restart?
        #f_src = os.path.join(model.prior_restart_path, self.restart)
        #f_dst = os.path.join(model.work_path, self.restart)

        #if os.path.isfile(f_src):
        #    try:
        #        os.symlink(f_src, f_dst)
        #    except OSError as ec:
        #        if ec.errno == errno.EEXIST:
        #            os.remove(f_dst)
        #            os.symlink(f_src, f_dst)
        #        else:
        #            raise

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
            print(line)

        # Put all in the current environment. 
        os.environ.update(vars)

        # Modify namelists for a continuation.
        if self.prior_output_path:

            nml_path = os.path.join(self.work_path, 'namelist')
            nml = f90nml.read(nml_path)

            runtime = um_time_to_time(nml['NLSTCALL']['RUN_RESUBMIT_INC'])
            init_date = um_date_to_date(nml['NLSTCALL']['MODEL_BASIS_TIME'])

            new_init_date = init_date + runtime

            nml['NLSTCALL']['MODEL_BASIS_TIME'] = date_to_um_date(new_init_date)
            nml['NLSTCALL']['ANCIL_REFTIME'] = date_to_um_date(new_init_date)

            f90nml.write(nml, nml_path + '~')
            shutil.move(nml_path + '~', nml_path)

            # Tell CABLE that this is a continuation run.
            nml_path = os.path.join(self.work_path, 'cable.nml')
            nml = f90nml.read(nml_path)
            nml['cable']['cable_user%CABLE_RUNTIME_COUPLED'] = True
            f90nml.write(nml, nml_path + '~')
            shutil.move(nml_path + '~', nml_path)


    def date_to_um_date(date):

        assert date.day == 1 and date.hour == 0 and date.minute == 0 and date.second == 0

        return '{}, {}, {}, 0, 0, 0'.format(date.year, date.month, date.day)

    def um_date_to_date(um_date):
        """
        Convert a string with format 'year, month, day, hour, minute, second'
        to a datetime date.
        """

        years, months, days, hours, minutes, seconds = map(int, um_date.split(','))

        return datetime.datetime(years=years, months=months, days=days,
                                 hours=hours, minues=minutes, seconds=seconds)

    def um_time_to_time(um_date):
        """
        Convert a string with format 'year, month, day, hour, minute, second'
        to a datetime timedelta object.

        Only days are supported. 
        """

        years, months, days, hours, minutes, seconds = map(int, um_date.split(','))
        assert years == 0 and months == 0 and hours == 0 and minutes == 0 and seconds == 0

        return datetime.timedelta(days=days)
