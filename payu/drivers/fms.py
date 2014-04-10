# coding: utf-8
"""
The payu interface for GFDL models based on FMS
-------------------------------------------------------------------------------
Contact: Marshall Ward <marshall.ward@anu.edu.au>
-------------------------------------------------------------------------------
Distributed as part of Payu, Copyright 2011 Marshall Ward
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
from ..fsops import mkdir_p
from ..modeldriver import Model

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
        self.work_init_path = self.work_input_path


    #--
    def archive(self, **kwargs):

        # Remove the 'INPUT' path
        cmd = 'rm -rf {path}'.format(path=self.work_input_path)
        rc = sp.check_call(shlex.split(cmd))

        # Archive restart files before processing model output
        cmd = 'mv {src} {dst}'.format(src=self.work_restart_path,
                                      dst=self.restart_path)
        sp.check_call(shlex.split(cmd))


    #---
    def collate(self):

        # Set the stacksize to be unlimited
        import resource as res
        res.setrlimit(res.RLIMIT_STACK, (res.RLIM_INFINITY, res.RLIM_INFINITY))

        # Locate the FMS collation tool
        mppnc_path = None
        for f in os.listdir(self.expt.bin_path):
            if f.startswith('mppnccombine'):
                mppnc_path = os.path.join(self.expt.bin_path, f)
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
