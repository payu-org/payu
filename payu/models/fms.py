"""Driver interface to the FMS model framework.

:copyright: Copyright 2011 Marshall Ward, see AUTHORS for details
:license: Apache License, Version 2.0, see LICENSE for details
"""
from __future__ import print_function

from collections import defaultdict
import multiprocessing.dummy as multiprocessing
import os
import resource as res
import shlex
import subprocess as sp
import sys
from itertools import count

from payu.models.model import Model
from payu import envmod


def cmdthread(cmd, cwd):
    # This is run in a thread, so the GIL of python makes it sensible to
    # capture the output from each process and print it out at the end so
    # it doesn't get scrambled when collates are run in parallel
    output = ''
    returncode = None
    try:
        output = sp.check_output(shlex.split(cmd), cwd=cwd, stderr=sp.STDOUT)
    except sp.CalledProcessError as e:
        output = e.output
        returncode = e.returncode
    return returncode, output


class Fms(Model):

    def __init__(self, expt, name, config):

        # payu initalisation
        super(Fms, self).__init__(expt, name, config)

    def set_model_pathnames(self):

        super(Fms, self).set_model_pathnames()

        # Define local FMS directories
        self.work_restart_path = os.path.join(self.work_path, 'RESTART')
        self.work_input_path = os.path.join(self.work_path, 'INPUT')
        self.work_init_path = self.work_input_path

    @staticmethod
    def get_uncollated_files(dir):
        # Generate collated file list and identify the first tile
        tile_fnames = [f for f in os.listdir(dir)
                       if f[-4:].isdigit() and f[-8:-4] == '.nc.']
        # print("dir: ",tile_fnames)
        tile_fnames.sort()
        return tile_fnames

    def archive(self, **kwargs):

        # Remove the 'INPUT' path
        cmd = 'rm -rf {}'.format(self.work_input_path)
        sp.check_call(shlex.split(cmd))

        # Archive restart files before processing model output
        if os.path.isdir(self.restart_path):
            os.rmdir(self.restart_path)

        cmd = 'mv {} {}'.format(self.work_restart_path, self.restart_path)
        sp.check_call(shlex.split(cmd))

    def collate(self):

        # Set the stacksize to be unlimited
        res.setrlimit(res.RLIMIT_STACK, (res.RLIM_INFINITY, res.RLIM_INFINITY))

        collate_config = self.expt.config.get('collate', {})

        # The mpi flag implies using mppnccombine-fast
        mpi = collate_config.get('mpi', False)

        if mpi:
            default_exe = 'mppnccombine-fast'
        else:
            default_exe = 'mppnccombine'

        # Locate the FMS collation tool
        # Check config for collate executable
        mppnc_path = collate_config.get('exe')
        if mppnc_path is None:
            for f in os.listdir(self.expt.lab.bin_path):
                if f == default_exe:
                    mppnc_path = os.path.join(self.expt.lab.bin_path, f)
                    break
        else:
            if not os.path.isabs(mppnc_path):
                mppnc_path = os.path.join(self.expt.lab.bin_path, mppnc_path)

        assert mppnc_path, 'No mppnccombine program found'

        # Check config for collate command line options
        collate_flags = collate_config.get('flags')
        if collate_flags is None:
            if mpi:
                collate_flags = '-r'
            else:
                collate_flags = '-n4 -z -m -r'

        if mpi:
            # The output file is the first argument after the flags
            # and mppnccombine-fast uses an explicit -o flag to specify
            # the output
            collate_flags = " ".join([collate_flags, '-o'])
            envmod.lib_update(mppnc_path, 'libmpi.so')

        # Import list of collated files to ignore
        collate_ignore = collate_config.get('ignore')
        if collate_ignore is None:
            collate_ignore = []
        elif type(collate_ignore) != list:
            collate_ignore = [collate_ignore]

        # Generate collated file list and identify the first tile
        tile_fnames = {}
        tile_fnames[self.output_path] = Fms.get_uncollated_files(self.output_path)

        print(tile_fnames)

        if collate_config.get('restart',False):
            # Add uncollated restart files 
            tile_fnames[self.restart_path] = Fms.get_uncollated_files(self.restart_path)

        # mnc_tiles = defaultdict(list)
        mnc_tiles = defaultdict(defaultdict(list).copy)
        for t_dir in tile_fnames:
            for t_fname in tile_fnames[t_dir]:
                t_base, t_ext = os.path.splitext(t_fname)
                t_ext = t_ext.lstrip('.')

                # Skip any files listed in the ignore list
                if t_base in collate_ignore:
                    continue

                mnc_tiles[t_dir][t_base].append(t_fname)

        # print(mnc_tiles)

        cpucount = int(collate_config.get('ncpus',
                       multiprocessing.cpu_count()))

        if mpi:
            # Default to one for mpi
            nprocesses = int(collate_config.get('threads', 1))
        else:
            nprocesses = int(collate_config.get('threads', cpucount))

        ncpusperprocess = int(cpucount/nprocesses)

        if ncpusperprocess == 1 and mpi:
            print("Warning: running collate with mpirun on a single processor")

        pool = multiprocessing.Pool(processes=nprocesses)

        # Collate each tileset into a single file
        results = []
        codes = []
        outputs = []
        for output_path in mnc_tiles:
            for nc_fname in mnc_tiles[output_path]:
                nc_path = os.path.join(output_path, nc_fname)

                # Remove the collated file if it already exists, since it is
                # probably from a failed collation attempt
                # TODO: Validate this somehow
                if os.path.isfile(nc_path):
                    os.remove(nc_path)

                cmd = ' '.join([mppnc_path, collate_flags, nc_fname,
                                ' '.join(mnc_tiles[output_path][nc_fname])])
                if mpi:
                    cmd = "mpirun -n {} {}".format(ncpusperprocess, cmd)

                print(cmd)
                results.append(
                    pool.apply_async(cmdthread, args=(cmd, output_path)))

        pool.close()
        pool.join()

        for result in results:
            rc, op = result.get()
            codes.append(rc)
            outputs.append(op)

        # TODO: Categorise the return codes
        if any(rc is not None for rc in codes):
            for p, rc, op in zip(count(), codes, outputs):
                if rc is not None:
                    print(
                        'payu: error: Thread {} crased with error code {}.'
                        '\n  Error message:\n{}'
                        ''.format(p, rc, op), file=sys.stderr)
            sys.exit(-1)
