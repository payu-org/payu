# coding: utf-8
"""
The payu interface for GFDL models based on FMS
-------------------------------------------------------------------------------
Contact: Marshall Ward <marshall.ward@anu.edu.au>
-------------------------------------------------------------------------------
Distributed as part of Payu, Copyright 2011-2012 Marshall Ward
Licensed under the Apache License, Version 2.0
http://www.apache.org/licenses/LICENSE-2.0
"""

# Standard Library
import os
import sys
import shlex
import shutil as sh
import subprocess as sp

# Local
from fsops import mkdir_p
from modeldriver import Model

#class Fms(Experiment):
class Fms(Model):

    #---
    def __init__(self, expt, name, config):

        # payu initalisation
        super(Fms, self).__init__(expt, name, config)


    #---
    def set_model_pathnames(self):

        super(Fms, self).set_model_pathnames()

        # Define local FMS directories
        self.work_restart_path = os.path.join(self.work_path, 'RESTART')
        self.work_input_path = os.path.join(self.work_path, 'INPUT')


    #---
    def setup(self, use_symlinks=True, repeat_run=False):

        super(Fms, self).setup()

        # Create experiment directory structure
        mkdir_p(self.work_input_path)
        mkdir_p(self.work_restart_path)

        # Either create a new INPUT path or link a previous RESTART as INPUT
        if self.prior_restart_path and not self.expt.repeat_run:
            restart_files = os.listdir(self.prior_restart_path)
            for f in restart_files:
                f_restart = os.path.join(self.prior_restart_path, f)
                f_input = os.path.join(self.work_input_path, f)
                if use_symlinks:
                    os.symlink(f_restart, f_input)
                else:
                    sh.copy(f_restart, f_input)

        # Link any input data to INPUT
        for input_path in self.input_paths:
            input_files = os.listdir(input_path)
            for f in input_files:
                f_input = os.path.join(input_path, f)
                f_work_input = os.path.join(self.work_input_path, f)
                # Do not use input file if it is in RESTART
                # TODO: Is this really what I want? Or should I warn the user?
                if not os.path.exists(f_work_input):
                    if use_symlinks:
                        os.symlink(f_input, f_work_input)
                    else:
                        sh.copy(f_input, f_work_input)


    #--
    def archive(self, **kwargs):

        super(Fms, self).archive(**kwargs)

        # Remove the 'INPUT' path
        cmd = 'rm -rf {path}'.format(path=self.work_input_path)
        rc = sp.check_call(shlex.split(cmd))

        # Archive restart files before processing model output
        cmd = 'mv {src} {dst}'.format(src=self.work_restart_path,
                                      dst=self.restart_path)
        sp.check_call(shlex.split(cmd))

        #super(Fms, self).archive(**kwargs)


    #---
    def collate(self):

        # Set the stacksize to be unlimited
        import resource as res
        res.setrlimit(res.RLIMIT_STACK, (res.RLIM_INFINITY, res.RLIM_INFINITY))

        # Locate the FMS collation tool
        mppnc_path = None
        for f in os.listdir(self.bin_path):
            if f.startswith('mppnccombine'):
                mppnc_path = os.path.join(self.bin_path, f)
                break
        assert mppnc_path

        # Generate collated file list and identify the first tile
        tile_fnames = [f for f in os.listdir(self.output_path)
                         if f[-4:].isdigit() and f[-8:-4] == '.nc.']

        mnc_tiles = {}
        for t in tile_fnames:
            t_name, t_ext = os.path.splitext(t)
            t_ext = t_ext.lstrip('.')

            try:
                if int(t_ext) < int(mnc_tiles[t_name]):
                    mnc_tiles[t_name] = t_ext
            except KeyError:
                mnc_tiles[t_name] = t_ext

        # Collate each tileset into a single file
        for f in mnc_tiles:
            tile_path = os.path.join(self.output_path, f)

            # Remove the collated file if it already exists, since it is
            # probably from a failed collation attempt
            # TODO: Validate this somehow
            if os.path.isfile(tile_path):
                os.remove(tile_path)

            cmd = '{mppnc} -n {tid} -r -64 {fpath}'.format(
                        mppnc = mppnc_path,
                        tid = mnc_tiles[f],
                        fpath = tile_path)
            cmd = shlex.split(cmd)
            rc = sp.Popen(cmd).wait()
            assert rc == 0
