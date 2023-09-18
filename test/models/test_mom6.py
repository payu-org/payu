import copy
import os
import shutil

import pytest
import f90nml

import payu

from test.common import cd
from test.common import tmpdir, ctrldir, labdir, expt_workdir
from test.common import config as config_orig
from test.common import write_config
from test.common import make_random_file, make_inputs

verbose = True

# Global config
config = copy.deepcopy(config_orig)
config["model"] = "mom6"


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
        expt_workdir.mkdir(parents=True)
        make_inputs()
    except Exception as e:
        print(e)

    write_config(config)


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

    # Remove any files in expt work directory
    for file in os.listdir(expt_workdir):
        try:
            os.remove(os.path.join(expt_workdir, file))
        except Exception as e:
            print(e)


def make_config_files(parameter_files):
    """Make config files in control directory"""
    for file in parameter_files:
        filename = os.path.join(ctrldir, file)
        make_random_file(filename, 8)


def make_input_nml_file(mom_parameter_files, sis_parameter_files=None):
    """Create an input.nml in expt work directory"""
    input_nml = {
        'MOM_input_nml': {
            'parameter_filename': mom_parameter_files,
        }
    }
    if sis_parameter_files:
        input_nml['SIS_input_nml'] = {
            'parameter_filename': sis_parameter_files,
        }
    input_nml_fp = os.path.join(expt_workdir, 'input.nml')
    f90nml.write(input_nml, input_nml_fp)


@pytest.mark.parametrize(
    "mom_parameter_files, sis_parameter_files, expected_files_added",
    [
        (
            ['MOM_input'],
            ['SIS_input', 'SIS_layout'],
            []
        ),
        (
            ['MOM_input', 'MOM_layout'],
            ['SIS_input', 'New_SIS_file'],
            ['New_SIS_file']
        ),
        (
            ['New_MOM_file', 'MOM_input'],
            None,
            ['New_MOM_file']
        )
    ])
def test_add_parameter_config_files(mom_parameter_files,
                                    sis_parameter_files,
                                    expected_files_added):
    # Create config files in control directory
    make_config_files(mom_parameter_files)
    if sis_parameter_files:
        make_config_files(sis_parameter_files)

    # Create config.nml
    make_input_nml_file(mom_parameter_files, sis_parameter_files)

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)
        model = expt.models[0]

    prior_config_files = model.config_files[:]

    # Function to test
    model.add_parameter_config_files()

    # Check files are added to config_files
    added_files = set(model.config_files).difference(prior_config_files)
    assert added_files == set(expected_files_added)

    # Check the extra files are moved to model's work path
    ctrl_path_files = os.listdir(model.work_path)
    for file in expected_files_added:
        assert file in ctrl_path_files
