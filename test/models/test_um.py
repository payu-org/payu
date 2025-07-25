import copy
import os
import shutil

import pytest
import datetime
import cftime
import yaml

import payu

from test.common import cd
from test.common import tmpdir, ctrldir, labdir
from test.common import config as config_orig
from test.common import write_config
from test.common import make_all_files
from test.common import list_expt_archive_dirs
from test.common import make_expt_archive_dir, remove_expt_archive_dirs


verbose = True

# Global config
config = copy.deepcopy(config_orig)

UM_RES_FILE = "um.res.yaml"

def setup_module(module):
    """
    Put any test-wide setup code in here, e.g. creating test files
    """
    if verbose:
        print("setup_module      module:%s" % module.__name__)

    # Should be taken care of by teardown, in case remnants lying around
    try:
        shutil.rmtree(tmpdir)
    except FileNotFoundError:
        pass

    try:
        tmpdir.mkdir()
        labdir.mkdir()
        ctrldir.mkdir()
        make_all_files()
    except Exception as e:
        print(e)

    # Write config
    test_config = config
    test_config['model'] = 'um'
    write_config(test_config)


def teardown_module(module):
    """
    Put any test-wide teardown code in here, e.g. removing test outputs
    """
    if verbose:
        print("teardown_module   module:%s" % module.__name__)

    try:
        shutil.rmtree(tmpdir)
        print('removing tmp')
    except Exception as e:
        print(e)


@pytest.fixture(autouse=True)
def teardown():
    # Run test
    yield

    # Remove any created restart files
    remove_expt_archive_dirs(type='restart')


def make_atmosphere_restart_dir(date,
                                restart_index=0,
                                additional_path=None):
    """Create tests restart directory with um.res.yaml file"""
    # Create restart directory
    restart_path = make_expt_archive_dir(type='restart',
                                         index=restart_index,
                                         additional_path=additional_path)

    # Create um.res.yaml file
    calendar_file_path = os.path.join(restart_path, UM_RES_FILE)

    with open(calendar_file_path, 'w') as um_cal_file:
        # yaml parser expects datetime.datetime object
        date_out = datetime.datetime(date.year,
                                     date.month,
                                     date.day,
                                     date.hour,
                                     date.minute,
                                     date.second)
        um_cal_file.write(yaml.dump({'end_date': date_out},
                                    default_flow_style=False))


@pytest.mark.parametrize(
    "date",
    [
        (
            cftime.datetime(1900, 2, 1, calendar="proleptic_gregorian")
        ),
        (
            cftime.datetime(1000, 11, 12, 12, 23, 34,
                            calendar="proleptic_gregorian")
        ),
        (
            cftime.datetime(101, 1, 1, calendar="proleptic_gregorian")
        ),
        (
            cftime.datetime(400, 2, 29, calendar="proleptic_gregorian")
        ),
    ])
def test_um_get_restart_datetime(date):
    """
    Check the UM driver correctly reads restart dates as cftime
    objects.
    """
    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)

    make_atmosphere_restart_dir(date)

    restart_path = list_expt_archive_dirs()[0]
    parsed_run_dt = expt.model.get_restart_datetime(restart_path)
    assert parsed_run_dt == date
