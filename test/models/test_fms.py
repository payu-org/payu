import copy
import os
from pathlib import Path
import pdb
import shutil
from unittest.mock import patch, MagicMock

import f90nml
import pytest
import yaml

import payu

from payu.models.fms import get_uncollated_files, get_avail_collate_flags

from test.common import tmpdir

verbose = False

MPPNC_STRING_UPSTREAM = """
mppnccombine 2024.05 - (written by Hans.Vahlenkamp@noaa.gov)

Usage:  mppnccombine [-v] [-V] [-M] [-a] [-r] [-n #] [-k #] [-e #] [-h #] [-64] [-n4 [-d #] [-s]] [-m]
                     output.nc [input ...]

  -v    Print some progress information.
  -V    Print version information.
  -M    Print memory usage statistics.
  -f    Force combine to happen even if input files are missing.
  -a    Append to an existing netCDF file (not heavily tested...).
  -r    Remove the ".####" decomposed files after a successful run.
  -n #  Input filename extensions start with number #### instead of 0000.
  -k #  Blocking factor. k records are read from an input file at a time.
        Valid values are between 0 and 100. For a given input, the maximum
        permissible value for k is min(total number of records, 100).
        Setting k to zero will set the blocking factor to this maximum
        permissible value. Setting k to a value higher than this value,
        will make the system implicitly set k to the highest permissible value.
        A value of 1 for k disables blocking. This is the default behavior.
        Blocking often improves performance, but increases the peak memory
        footprint (by the blocking factor). Beware of running out of
        available physical memory and causing swapping to disk due to
        large blocking factors and/or large input datasets.
        A value of 10 for k has worked well on many input datasets.
        See -x for estimating memory usage for a given input set.
  -e #  Ending number #### of a specified range of input filename extensions.
        Files within the range do not have to be consecutively numbered.
  -h #  Add a specified number of bytes of padding at the end of the header.
  -64   Create netCDF output files with the 64-bit offset format.
  -n4   Create netCDF output files in NETCDF4_CLASSIC mode (no v4 enhanced features).
  -d #  When in NETCDF4 mode, use deflation of level #.
  -s    When in NETCDF4 mode, use shuffle.
  -m    Initialize output variables with a "missing_value" from the variables
        of the first input file instead of the default 0 value.
  -x    Print an estimate for peak memory resident size in (MB) and exit.
        No output file will be created. Setting -x automatically sets
        the blocking factor (-k) to 1. Any value set for -k on the
        command-line will be ignored. To estimate memory usage for a
        a different blocking factor, simply multiply the estimate by k.

mppnccombine joins together an arbitrary number of netCDF input files, each
containing parts of a decomposed domain, into a unified netCDF output file.
An output file must be specified and it is assumed to be the first filename
argument.  If the output file already exists, then it will not be modified
unless the option is chosen to append to it.  If no input files are specified
then their names will be based on the name of the output file plus the default
numeric extension ".0000", which will increment by 1.  There is an option for
starting the filename extensions with an arbitrary number instead of 0.  There
is an option for specifying an end to the range of filename extension numbers;
files within the range do not have to be consecutively numbered.  If input
files are specified then names will be used verbatim.

A value of 0 is returned if execution completed successfully; a value of 1
otherwise.
"""
MPPNC_FLAGS_UPSTREAM = [
    "-v", '-V', "-M", "-f", "-a", "-r", "-n", "-k", "-e", "-h", "-64", "-n4", "-d", "-s", "-m", "-x"
]
MPPNC_STRING_MOM5 = """
mppnccombine 2.2.5 - (written by Hans.Vahlenkamp)

Usage:  mppnccombine [-v] [-V] [-M] [-a] [-r] [-n #] [-k #] [-e #] [-h #] [-64] [-n4] [-m]
                     output.nc [input ...]

  -v    Print some progress information.
  -V    Print version information.
  -M    Print memory usage statistics.
  -f    Force combine to happen even if input files are missing.
  -a    Append to an existing netCDF file (not heavily tested...).
  -r    Remove the ".####" decomposed files after a successful run.
  -n #  Input filename extensions start with number #### instead of 0000.
  -k #  Blocking factor. k records are read from an input file at a time.
        Valid values are between 0 and 100. For a given input, the maximum
        permissible value for k is min(total number of records, 100).
        Setting k to zero will set the blocking factor to this maximum
        permissible value. Setting k to a value higher than this value,
        will make the system implictly set k to the highest permissible value.
        A value of 1 for k disables blocking. This is the default behavior.
        Blocking often improves performance, but increases the peak memory
        footprint (by the blocking factor). Beware of running out of
        available physical memory and causing swapping to disk due to
        large blocking factors and/or large input datasets.
        A value of 10 for k has worked well on many input datasets.
        See -x for estimating memory usage for a given input set.
  -e #  Ending number #### of a specified range of input filename extensions.
        Files within the range do not have to be consecutively numbered.
  -h #  Add a specified number of bytes of padding at the end of the header.
  -64   Create netCDF output files with the 64-bit offset format.
  -n4   Create netCDF output files in NETCDF4_CLASSIC mode (no v4 enhanced features).
  -m    Initialize output variables with a "missing_value" from the variables
        of the first input file instead of the default 0 value.
  -x    Print an estimate for peak memory resident size in (MB) and exit.
        No output file will be created. Setting -x automatically sets
        the blocking factor (-k) to 1. Any value set for -k on the
        command-line will be ignored. To estimate memory usage for a
        a different blocking factor, simply multiply the estimate by k.
  -z    Enable netCDF4 compression
  -d #  Set deflate (compression) level. Valid values: 0-9, default=5
  -s    Toggle OFF shuffle option in compression

mppnccombine joins together an arbitrary number of netCDF input files, each
containing parts of a decomposed domain, into a unified netCDF output file.
An output file must be specified and it is assumed to be the first filename
argument.  If the output file already exists, then it will not be modified
unless the option is chosen to append to it.  If no input files are specified
then their names will be based on the name of the output file plus the default
numeric extension ".0000", which will increment by 1.  There is an option for
starting the filename extensions with an arbitrary number instead of 0.  There
is an option for specifying an end to the range of filename extension numbers;
files within the range do not have to be consecutively numbered.  If input
files are specified then names will be used verbatim.

A value of 0 is returned if execution completed successfully; a value of 1
otherwise.
"""
MPPNC_FLAGS_MOM5 = MPPNC_FLAGS_UPSTREAM + ["-z"]

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
    

@pytest.mark.parametrize("help_text, expected_flags", [
    (MPPNC_STRING_UPSTREAM, MPPNC_FLAGS_UPSTREAM),
    (MPPNC_STRING_MOM5, MPPNC_FLAGS_MOM5),
])
@patch("subprocess.run")
def test_get_avail_collate_flags(mock_run, help_text, expected_flags):
    """Test parsing mppnccombine flags from the help string"""
    help_text = help_text
    mock_run.return_value = MagicMock(stdout=help_text)
    
    result = get_avail_collate_flags("mppnccombine")
    assert sorted(result) == sorted(expected_flags)

@patch("subprocess.run")
def test_get_avail_collate_flags_runtimeerror(mock_run):
    """Test that RuntimeError is raised when subprocess.run fails"""
    mock_run.side_effect = OSError("Mocked OSError")

    with pytest.raises(RuntimeError) as excinfo:
        get_avail_collate_flags("mppnccombine")

    assert "Failed to run" in str(excinfo.value)
    # Ensure error chaining happened
    assert isinstance(excinfo.value.__cause__, OSError)