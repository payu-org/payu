import json
import pytest
import os
import shutil
from unittest.mock import patch
from pathlib import Path

# import payu packages
from payu.fsops import atomic_write_file, movetree, list_sorted_archive_dirs

# import some common variables for testing
from .common import tmpdir, testdir, labdir, archive_dir, make_all_files

def scantree(path):
    """
    Recursively yield DirEntry objects for given directory.
    https://stackoverflow.com/a/33135143/4727812
    """
    for entry in os.scandir(path):
        if entry.is_dir(follow_symlinks=False):
            yield from scantree(entry.path)
        else:
            yield entry

def savetree(path):
    """
    Save a directory tree to a dict
    """
    result = {}
    for entry in scantree(path):
        result[entry.name] = (Path(entry.path).relative_to(path),
                              entry.stat().st_size)
    return(result)

def test_movetree():
    tmptwo = testdir / 'tmp2'
    try:
        shutil.rmtree(tmptwo)
    except FileNotFoundError:
        pass

    make_all_files()

    treeinfo = savetree(tmpdir)

    tmp_inode = tmpdir.stat().st_ino

    movetree(tmpdir, tmptwo)

    # Ensure src directory removed
    assert(not tmpdir.exists())

    # Ensure dst directory has new inode number
    assert(tmp_inode != tmptwo.stat().st_ino)

    # Ensure directory tree faithfully moved
    assert(treeinfo == savetree(tmptwo))

    # Move tmp2 back to tmp
    shutil.move(tmptwo, tmpdir)

def test_atomic_write_file_new_content():
    """Test that atomic_write_file write expected content into designated file
    and delete the temp file."""
    write_dir = tmpdir / "test_write_dir"
    orig_file = write_dir / "origin.json"
    content = {"key1": "value1", "key2": 123}
    # write original file
    write_dir.mkdir(parents=True, exist_ok=True)
    with orig_file.open("w") as f:
        json.dump(content, f)

    new_content = {"key1": "new_value", "key2": 456}
    atomic_write_file(orig_file, new_content)

    # assert correct content
    assert json.loads(orig_file.read_text()) == new_content

    # assert no other files exist in this directory (e.g. temp files)
    files_in_dir = list(write_dir.iterdir())
    assert len(files_in_dir) == 1
    assert files_in_dir[0] == orig_file

def sim_disrupt(*args, **kwargs):
        raise RuntimeError("Simulated disruption")

def test_atomic_write_file_disrupt_replace(monkeypatch):
    """Test that when atomic_write_file is disrupted during replace operation,
    the original file will not be corrupted/changed."""
    write_dir = tmpdir / "test_disrupt_replace_dir"
    orig_file = write_dir / "origin.json"
    content = {"key1": "value1", "key2": 123}

    # write original file
    write_dir.mkdir(parents=True, exist_ok=True)
    with orig_file.open("w") as f:
        json.dump(content, f)

    # simulate disruption by raising an exception during replacing
    new_content = {"key1": "new_value", "key2": 456}
    monkeypatch.setattr("payu.fsops.os.replace", sim_disrupt)
    with pytest.raises(RuntimeError):
        atomic_write_file(orig_file, new_content)

    # assert the original file is unchanged and not corrupted
    with open(orig_file, 'r') as f:
        content_after_error = json.load(f)
    assert content_after_error == content


def test_atomic_write_file_disrupt_dump(monkeypatch):
    """Test that when atomic_write_file is disrupted during writing tmp file,
    the original file will not be corrupted/changed."""
    write_dir = tmpdir / "test_disrupt_dump_dir"
    orig_file = write_dir / "origin.json"
    content = {"key1": "value1", "key2": 123}

    # write original file
    write_dir.mkdir(parents=True, exist_ok=True)
    with orig_file.open("w") as f:
        json.dump(content, f)

    # simulate disruption in writing tmp file
    new_content = {"key1": "new_value", "key2": 456}
    monkeypatch.setattr("payu.fsops.json.dump", sim_disrupt)
    with pytest.raises(RuntimeError):
        atomic_write_file(orig_file, new_content)

    # assert the original file is unchanged and not corrupted
    with open(orig_file, 'r') as f:
        content_after_error = json.load(f)
    assert content_after_error == content


def test_list_sorted_archive_dirs(setup_test_dir):
    """Test that list_sorted_archive_dirs correctly lists and sorts directory names."""
    # Create archive directories - mix of valid/invalid names
    archive_dirs = [
        'output000', 'output1001', 'output023', 'output404',
        'output', 'Output001', 'output44', # not valid output dir
        'Restart', 'restart2', 'restart', 'restart55', # not valid restart dir
        'restart102932', 'restart021', 'restart009', 'restart606'
    ]

    os.makedirs(archive_dir, exist_ok=True)
    for dir in archive_dirs:
        (archive_dir / dir).mkdir(parents=True)

    # Add some files
    (archive_dir / 'restart005').touch()
    (archive_dir / 'output005').touch()

    # Add a restart symlink
    archive_dir2 = labdir / 'archive2'
    source_path = archive_dir2 / 'restart999'
    source_path.mkdir(parents=True)
    (archive_dir / 'restart23042').symlink_to(source_path)

    # Test list output dirs and with string archive path
    outputs = list_sorted_archive_dirs(str(archive_dir), dir_type="output")
    assert outputs == ['output000', 'output023', 'output404', 'output1001']

    # Test list restarts
    restarts = list_sorted_archive_dirs(archive_dir, dir_type="restart")
    assert restarts == ['restart009', 'restart021', 'restart606',
                        'restart23042', 'restart102932']
