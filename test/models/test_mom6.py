import copy
import os
import shutil

import pytest
import f90nml

import payu

from test.common import cd
from test.common import tmpdir, ctrldir, labdir, expt_workdir, ctrldir_basename
from test.common import write_config, write_metadata
from test.common import make_random_file, make_inputs, make_exe

verbose = True


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
        make_exe()
        write_metadata()
    except Exception as e:
        print(e)

    config = {
            'laboratory': 'lab',
            'jobname': 'testrun',
            'model': 'mom6',
            'exe': 'test.exe',
            'experiment': ctrldir_basename,
            'metadata': {
                'enable': False
            }
    }
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
def test_mom6_add_parameter_files(input_nml,
                                  expected_files_added):
    # Create config.nml
    input_nml_fp = os.path.join(ctrldir, 'input.nml')
    f90nml.write(input_nml, input_nml_fp)

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)
        model = expt.models[0]

    prior_config_files = model.config_files[:]

    # Function to test
    payu.models.mom6.mom6_add_parameter_files(model)

    # Check files are added to config_files
    added_files = set(model.config_files).difference(prior_config_files)
    assert added_files == set(expected_files_added)

    # Tidy up input.nml
    os.remove(input_nml_fp)


def test_setup():
    input_nml = {
        "MOM_input_nml": {
            "input_filename": 'F',
            "parameter_filename": ["MOM_input", "MOM_override"]
        },
        "SIS_input_nml": {
            "parameter_filename": "SIS_input"
        }
    }

    expected_files_added = {'input.nml', 'diag_table',
                            'MOM_input', 'MOM_override', 'SIS_input'}

    # Create config files in control directory
    for file in expected_files_added:
        if file != 'input.nml':
            filename = os.path.join(ctrldir, file)
            make_random_file(filename, 8)

    # Create config.nml
    input_nml_fp = os.path.join(ctrldir, 'input.nml')
    f90nml.write(input_nml, input_nml_fp)

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)
        model = expt.models[0]

        # Function to test
        model.setup()

    # Check config files are moved to model's work path
    work_path_files = os.listdir(model.work_path)
    for file in expected_files_added:
        assert file in work_path_files

    # Check input.nml was patched as new run
    work_input_fpath = os.path.join(model.work_path, 'input.nml')
    input_nml = f90nml.read(work_input_fpath)
    assert input_nml['MOM_input_nml']['input_filename'] == 'n'
    assert input_nml['SIS_input_nml']['input_filename'] == 'n'
