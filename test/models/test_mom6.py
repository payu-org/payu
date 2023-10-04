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


@pytest.mark.parametrize(
        "input_nml, expected_files_added",
        [
            (
                {
                    "MOM_input_nml": {
                        "parameter_filename": "MOM_Input"
                    }
                },
                ["MOM_Input"]
            ),
            (
                {
                    "SIS_input_nml": {
                        "parameter_filename": "SIS_Input"
                    }
                },
                ["SIS_Input"]
            ),
            (
                {
                    "MOM_input_nml": {
                        "parameter_filename": ["MOM_Input", "MOM_override"]
                    },
                    "SIS_input_nml": {
                        "output_directory": '.'
                    }
                },
                ["MOM_Input", "MOM_override"]
            )
        ])
def test_add_config_files(input_nml,
                          expected_files_added):
    # Create config files in control directory
    for file in expected_files_added:
        filename = os.path.join(ctrldir, file)
        make_random_file(filename, 8)

    # Create config.nml
    input_nml_fp = os.path.join(expt_workdir, 'input.nml')
    f90nml.write(input_nml, input_nml_fp)

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)
        model = expt.models[0]

    prior_config_files = model.config_files[:]

    # Function to test
    model.add_config_files()

    # Check files are added to config_files
    added_files = set(model.config_files).difference(prior_config_files)
    assert added_files == set(expected_files_added)

    # Check the extra files are moved to model's work path
    ctrl_path_files = os.listdir(model.work_path)
    for file in expected_files_added:
        assert file in ctrl_path_files
