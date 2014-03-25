#!/usr/bin/env python
# coding: utf-8
"""
The payu interface for the CICE model
-------------------------------------------------------------------------------
Contact: Marshall Ward <marshall.ward@anu.edu.au>
-------------------------------------------------------------------------------
Distributed as part of Payu, Copyright 2011-2012 Marshall Ward
Licensed under the Apache License, Version 2.0
http://www.apache.org/licenses/LICENSE-2.0
"""

# XXX: This doesn't work, don't use it at the moment!

# Standard Library
import os
import sys
import shlex
import shutil as sh
import subprocess as sp

# Local
import nml
from fsops import mkdir_p
from modeldriver import Model

class Cice(Model):

    #---
    def __init__(self, expt, name, config):
        super(Cice, self).__init__(expt, name, config)

        self.model_type = 'cice'
        self.default_exec = 'cice'

        self.modules = ['pbs',
                        'openmpi']

        self.config_files = ['ice_in']


    #---
    def set_model_pathnames(self):
        super(Cice, self).set_model_pathnames()

        ice_nml_path = os.path.join(self.control_path, 'ice_in')
        ice_nmls = nml.parse(ice_nml_path)

        # Assume local paths are relative to the work path
        res_path = os.path.normpath(ice_nmls['setup_nml']['restart_dir'])
        if not os.path.isabs(res_path):
            res_path = os.path.join(self.work_path, res_path)
        self.work_restart_path = res_path

        work_out_path = os.path.normpath(ice_nmls['setup_nml']['history_dir'])
        if not os.path.isabs(work_out_path):
            work_out_path = os.path.join(self.work_path, work_out_path)
        self.work_output_path = work_out_path


    #---
    def setup(self, use_symlinks=True, repeat_run=False):
        super(Cice, self).setup()

        # Create experiment directory structure
        mkdir_p(self.work_input_path)
        mkdir_p(self.work_restart_path)
        mkdir_p(self.work_output_path)

        # Either create a new INPUT path or link a previous RESTART as INPUT
        if self.prior_restart_path and not repeat_run:
            restart_files = os.listdir(self.prior_res_path)
            for f in restart_files:
                f_res = os.path.join(self.prior_res_path, f)
                f_input = os.path.join(self.work_input_path, f)
                if use_symlinks:
                    os.symlink(f_res, f_input)
                else:
                    sh.copy(f_res, f_input)

        # TODO: Deep restart paths (path/to/restart) (strip work_path)
        res_path = os.path.basename(self.work_restart_path)

        # Link any input data to INPUT
        for input_path in self.input_paths:
            for f in os.listdir(input_path):

                # TODO: Refactor to merge these for loops?

                # Transfer any local (initialization) restarts
                if f == res_path:
                    input_res_path = os.path.join(input_path, res_path)
                    for f_res in os.listdir(input_res_path):
                        f_res_input = os.path.join(input_res_path, f_res)
                        f_res_work = os.path.join(self.work_restart_path, f_res)
                        if use_symlinks:
                            os.symlink(f_res_input, f_res_work)
                        else:
                            sh.copy(f_res_input, f_res_work)

                f_input = os.path.join(input_path, f)
                f_work = os.path.join(self.work_path, f)
                # Do not use input file if it is in RESTART
                if not os.path.exists(f_work):
                    if use_symlinks:
                        os.symlink(f_input, f_work)
                    else:
                        sh.copy(f_input, f_work)


    #--
    def archive(self, **kwargs):

        # NOTE: CICE uses work directory as input
        for f in os.listdir(self.work_input_path):
            f_path = os.path.join(self.work_input_path, f)
            if os.path.islink(f_path):
                os.remove(f_path)

        # Archive restart files before processing model output
        cmd = 'mv {src} {dst}'.format(src=self.work_restart_path,
                                      dst=self.restart_path)
        rc = sp.Popen(shlex.split(cmd)).wait()
        assert rc == 0


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
