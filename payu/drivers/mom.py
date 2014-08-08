# coding: utf-8
"""
The payu interface for MOM
-------------------------------------------------------------------------------
Primary Contact: Marshall Ward <marshall.ward@anu.edu.au>
-------------------------------------------------------------------------------
Distributed as part of Payu, Copyright 2011-2012 Marshall Ward
Licensed under the Apache License, Version 2.0
http://www.apache.org/licenses/LICENSE-2.0
"""

# Standard Library
import os
import shlex
import shutil
import subprocess as sp
import sys

# Local
import f90nml
from payu.drivers.fms import Fms
from payu.fsops import mkdir_p

# Module support (for NCO)
execfile('/opt/Modules/default/init/python')


class Mom(Fms):

    #---
    def __init__(self, expt, name, config):

        # FMS initalisation
        super(Mom, self).__init__(expt, name, config)

        # Append the MOM-specific configuration details
        self.config['core2iaf'] = expt.config.get('core2iaf')

        # Model-specific configuration
        self.model_type = 'mom'
        self.default_exec = 'fms_MOM_SIS.x'

        # Default repo and build details.
        self.repo_url = 'git://github.com/BreakawayLabs/mom.git'
        self.repo_tag = 'master'
        self.build_command = './MOM_compile.csh --platform nci --type MOM_SIS'

        self.modules = ['pbs',
                        'openmpi']

        self.config_files = ['data_table',
                             'diag_table',
                             'field_table',
                             'input.nml']

        self.optional_config_files = ['blob_diag_table']


    #---
    def set_model_pathnames(self):
        super(Mom, self).set_model_pathnames()

        self.build_exec_path = os.path.join(self.codebase_path, 'exec', 'nci',
                                            'MOM_SIS')
        self.build_path = os.path.join(self.codebase_path, 'exp')


    #---
    def build_model(self):
        super(Mom, self).build_model()

        # Model is built, now copy over mppnccombine.
        mppnc_exec = 'mppnccombine.nci'

        mppnc_src = os.path.join(self.codebase_path, 'bin', mppnc_exec)
        mppnc_dest = os.path.join(self.expt.lab.bin_path, 'mppnccombine')
        shutil.copy(mppnc_src, mppnc_dest)


    #---
    def setup(self):
        # FMS initialisation
        super(Mom, self).setup()

        use_core2iaf = self.config.get('core2iaf')
        if use_core2iaf:
            self.core2iaf_setup()

        # Set the runtime. 
        if self.expt.runtime:
            nml_path = os.path.join(self.work_path, 'input.nml')
            nml = f90nml.read(nml_path)
            ocean_solo_nml = nml['ocean_solo_nml']

            ocean_solo_nml['years'] = self.expt.runtime['years']
            ocean_solo_nml['months'] = self.expt.runtime['months']
            ocean_solo_nml['days'] = self.expt.runtime['days']

            f90nml.write(nml, nml_path + '~')
            shutil.move(nml_path + '~', nml_path)

    #---
    def core2iaf_setup(self, core2iaf_path=None, driver_name=None):
        # This is a very long method
        # TODO: Separate into sub-methods

        import scipy.io.netcdf as nc
        module('load', 'nco')

        # Need to make these input arguments
        default_core2iaf_path = '/g/data1/v45/mom/core2iaf'
        if core2iaf_path == None:
            core2iaf_path = default_core2iaf_path

        default_driver_name = 'coupler'
        if driver_name == None:
            driver_name = default_driver_name

        # TODO: Extract this from the input files
        max_days = 60 * 365

        # Calendar constants
        NO_CALENDAR, THIRTY_DAY_MONTHS, JULIAN, GREGORIAN, NOLEAP = range(5)
        month_days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

        date_vname = {'coupler': 'current_date', 'ocean_solo': 'date_init'}

        #----------
        # t_start
        tstamp_fname = driver_name + '.res'
        if self.prior_restart_path:
            prior_tstamp_path = os.path.join(self.prior_restart_path,
                                             tstamp_fname)
            tstamp_file = open(prior_tstamp_path, 'r')

            t_calendar = tstamp_file.readline().split()
            assert int(t_calendar[0]) == NOLEAP

            # First timestamp is unused
            last_tstamp = tstamp_file.readline().split()

            tstamp = tstamp_file.readline().split()
            tstamp_file.close()

        else:
            input_nml = open('input.nml', 'r')
            for line in input_nml:
                if line.strip().startswith(date_vname[driver_name]):
                    tstamp = line.split('=')[1].split(',')
                    break

        # Parse timestamp
        t_yr, t_mon, t_day, t_hr, t_min, t_sec = [int(t) for t in tstamp[:6]]

        cal_start = {'years': t_yr, 'months': t_mon, 'days': t_day,
                     'hours': t_hr, 'minutes': t_min, 'seconds': t_sec}

        t_monthdays = sum(month_days[:t_mon-1])

        t_start = 365.*(t_yr - 1) + t_monthdays + (t_day - 1) \
                 + (t_hr + (t_min + t_sec / 60.) / 60.) / 24.

        #--------
        # t_end

        cal_dt = {'years': 0, 'months': 0, 'days': 0,
                  'hours': 0, 'minutes': 0, 'seconds': 0}

        input_nml = open('input.nml', 'r')
        for line in input_nml:
            for vname in cal_dt.keys():
                if line.strip().startswith(vname):
                    val = int(line.strip().split('=')[-1].rstrip(','))
                    cal_dt[vname] = val

        m1 = cal_start['months'] - 1
        dm = cal_dt['months']

        dt_monthdays = 365. * (dm // 12) \
                      + sum(month_days[m1:(m1 + (dm % 12))]) \
                      + sum(month_days[:max(0, m1 + (dm % 12) - 12)])

        dt_days = 365. * cal_dt['years'] + dt_monthdays + cal_dt['days'] \
                 + (cal_dt['hours']
                    + (cal_dt['minutes'] + cal_dt['seconds'] / 60.) / 60.) / 24.

        t_end = t_start + dt_days

        print('t_start: {}, t_end: {}'.format(t_start, t_end))

        # TODO: Periodic forcing cycle
        # Non-integer ratios will be complicated. This is a temporary solution

        t_start = t_start % max_days
        # Check to prevent edge case t_end == max_days)
        if t_end > max_days:
            t_end = t_end % max_days

        #---
        # Produce forcing files

        # TODO: ncks fails if t_end is less than smallest forcing time
        # (But MOM may reject this case anyway)

        in_fnames = os.listdir(core2iaf_path)

        for f in in_fnames:
            fsplit = f.split('.')
            out_fname = '.'.join([fsplit[0], fsplit[-1]])
            in_fpath = os.path.join(core2iaf_path, f)
            out_fpath = os.path.join(self.work_path, 'INPUT', out_fname)

            # Locate the time axis in each file
            # TODO: might be a better way to do this
            f_nc = nc.netcdf_file(in_fpath, 'r')
            for k in f_nc.variables:
                if k.lower() == 'time':
                    t_axis = k
            f_nc.close()
            assert t_axis

            cmd = 'ncks -d %s,%.1f,%.1f -o %s %s' \
                    % (t_axis, t_start, t_end, out_fpath, in_fpath)
            rc = sp.Popen(shlex.split(cmd)).wait()
            assert rc == 0
