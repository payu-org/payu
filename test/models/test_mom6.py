import os
import shutil
from pathlib import Path

import pytest
import f90nml

import payu

from test.common import cd
from test.common import tmpdir, ctrldir, labdir, expt_workdir, ctrldir_basename
from test.common import write_config, write_metadata
from test.common import make_random_file, make_inputs, make_exe
from test.test_git_utils import create_new_repo

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

@pytest.fixture
def mom_parameter_doc(request):

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)
        model = expt.models[0]

   # Create docs
    if (request.param != None) :
        for file in request.param:
            filename = os.path.join(model.work_path, file)
            make_random_file(filename, 8)

    yield model

    # and Tidy up 
    if (request.param != None) :
        for file in request.param:
            filename = os.path.join(model.work_path, file)
            os.remove(filename)


@pytest.mark.parametrize(
        "mom_parameter_doc", 
        [["MOM_parameter_doc.all","MOM_parameter_doc.debug","MOM_parameter_docs.debug", "available_diags.000000"]],
        indirect=True
)
@pytest.mark.filterwarnings("error")
def test_mom6_save_doc_files(mom_parameter_doc):
    # Confirm that mom6_save_doc_filse moves files names MOM_parameter_doc.* into the docs folder of a config
    # and doesn't move files that don't match that name

    # don't try and commit during tests
    mom_parameter_doc.expt.runlog.enabled = False

    # Function to test
    payu.models.mom6.mom6_save_docs_files(mom_parameter_doc)

    # Check MOM_parameter_doc.* are added to control_path
    for file in ["MOM_parameter_doc.all","MOM_parameter_doc.debug", "available_diags.000000"]:
        filename = os.path.join(mom_parameter_doc.control_path, "docs", file)
        assert os.path.isfile(filename)==True , "Payu did not move MOM_parameter_doc.* files into docs folder"
        os.remove(filename)

    # Check fake files are not added to control_path
    for file in ["MOM_parameter_docs.debug"]:
        filename = os.path.join(mom_parameter_doc.control_path, "docs", file)
        assert os.path.isfile(filename)==False, "Payu incorrectly moved MOM_parameter_docs.* files into docs folder"


@pytest.mark.parametrize(
        "mom_parameter_doc", 
        [["MOM_parameter_doc.layout"]],
        indirect=True
)
@pytest.mark.filterwarnings("error")
def test_mom6_commit_doc_files(mom_parameter_doc):
    # Confirm that mom6_save_doc_files commits files named MOM_parameter_doc.* into the docs folder of a config
    mom_parameter_doc.expt.runlog.enabled = True

    #init a git repo
    repo = create_new_repo(Path(mom_parameter_doc.control_path))
    initial_commit = repo.head.commit

    # Function to test
    payu.models.mom6.mom6_save_docs_files(mom_parameter_doc)

    # Check files are added to control_path
    for file in ["MOM_parameter_doc.layout"]:
        filename = os.path.join(mom_parameter_doc.control_path, "docs", file)
        assert os.path.isfile(filename)==True , "docs/MOM_parameter_doc.* do not exist"
        os.remove(filename)
    
    assert repo.head.commit != initial_commit,  "Payu did not commit MOM_parameter_doc.layout"

    # Confirm it doesn't commit twice if unchanged
    initial_commit = repo.head.commit
    payu.models.mom6.mom6_save_docs_files(mom_parameter_doc)

    assert repo.head.commit == initial_commit,  "Payu commit MOM_parameter_doc incorrectly"

    # Confirm it does commit twice correctly
    file = "MOM_parameter_doc.all"
    filename = os.path.join(mom_parameter_doc.work_path, file)
    make_random_file(filename, 8)

    payu.models.mom6.mom6_save_docs_files(mom_parameter_doc)

    assert repo.head.commit != initial_commit,  "Payu did not commit MOM_parameter_doc.all"

    # and Tidy up 
    filename = os.path.join(mom_parameter_doc.work_path, file)
    os.remove(filename)


@pytest.mark.parametrize(
        "mom_parameter_doc", 
        [["MOM_parameter_doc.layout"]],
        indirect=True
)
@pytest.mark.filterwarnings("error")
def test_mom6_not_commit_doc_files(mom_parameter_doc):
    # Confirm that mom6_save_doc_files doesn't commits files if runlog is False

    mom_parameter_doc.expt.runlog.enabled = False

    #init a git repo
    repo = create_new_repo(Path(mom_parameter_doc.control_path))
    initial_commit = repo.head.commit

    # Function to test
    payu.models.mom6.mom6_save_docs_files(mom_parameter_doc)

    # Check files are added to control_path
    for file in ["MOM_parameter_doc.layout"]:
        filename = os.path.join(mom_parameter_doc.control_path, "docs", file)
        assert os.path.isfile(filename)==True , "docs/MOM_parameter_doc.* do not exist"
        os.remove(filename)
    
    assert repo.head.commit == initial_commit,  "Payu incorrectly committed MOM_parameter_docs.layout"

@pytest.mark.parametrize(
        "mom_parameter_doc", 
        [None],
        indirect=True
)
@pytest.mark.filterwarnings("error")
def test_mom6_not_commit_doc_files(mom_parameter_doc):
    # Confirm that mom6_save_doc_files doesn't commits files if runlog is False

    #init a git repo
    repo = create_new_repo(Path(mom_parameter_doc.control_path))
    initial_commit = repo.head.commit

    # Function to test
    payu.models.mom6.mom6_save_docs_files(mom_parameter_doc)
   
    assert repo.head.commit == initial_commit,  "Payu incorrectly committed with no docs to add"


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


def test_get_cur_expt_time():
    """ Test that get_model_cur_expt_time() correctly reads the start date from input.nml 
    and the time from ocean.stats."""
    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)

    # Write a restart date into input.nml
    input_path = os.path.join(expt.work_path, 'input.nml')
    nml = f90nml.Namelist()
    nml['ocean_solo_nml'] = {'date_init': [1900, 1, 31, 0, 0, 0]}
    f90nml.write(nml, input_path, force=True)

    # Write a timestep into ocean.stats
    stats_path = os.path.join(expt.work_path, 'ocean.stats')
    with open(stats_path, 'w') as f:
        f.write("360,      50.000,\n") # timestep, time in days

    # Write a calendar into ocean_solo.res
    ocean_solo_path = os.path.join(expt.work_path, 'INPUT', 'ocean_solo.res')
    os.makedirs(expt.restart_path, exist_ok=True)
    with open(ocean_solo_path, 'w') as f:
        f.write("2\n")  # Use Julian calendar

    cur_expt_time = expt.get_model_cur_expt_time()
    assert cur_expt_time.isoformat() == "1900-03-21T00:00:00"
    
@pytest.mark.parametrize("missing_file",[
    (
        ['input.nml']
    ),
    (
        ['ocean.stats']
    ),
    (
        ['ocean_solo.res']
    ),
    (
        ['input.nml', 'ocean.stats', 'ocean_solo.res']
    )
])
def test_get_cur_expt_time_missing_files(missing_file):
    """ Test that get_model_cur_expt_time() correctly handles missing files."""
    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)

    # Write a restart date into input.nml
    input_path = os.path.join(expt.work_path, 'input.nml')
    nml = f90nml.Namelist()
    nml['ocean_solo_nml'] = {'date_init': [1900, 1, 31, 0, 0, 0]}
    f90nml.write(nml, input_path, force=True)

    # Write a timestep into ocean.stats
    stats_path = os.path.join(expt.work_path, 'ocean.stats')
    with open(stats_path, 'w') as f:
        f.write("360,      50.000,\n") # timestep, time in days

    # Write a calendar into ocean_solo.res
    ocean_solo_path = os.path.join(expt.work_path, 'INPUT', 'ocean_solo.res')
    os.makedirs(expt.restart_path, exist_ok=True)
    with open(ocean_solo_path, 'w') as f:
        f.write("2\n")  # Use Julian calendar

    for file in missing_file:
        if file == 'input.nml' or file == 'ocean.stats':
            os.remove(os.path.join(expt.work_path, file))
        elif file == 'ocean_solo.res':
            os.remove(os.path.join(expt.work_path, 'INPUT', file))

    with pytest.raises(FileNotFoundError):
        cur_expt_time = expt.get_model_cur_expt_time()


def test_read_start_date():
    """ Test that read_start_date() correctly handle errors."""
    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)

    # Write a restart date into input.nml
    input_path = os.path.join(expt.work_path, 'input.nml')
    nml = f90nml.Namelist()
    nml['top_key'] = {'key': 'value'}
    f90nml.write(nml, input_path, force=True)

    # Write a timestep into ocean.stats
    stats_path = os.path.join(expt.work_path, 'ocean.stats')
    with open(stats_path, 'w') as f:
        f.write("360,      50.000,\n")
    
    # Write a calendar and current model time into ocean_solo.res
    ocean_solo_path = os.path.join(expt.work_path, 'INPUT', 'ocean_solo.res')
    os.makedirs(os.path.dirname(ocean_solo_path), exist_ok=True)
    with open(ocean_solo_path, 'w') as f:
        f.write("2\n")  # Use Julian calendar

    with pytest.raises(ValueError, match=f"Key 'date_init' not found in {input_path}"):
        cur_expt_time = expt.get_model_cur_expt_time()
        assert cur_expt_time is None


def test_read_timestep():
    """ Test that read_timestep() correctly handle errors."""
    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)

    # Write a restart date into input.nml
    input_path = os.path.join(expt.work_path, 'input.nml')
    nml = f90nml.Namelist()
    nml['ocean_solo_nml'] = {'date_init': [1900, 1, 31, 0, 0, 0]}
    f90nml.write(nml, input_path, force=True)

    # Write a timestep into ocean.stats
    stats_path = os.path.join(expt.work_path, 'ocean.stats')
    with open(stats_path, 'w') as f:
        f.write("0\n")
    
    # Write a calendar into ocean_solo.res
    ocean_solo_path = os.path.join(expt.work_path, 'INPUT', 'ocean_solo.res')
    os.makedirs(os.path.dirname(ocean_solo_path), exist_ok=True)
    with open(ocean_solo_path, 'w') as f:
        f.write("2\n")  # Use Julian calendar

    with pytest.raises(IndexError):
        cur_expt_time = expt.get_model_cur_expt_time()

def test_get_calendar():
    """ Test that get_calendar() correctly handle error when ocean_solo.res is empty."""
    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)

    # Write a restart date into input.nml
    input_path = os.path.join(expt.work_path, 'input.nml')
    nml = f90nml.Namelist()
    nml['ocean_solo_nml'] = {'date_init': [1900, 1, 31, 0, 0, 0]}
    f90nml.write(nml, input_path, force=True)

    # Write a timestep into ocean.stats
    stats_path = os.path.join(expt.work_path, 'ocean.stats')
    with open(stats_path, 'w') as f:
        f.write("0\n")
    
    # Write a calendar into ocean_solo.res
    ocean_solo_path = os.path.join(expt.work_path, 'INPUT', 'ocean_solo.res')
    os.makedirs(os.path.dirname(ocean_solo_path), exist_ok=True)
    with open(ocean_solo_path, 'w') as f:
        f.write("\n")  # Empty

    with pytest.raises(IndexError):
        cur_expt_time = expt.get_model_cur_expt_time()