import json
import pytest
import os
from unittest.mock import patch
import hashlib

# import payu packages
from payu.fsops import atomic_write_file, calculate_md5_hash

# import some common variables for testing
from .common import tmpdir

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


def test_calculate_md5_hash():
    """Test that calculate_md5_hash returns the correct hash for a given file"""
    # Create a temporary file with known content
    test_file = tmpdir / "test_file.txt"
    test_content = b"Hello payu!"
    with open(test_file, "wb") as f:
        f.write(test_content)

    # Calculate the expected MD5 hash
    expected_hash = hashlib.md5(test_content).hexdigest()

    # Call the function to calculate the MD5 hash
    result_hash = calculate_md5_hash(test_file)

    assert result_hash == expected_hash
    os.remove(test_file)


def test_calculate_md5_hash_file_not_found():
    """Test that calculate_md5_hash raises FileNotFoundError when file does not exist"""
    non_exist_file = tmpdir / "non_existent_file.txt"

    with pytest.raises(FileNotFoundError) as excinfo:
        calculate_md5_hash(non_exist_file)

    assert "File not found" in str(excinfo.value)

