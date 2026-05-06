import json
import pytest
import os
from unittest.mock import patch

# import payu packages
from payu.fsops import atomic_write_file

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

