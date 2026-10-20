import os
import shutil
from unittest.mock import patch, MagicMock

import pytest

import payu.models.fms as fms_module
from payu.models.fms import get_uncollated_files, get_avail_collate_flags, restart_mapping_log, get_restart_uncollated_hashes
from payu.models.fms import fms_collate
from payu.errors import PayuRuntimeError

from test.common import tmpdir

from pathlib import Path
from types import SimpleNamespace
from ruamel.yaml import YAML


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


@pytest.mark.parametrize(
    "subdir",
    [
        None,  # flat directory - restart000
        "ocean",  # subdirectory - restart000/ocean
    ],
)
@patch("payu.models.fms.hash")
def test_restart_hash_directory_layout(mock_hash, tmp_path, subdir):
    """
    Test restart hash mapping for flat and nested directory layouts.
    """
    archive = tmp_path / "archive"
    restart = archive / "restart000"

    if subdir:
        restart = restart / subdir

    # Set up the restart test tiles
    base = "access-mom6.r.nc"
    tiles = [f"{base}.{i:04d}" for i in range(3)]

    # Include output tiles to verify they are excluded
    mnc_tiles = {
        str(archive / "output000"): {
            "access-mom6.out.nc": [f"access-mom6.out.nc.{i:04d}" for i in range(3)]
        },
        str(restart): {
            base: tiles
        },
    }

    # Return filenames as fake hashes
    mock_hash.side_effect = lambda file_path, hashfn: f"{os.path.basename(file_path)}"

    model = MagicMock()
    model.expt.archive_path = str(archive)

    mapping = get_restart_uncollated_hashes(mnc_tiles, model)

    assert mapping == {
        "restart000": {
            str(restart / base): tiles
        }
    }


@pytest.mark.parametrize("use_glob,extra_file_location",
    [
        (True, None),  # glob matching all tiles for both output and restart directories
        (True, "output"),  # glob matches an extra file in the output directory so fall back
        (True, "restart"),  # glob matches an extra file in the restart directory so fall back
        (False, False),  # glob is disabled so both directories fall back to explicit tile listing
    ]
)
def test_fms_collate_mpi_glob(tmp_path, monkeypatch, capsys, use_glob, extra_file_location):
    """
    Test MPI glob handling and restart hashing in fms_collate.
    """
    archive = tmp_path / "archive"
    output = archive / "output000"
    restart = archive / "restart000"

    output_base = "access-om3.mom6.out.nc"
    restart_base = "access-om3.mom6.r.nc"

    for d, base in ((output, output_base), (restart, restart_base)):
        d.mkdir(parents=True)
        for n in range(3):
            (d / f"{base}.{n:04d}").write_text(f"tile {n}")

    # Add an extra file that matches the glob but is not a valid tile.
    # This should prevent the glob optimisation
    if extra_file_location == "output":
        (output / f"{output_base}.bk").write_text("bk")
    elif extra_file_location == "restart":
        (restart / f"{restart_base}.bk").write_text("bk")

    # mock the model with MPI collation enabled
    model = MagicMock()
    model.expt.config = {
        "collate": {
            "mpi": True,
            "glob": use_glob,
            "restart": True,
            "exe": "mppnccombine-fast",
            "ncpus": 4,
        }
    }

    model.expt.archive_path = str(archive)
    model.output_path = str(output)
    model.prior_restart_path = str(restart)
    model.expand_executable_path.return_value = "mppnccombine-fast"

    # capture collation commands without actually running MPI
    commands = {}
    pool = MagicMock()

    def mock_apply_async(func, args):
        command, directory = args
        commands[directory] = command

        # simulate successful collation
        result = MagicMock()
        result.get.return_value = (None, b"")
        return result

    pool.apply_async.side_effect = mock_apply_async

    # mock multiprocessing and env operations
    monkeypatch.setattr("payu.models.fms.multiprocessing.Pool", lambda **kwargs: pool)
    monkeypatch.setattr("payu.models.fms.res.setrlimit", lambda *args: None)
    monkeypatch.setattr("payu.models.fms.required_libs", lambda *args: [])
    monkeypatch.setattr("payu.models.fms.envmod.lib_update", lambda *args: None)
    monkeypatch.setattr("payu.models.fms.envmod.module", lambda *args: None)

    # ensure hashing uses actual files
    def mock_hash(path, hashfn):
        assert os.path.isfile(path)  # never hash a glob pattern
        return os.path.basename(path)

    monkeypatch.setattr("payu.models.fms.hash", mock_hash)

    # skip hashing collated files since no real collated files in this test
    monkeypatch.setattr("payu.models.fms.restart_mapping_log", lambda hashes: hashes)

    # Exercise the large-tile warning when glob matching fails
    if use_glob and extra_file_location == "output":
        monkeypatch.setattr(
            "payu.models.fms.MPI_FORK_MAX_FILE_LIMIT", 2
        )

    # Verify the expected warnings when glob matching fails
    if use_glob and extra_file_location is not None:
        with pytest.warns(UserWarning) as recorded_warnings:
            mapping = fms_collate(model)

        messages = [str(w.message) for w in recorded_warnings]

        affected_base = (
            output_base
            if extra_file_location == "output"
            else restart_base
        )

        assert (
            f"Cannot use globstr {affected_base}.* to collate {affected_base}. "
            "Falling back to listing tiles individually."
        ) in messages

        if extra_file_location == "output":
            assert "Large number of tiles: 3" in messages
            assert "Collation will be slow and may fail" in messages
    else:
        mapping = fms_collate(model)

    # Expected tile names when glob optimisation is not used
    output_explicit = " ".join(
        f"{output_base}.{i:04d}" for i in range(3)
    )
    restart_explicit = " ".join(
        f"{restart_base}.{i:04d}" for i in range(3)
    )

    # check output glob handling
    expected_output = (
        f"{output_base}.*"
        if use_glob and extra_file_location != "output"
        else output_explicit
    )
    assert commands[str(output)].endswith(expected_output)

    # check restart glob handling
    expected_restart = (
        f"{restart_base}.*"
        if use_glob and extra_file_location != "restart"
        else restart_explicit
    )
    assert commands[str(restart)].endswith(expected_restart)

    # verify restart hashes were calculated from individual tiles
    assert mapping == {
        "restart000": {
            str(restart / restart_base): [
                f"{restart_base}.{i:04d}" for i in range(3)
            ]
        }
    }
def _read_restart_yaml(path):
    return YAML().load(path)


def _write_restart_yaml(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    YAML().dump(data, path)


@pytest.fixture
def mom6_collate_case(tmp_path, monkeypatch):
    """
    Use real restart directories but mock out the external collate process and hashing
    """
    archive_path = tmp_path / "archive"
    output_path = archive_path / "output000"
    restart_path = archive_path / "restart000"
    output_path.mkdir(parents=True)
    restart_path.mkdir(parents=True)

    expt = SimpleNamespace(
        archive_path=str(archive_path),
        config={
            "collate": {
                "exe": "mppnccombine",
                "flags": "-r",
                "restart": True,
                "ncpus": 2,
            }
        }
    )

    model = SimpleNamespace(
        model_type="mom6",
        output_path=str(output_path),
        prior_restart_path=str(restart_path),
        expt=expt,
        expand_executable_path=lambda path: path,
    )
    expt.models = [model]

    pool = MagicMock()
    pool.apply_async.return_value.get.return_value = (None, b"")
    monkeypatch.setattr(fms_module.multiprocessing, "Pool", lambda **kwargs: pool)
    monkeypatch.setattr(fms_module, "hash", lambda filename, hashfn=None: f"hash:{Path(filename).name}")

    return model, pool


def test_collate_updates_only_restart_representation(mom6_collate_case):
    """
    Test that fms_collate updates the restart mapping but does not collate output files
    """
    model, _ = mom6_collate_case
    restart = Path(model.prior_restart_path)

    # Create tiled MOM6 restart files
    (restart / "MOM.res.nc.0000").touch()
    (restart / "MOM.res.nc.0001").touch()

    original = {
        "payu_current_run": 0,
        "name": "test_experiment-uuid-123",
        "experiment_uuid": "uuid-123",
        "model_finish_time": '1959-01-01T00:00:00',
        "mom6_restart": {
            "layout": [72, 48],
            "io_layout": [72, 48],
            "representation": "tiled",
        },
    }
    metadata_path = restart / "restart_metadata.yaml"
    _write_restart_yaml(metadata_path, original)

    mapping = fms_collate(model)

    assert "restart000" in mapping

    updated = _read_restart_yaml(metadata_path)

    assert updated == {
        **original,
        "mom6_restart": {
            **original["mom6_restart"],
            "representation": "collated",
        },
    }


@pytest.mark.parametrize("missing_restart_path", [False, True])
def test_collate_without_restart_tiles_does_not_update_metadata(mom6_collate_case, missing_restart_path):
    """
    Leave restart provenance tiled if no restart files were collated
    """
    model, _ = mom6_collate_case
    restart = Path(model.prior_restart_path)
    metadata_path = restart / "restart_metadata.yaml"

    original = {
        "mom6_restart": {
            "layout": [8, 8],
            "io_layout": [8, 8],
            "representation": "tiled",
        }
    }
    _write_restart_yaml(metadata_path, original)
    (Path(model.output_path) / "ocean.stats.nc.0000").touch()

    if missing_restart_path:
        model.prior_restart_path = None

    fms_collate(model)

    assert _read_restart_yaml(metadata_path) == original


@pytest.mark.parametrize("metadata", [None, {"payu_current_run": 0}, {}])
def test_collate_handles_missing_or_legacy_metadata(mom6_collate_case, metadata):
    """
    Support older or missing metadata files without adding MOM6 fields
    """
    model, _ = mom6_collate_case
    restart = Path(model.prior_restart_path)
    (restart / "access-om3.mom6.r.nc.0000").touch()
    metadata_path = restart / "restart_metadata.yaml"

    if metadata is not None:
        _write_restart_yaml(metadata_path, metadata)

    fms_collate(model)

    if metadata is None:
        assert not metadata_path.exists()
    else:
        assert _read_restart_yaml(metadata_path) == metadata


def test_failed_collation_preserves_tiled_representation(mom6_collate_case):
    """
    Preserve tiled provenance when an external collation command fails.
    """
    model, pool = mom6_collate_case
    restart = Path(model.prior_restart_path)
    (restart / "access-om3.mom6.r.nc.0000").touch()
    metadata_path = restart / "restart_metadata.yaml"

    original = {
        "mom6_restart": {
            "layout": [4, 4],
            "io_layout": [4, 4],
            "representation": "tiled",
        }
    }
    _write_restart_yaml(metadata_path, original)
    pool.apply_async.return_value.get.return_value = (1, b"mock collate failure")

    with pytest.raises(PayuRuntimeError, match="mock collate failure"):
        fms_collate(model)

    assert _read_restart_yaml(metadata_path) == original
