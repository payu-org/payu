# coding: utf-8
"""
The payu interface for MOM4
===============================================================================
Primary Contact:    Marshall Ward (marshall.ward@anu.edu.au)
"""

import os
import subprocess as sp
from fms import fms

class mom4(fms):
    #---
    def __init__(self, **kwargs):
        
        # FMS initalisation
        super(mom4, self).__init__(**kwargs)
        
        # Model-specific configuration
        self.model_name = 'mom4'
        self.default_exec = 'mom4'
        
        self.modules = ['pbs',
                        'openmpi',
                        'nco']
        
        self.config_files = ['data_table',
                             'diag_table',
                             'field_table',
                             'input.nml']
        
        self.path_names(**kwargs)
        self.load_modules()
    
    
    #---
    def core2iaf_setup(self, core2iaf_path=None, driver_name=None):
        # This is a very long method
        # TODO: Separate into sub-methods
        
        # Need to make these input arguments
        default_core2iaf_path = '/short/v45/core2iaf'
        if core2iaf_path == None:
           core2iaf_path = default_core2iaf_path
        
        default_driver_name = 'coupler'
        if driver_name == None:
            driver_name = default_driver_name
        
        # TODO: Extract this from the forcing files
        max_days = 60 * 365
        
        # Calendar constants
        NO_CALENDAR, THIRTY_DAY_MONTHS, JULIAN, GREGORIAN, NOLEAP = range(5)
        month_days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        
        date_vname = {'coupler': 'current_date', 'ocean_solo': 'date_init'}
        
        #----------
        # t_start
        last_run_dir = 'run%02i' % (self.counter-1,)
        last_res_path = os.path.join(self.archive_path, last_run_dir, 'RESTART')
        tstamp_fname = driver_name + '.res'
        last_tstamp_path = os.path.join(last_res_path, tstamp_fname)
        
        try:
            tstamp_file = open(last_tstamp_path, 'r')
            
            t_calendar = tstamp_file.readline().split()
            assert int(t_calendar[0]) == NOLEAP
            
            # First timestamp is unused
            last_tstamp = tstamp_file.readline().split()
            
            tstamp = tstamp_file.readline().split()
            tstamp_file.close()
        
        except IOError:
            input_nml = open('input.nml','r')
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
        
        input_nml = open('input.nml','r')
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
            
            cmd = 'ncks -d TIME,%.1f,%.1f -o %s %s' \
                    % (t_start, t_end, out_fpath, in_fpath)
            rc = sp.Popen(cmd.split()).wait()
            assert rc == 0
