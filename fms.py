#!/usr/bin/env python
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

from payu import Experiment, mkdir_p
import os
import sys
import shlex
import shutil as sh
import subprocess as sp

class fms(Experiment):

    #---
    def __init__(self, **kwargs):

        # payu initalisation
        super(fms, self).__init__(**kwargs)


    #---
    def path_names(self, **kwargs):
        super(fms, self).path_names(**kwargs)

        # Define local FMS directories
        self.work_res_path = os.path.join(self.work_path, 'RESTART')
        self.input_path = os.path.join(self.work_path, 'INPUT')


    #---
    def build(self):
        raise NotImplementedError


    #---
    def setup(self, use_symlinks=True, repeat_run=False):

        # payu setup:
        #   work path and symlink, config file copy
        super(fms, self).setup()

        # Create experiment directory structure
        mkdir_p(self.work_res_path)

        # Either create a new INPUT path or link a previous RESTART as INPUT
        mkdir_p(self.input_path)

        if self.counter > 1 and not repeat_run:
            restart_files = os.listdir(self.prior_res_path)
            for f in restart_files:
                f_res = os.path.join(self.prior_res_path, f)
                f_input = os.path.join(self.input_path, f)
                if use_symlinks:
                    os.symlink(f_res, f_input)
                else:
                    sh.copy(f_res, f_input)

        # Link any forcing data to INPUT
        if self.forcing_path:
            forcing_files = os.listdir(self.forcing_path)
            for f in forcing_files:
                f_forcing = os.path.join(self.forcing_path, f)
                f_input = os.path.join(self.input_path, f)
                # Do not use forcing file if it is in RESTART
                if not os.path.exists(f_input):
                    if use_symlinks:
                        os.symlink(f_forcing, f_input)
                    else:
                        sh.copy(f_forcing, f_input)


    #---
    def run(self, *flags):
        flags = flags + ('-wd %s' % self.work_path, )
        super(fms, self).run(*flags)


    #--
    def archive(self, **kwargs):

        # Remove the 'INPUT' path
        cmd = 'rm -rf {path}'.format(path=self.input_path)
        rc = sp.Popen(shlex.split(cmd)).wait()
        assert rc == 0

        # Archive restart files before processing model output
        mkdir_p(self.archive_path)
        cmd = 'mv {src} {dst}'.format(src=self.work_res_path,
                                      dst=self.res_path)
        rc = sp.Popen(shlex.split(cmd)).wait()
        assert rc == 0

        super(fms, self).archive(**kwargs)


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
        tile_fnames = [f for f in os.listdir(self.run_path)
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
            tile_path = os.path.join(self.run_path, f)

            # Remove the collated file if it already exists, since it is
            # probably from a failed collation attempt
            # TODO: Validate this somehow
            if os.path.isfile(tile_path):
                os.remove(tile_path)

            cmd = '{mppnc} -n {tid} -r -64 {fpath}'.format(
                        mppnc = mppnc_path,
                        tid = mnc_tiles[f],
                        fpath = tile_path)
            rc = sp.Popen(shlex.split(cmd)).wait()
            assert rc == 0
