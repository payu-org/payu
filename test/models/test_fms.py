import copy
import os
from pathlib import Path
import pdb
import shutil

import f90nml
import pytest
import yaml

import payu

from payu.models.fms import get_uncollated_files

from test.common import tmpdir

verbose = False


def rmtmp():
    try:
        shutil.rmtree(tmpdir)
    except FileNotFoundError:
        pass


def mktmp():
    tmpdir.mkdir()


def setup_module(module):
    """
    Put any test-wide setup code in here, e.g. creating test files
    """
    if verbose:
        print("setup_module      module:%s" % module.__name__)

    rmtmp()
    mktmp()


def teardown_module(module):
    """
    Put any test-wide teardown code in here, e.g. removing test outputs
    """
    if verbose:
        print("teardown_module   module:%s" % module.__name__)

    rmtmp()


def make_tiles(begin, end, prefix='tile'):

    files = []
    for n in range(begin, end):
        p = tmpdir / "{}.nc.{:06d}".format(prefix, n)
        p.touch()
        files.append(str(p.name))

    # Make a random non-conforming filename
    (tmpdir / "log.out").touch()

    # Make a random already collated file
    (tmpdir / "collated.nc").touch()

    return files


def rm_tiles():

    for f in tmpdir.iterdir():
        f.unlink()


def test_get_uncollated_files():

    files = make_tiles(9900, 9999)

    mncfiles = get_uncollated_files(tmpdir)

    assert len(mncfiles) == len(files)
    assert all(a == b for a, b in zip(mncfiles, files))

    files = make_tiles(9900, 10100)

    mncfiles = get_uncollated_files(tmpdir)

    assert len(mncfiles) == len(files)
    assert all(a == b for a, b in zip(mncfiles, files))

    rm_tiles()

    files = make_tiles(0, 99)

    mncfiles = get_uncollated_files(tmpdir)

    assert len(mncfiles) == len(files)
    assert all(a == b for a, b in zip(mncfiles, files))

    rm_tiles()

    # Make sure still sorts once over the six-figure zero-padding
    files = make_tiles(999997, 1000010)

    mncfiles = get_uncollated_files(tmpdir)

    assert len(mncfiles) == len(files)
    assert all(a == b for a, b in zip(mncfiles, files))


def test_get_uncollated_restart_files():

    rm_tiles()

    prefix = "tile.res"

    files = make_tiles(9900, 9999, prefix)

    mncfiles = get_uncollated_files(tmpdir)

    assert len(mncfiles) == len(files)
    assert all(a == b for a, b in zip(mncfiles, files))

    files = make_tiles(9900, 10100, prefix)

    mncfiles = get_uncollated_files(tmpdir)

    assert len(mncfiles) == len(files)
    assert all(a == b for a, b in zip(mncfiles, files))

    rm_tiles()

    files = make_tiles(0, 99, prefix)

    mncfiles = get_uncollated_files(tmpdir)

    assert len(mncfiles) == len(files)
    assert all(a == b for a, b in zip(mncfiles, files))

    rm_tiles()

    # Make sure still sorts once over the six-figure zero-padding
    files = make_tiles(999997, 1000010, prefix)

    mncfiles = get_uncollated_files(tmpdir)

    assert len(mncfiles) == len(files)
    assert all(a == b for a, b in zip(mncfiles, files))
