import os
import shutil
from unittest.mock import patch, MagicMock

import pytest

from payu.models.fms import get_uncollated_files, get_avail_collate_flags, restart_mapping_log, get_restart_uncollated_hashes

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

@pytest.fixture(autouse=True)
def setup_module(setup_test_dir, empty_workdir):
    """
    Put any test-wide setup code in here, e.g. creating test files
    """
    pass



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


@pytest.mark.parametrize("begin, end, prefix", [
    (9900, 9999, 'tile'),
    (9900, 10100, 'tile'),
    (0, 99, 'tile'),
    (999997, 1000010, 'tile')
])
def test_get_uncollated_files(begin, end, prefix):

    files = make_tiles(begin, end, prefix)

    mncfiles = get_uncollated_files(tmpdir)

    assert len(mncfiles) == len(files)
    assert all(a == b for a, b in zip(mncfiles, files))

@pytest.mark.parametrize("begin, end, prefix", [
    (9900, 9999, 'tile.res'),
    (9900, 10100, 'tile.res'),
    (0, 99, 'tile.res'),
    (999997, 1000010, 'tile.res')
])
def test_get_uncollated_restart_files(begin, end, prefix):

    files = make_tiles(begin, end, prefix)

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


@patch("payu.models.fms.hash")
def test_restart_mapping_log(mock_hash):
    """Test that a mapping collate dictionary is generated correctly"""
    # Set up mock md5 hash values for the test files
    mock_hash.side_effect = lambda file_path, hashfn: f"md5_{os.path.basename(file_path)}"

    # Create a dictionary of uncollated tiles
    archive_dir = tmpdir / "archive"
    output_dir =  archive_dir / "output003" / "ocean"
    restart_dir = archive_dir / "restart002" / "ocean"
    mnc_tiles = {
        str(output_dir): {
            "ocean_1d.res.nc": ["ocean_1d.res.nc.0000", "ocean_1d.res.nc.0001"]
        },
        str(restart_dir): {
            "ocean_2d.res.nc": ["ocean_2d.res.nc.0000", "ocean_2d.res.nc.0001"],
            "ocean_3d.res.nc": ["ocean_3d.res.nc.0000", "ocean_3d.res.nc.0001"],
        }
    }
    # set up mock model
    mock_model = MagicMock()
    mock_model.expt.archive_path = str(archive_dir)

    # Call the restart_mapping_log function
    uncollate_hashes_dict = get_restart_uncollated_hashes(mnc_tiles, mock_model)
    mock_model = MagicMock()
    mock_model.prior_restart_path = str(restart_dir)
    mock_model.expt.archive_path = str(archive_dir)
    mapping_collate_dict = restart_mapping_log(uncollate_hashes_dict)

    # Set up the expected mapping dictionary
    expected_mapping = {
        "restart002":{
            "md5_ocean_2d.res.nc": ["md5_ocean_2d.res.nc.0000", "md5_ocean_2d.res.nc.0001"],
            "md5_ocean_3d.res.nc": ["md5_ocean_3d.res.nc.0000", "md5_ocean_3d.res.nc.0001"],
        }
    }
    
    # Confirm only restart collation are recorded in the mapping (but not output collation)
    assert mapping_collate_dict == expected_mapping