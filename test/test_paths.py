import os
from pathlib import Path
import shutil

import pytest

from payu.laboratory import Laboratory

from .common import cd
from .common import tmpdir, ctrldir
from .common import write_config


@pytest.fixture(autouse=True)
def setup_and_teardown():
    # Create tmp and control directories
    try:
        tmpdir.mkdir()
        ctrldir.mkdir()
    except Exception as e:
        print(e)

    yield

    # Remove tmp directory
    try:
        shutil.rmtree(tmpdir)
    except Exception as e:
        print(e)


@pytest.mark.parametrize(
    "config, expected_shortpath, expected_user, expected_labname",
    [
        (
            # Test shortpath and model name for laboratory
            {
                'shortpath': '..',
                'model': 'test',
            }, '..', '*', 'test'
        ),
        (
            # Test relative laboratory path
            {
                'shortpath': '/scratch/xx00',
                'model': 'test',
                'laboratory': 'lab'
            }, '/scratch/xx00', '*', 'lab'
        ),
        (
            # Test absolute laboratory path
            {
                'shortpath': '/scratch/xx00',
                'model': 'test',
                'laboratory': '/scratch/aa00/user999/lab'
            }, '/scratch/aa00', 'user999', 'lab'
        ),
        (
            # Test user defined in config.yaml
            {
                'shortpath': '/scratch/xx00',
                'model': 'test',
                'user': 'user123'
            }, '/scratch/xx00', 'user123', 'test'
        ),
    ]
)
def test_laboratory_basepath(config, expected_shortpath, expected_user,
                             expected_labname):
    write_config(config)

    with cd(ctrldir):
        lab = Laboratory(None, None, None)
        basepath = Path(lab.basepath)

        # Check shortpath
        assert basepath.parent.parent.match(expected_shortpath)

        # Check userId - if fixed value
        if expected_user != '*':
            assert basepath.parent.name == expected_user

        # Check laboratory name
        assert basepath.name == expected_labname


@pytest.mark.parametrize(
    "config, expected_project, expected_labname",
    [
        (
            # Test default for project is env variable
            {
                'model': 'test',
            }, 'x00', 'test'
        ),
        (
            # Test project in config is used in default shortpath
            {
                'project': 'aa00',
                'model': 'test',
            }, 'aa00', 'test'
        ),
    ]
)
def test_laboratory_basepath_default_shortpath(config, expected_project,
                                               expected_labname):
    write_config(config)

    # Set a PROJECT env variable to x00 get reproducible paths
    os.environ['PROJECT'] = 'x00'

    with cd(ctrldir):
        lab = Laboratory(None, None, None)

        # Check base of shortpath is used
        assert lab.base in ['/short', '/scratch', '.']
        assert lab.basepath.startswith(lab.base)

        basepath = Path(lab.basepath)

        # Check project
        assert basepath.parent.parent.name == expected_project

        # Check lab name
        assert basepath.name == expected_labname
