"""Driver interface to the FMS model framework.

:copyright: Copyright 2011 Marshall Ward, see AUTHORS for details
:license: Apache License, Version 2.0, see LICENSE for details
"""
from __future__ import print_function

from collections import defaultdict
from pathlib import Path
import multiprocessing
import os
import resource as res
import shlex
import shutil
import subprocess as sp
import sys
from itertools import count
import fnmatch

from payu.models.model import Model
from payu import envmod
from payu.fsops import required_libs

# There is a limit on the number of command line arguments in a forked
# MPI process. This applies only to mppnccombine-fast. The limit is higher
# than this, but mppnccombine-fast is very slow with large numbers of files
MPI_FORK_MAX_FILE_LIMIT = 1000


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


def get_uncollated_files(dir):

    if not os.path.isdir(dir):
        return []

    # Generate collated file list and identify the first tile
    tile_fnames = [f for f in Path(dir).glob('*.nc.*')
                   if f.suffixes[-2] == '.nc' and
                   f.suffixes[-1][1:].isdigit()]

    # Sort numerically according to the number in the suffix and strip off
    # path information
    return [f.name for f
            in sorted(tile_fnames, key=lambda e: int(e.suffixes[-1][1:]))]

def fms_collate(model):
    """
    Collate model output using mppnccombine. This is broken out of the Fms class so that it can
    be used by other models

    Parameters
    ----------
    model: :py:class:`~payu.models.model`
        The payu model class or child thereof
    """
    
    # Set the stacksize to be unlimited
    res.setrlimit(res.RLIMIT_STACK, (res.RLIM_INFINITY, res.RLIM_INFINITY))

    collate_config = model.expt.config.get('collate', {})

    # The mpi flag implies using mppnccombine-fast
    mpi = collate_config.get('mpi', False)

    if mpi:
        # Load mpi modules for collation
        model.expt.load_modules()
        default_exe = 'mppnccombine-fast'
    else:
        default_exe = 'mppnccombine'

    # Locate the FMS collation tool
    # Check config for collate executable
    mppnc_path = collate_config.get('exe')
    if mppnc_path is None:
        for f in os.listdir(model.expt.lab.bin_path):
            if f == default_exe:
                mppnc_path = os.path.join(model.expt.lab.bin_path, f)
                break
    else:
        mppnc_path = model.expand_executable_path(mppnc_path)

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
        envmod.lib_update(required_libs(mppnc_path), 'libmpi.so')

    # Import list of collated files to ignore
    collate_ignore = collate_config.get('ignore')
    if collate_ignore is None:
        collate_ignore = []
    elif type(collate_ignore) != list:
        collate_ignore = [collate_ignore]

    # Generate collated file list and identify the first tile
    tile_fnames = {}
    fnames = get_uncollated_files(model.output_path)
    tile_fnames[model.output_path] = fnames

    print(tile_fnames)

    if (collate_config.get('restart', False) and
            model.prior_restart_path is not None):
        # Add uncollated restart files
        fnames = get_uncollated_files(model.prior_restart_path)
        tile_fnames[model.prior_restart_path] = fnames

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

    if mpi and collate_config.get('glob', True):
        for t_base in mnc_tiles:
            globstr = "{}.*".format(t_base)
            # Try an equivalent glob and check the same files are returned
            mnc_glob = fnmatch.filter(os.listdir(model.output_path),
                                      globstr)
            if mnc_tiles[t_base] == sorted(mnc_glob):
                mnc_tiles[t_base] = [globstr, ]
                print("Note: using globstr ({}) for collating {}"
                      .format(globstr, t_base))
            else:
                print("Warning: cannot use globstr {} to collate {}"
                      .format(globstr, t_base))
                if len(mnc_tiles[t_base]) > MPI_FORK_MAX_FILE_LIMIT:
                    print("Warning: large number of tiles: {} "
                          .format(len(mnc_tiles[t_base])))
                    print("Warning: collation will be slow and may fail")

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
                print('payu: error: Thread {p} crashed with error code '
                      '{rc}.'.format(p=p, rc=rc), file=sys.stderr)
                print(' Error message:', file=sys.stderr)
                print(op.decode(), file=sys.stderr)
        sys.exit(-1)


class Fms(Model):

    def __init__(self, expt, name, config):
        
        # payu initialisation
        super().__init__(expt, name, config)

    def set_model_pathnames(self):

        super().set_model_pathnames()

        # Define local FMS directories
        self.work_restart_path = os.path.join(self.work_path, 'RESTART')
        self.work_input_path = os.path.join(self.work_path, 'INPUT')
        self.work_init_path = self.work_input_path

    def archive(self, **kwargs):
        super().archive()

        # Remove the 'INPUT' path
        shutil.rmtree(self.work_input_path, ignore_errors=True)

        # Archive restart files before processing model output
        if os.path.isdir(self.restart_path):
            os.rmdir(self.restart_path)

        shutil.move(self.work_restart_path, self.restart_path)

    def collate(self):
        fms_collate(self)
