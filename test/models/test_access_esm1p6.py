import copy
import os
import shutil
import f90nml

import pytest

import payu
from payu.models.access_esm1p6 import AccessEsm1p6

from test.common import cd, expt_workdir
from test.common import tmpdir, ctrldir, labdir, workdir, archive_dir
from test.common import config as config_orig
from test.common import write_config
from test.common import make_all_files
from test.common import config_path

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
        archive_dir.mkdir()
        make_all_files()
    except Exception as e:
        print(e)


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
def empty_workdir():
    """
    Model setup tests require a clean work directory and symlink from
    the control directory.
    """
    expt_workdir.mkdir(parents=True)
    # Symlink must exist for setup to use correct locations
    workdir.symlink_to(expt_workdir)

    yield expt_workdir
    try:
        shutil.rmtree(expt_workdir)
    except FileNotFoundError:
        pass
    workdir.unlink()


@pytest.fixture
def esm1p6_um_only_config():
    """
    Configuration for experiment with UM as a submodel
    of ESM1.6
    """
    config = copy.deepcopy(config_orig)
    config["model"] = "access-esm1.6"
    config["submodels"] = [{"name": "atmosphere",
                           "model": "um"}]
    write_config(config)

    # Run test
    yield

    # Teardown
    os.remove(config_path)


@pytest.fixture
def um_only_ctrl_dir():
    """
    Configuration for experiment with UM as standalone
    model
    """
    # First make a separate control directory for standalone UM experiment
    um_ctrl_dir = tmpdir/"um_only_ctrl"
    um_ctrl_dir.mkdir()

    config = copy.deepcopy(config_orig)
    config["model"] = "um"

    write_config(config, path=um_ctrl_dir/"config.yaml")

    # Run test
    yield um_ctrl_dir

    # Teardown
    shutil.rmtree(um_ctrl_dir)


def test_esm1p6_patch_optional_config_files(um_only_ctrl_dir,
                                            esm1p6_um_only_config):
    """
    Test that the access-esm1.6 driver correctly updates the UM
    configuration files.
    """
    # Initialise standalone UM model
    with cd(um_only_ctrl_dir):
        um_config_path = um_only_ctrl_dir / "config.yaml"
        um_lab = payu.laboratory.Laboratory(lab_path=str(labdir),
                                            config_path=um_config_path) 
        um_expt = payu.experiment.Experiment(um_lab, reproduce=False)

    um_standalone_model = um_expt.models[0]

    # Initialise ESM1.6 with UM submodel
    with cd(ctrldir):
        esm1p6_lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        esm1p6_expt = payu.experiment.Experiment(esm1p6_lab, reproduce=False)

    for model in esm1p6_expt.models:
        if model.model_type == "um":
            esm1p6_um_model = model

    # Check there are no duplicate files from double initialisation
    assert (
        len(esm1p6_um_model.optional_config_files) ==
        len(set(esm1p6_um_model.optional_config_files))
    )

    # Check that esm1p6 driver added new config files compared
    # to the standalone UM.

    expected_files = ["soil.nml", "pft_params.nml"]
    assert (
        set(esm1p6_um_model.optional_config_files) ==
        set(um_standalone_model.optional_config_files).union(expected_files)
    )


def test_get_cur_expt_time(um_only_ctrl_dir, esm1p6_um_only_config):
    """
    Test that the access-esm1.6 driver correctly parses the model_basis_time.
    """
    # Initialise ESM1.6
    with cd(ctrldir):
        esm1p6_lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        esm1p6_expt = payu.experiment.Experiment(esm1p6_lab, reproduce=False)

    # write the namelist with a known model_basis_time (start date)
    nl_path = os.path.join(esm1p6_expt.work_path, 'atmosphere', 'namelists')
    os.makedirs(os.path.dirname(nl_path), exist_ok=True)
    model_basis_time = [1900, 1, 31, 0, 0, 0]
    nml = f90nml.Namelist()
    nml['nlstcall'] = {'model_basis_time': model_basis_time}
    f90nml.write(nml, nl_path, force=True)

    #write log file with a known timestep and default step length (30 min)
    log_path = os.path.join(esm1p6_expt.work_path, 'atmosphere', 'atm.fort6.pe0')
    with open(log_path, 'w') as f:
        f.write(f"U_MODEL: STEPS_PER_PERIODim=                    48\n")
        f.write(f"U_MODEL: SECS_PER_PERIODim=                 86400\n")
        f.write(f"Atm_Step: Timestep                      10\n")

    cur_expt_time = esm1p6_expt.get_model_cur_expt_time()
    assert cur_expt_time == "1900-01-31T05:00:00"


@pytest.mark.parametrize("missing_file", [
    (
        ['namelists']
    ),
    (
        ['atm.fort6.pe0']
    ),
    (
        ['namelists', 'atm.fort6.pe0']
    )
])
def test_get_cur_expt_time_missing_files(um_only_ctrl_dir, esm1p6_um_only_config, missing_file):
    """
    Test that the access-esm1.6 driver correctly handles missing files.
    """
    # Initialise ESM1.6
    with cd(ctrldir):
        esm1p6_lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        esm1p6_expt = payu.experiment.Experiment(esm1p6_lab, reproduce=False)

    nl_path = os.path.join(esm1p6_expt.work_path, 'atmosphere', 'namelists')
    log_path = os.path.join(esm1p6_expt.work_path, 'atmosphere', 'atm.fort6.pe0')
    os.makedirs(os.path.dirname(nl_path), exist_ok=True)
    open(nl_path, 'a').close()
    open(log_path, 'a').close()

    if 'namelists' in missing_file:
        os.remove(nl_path)
    if 'atm.fort6.pe0' in missing_file:
        os.remove(log_path)

    with pytest.warns(UserWarning, match=f"Could not find required files: {nl_path} or {log_path}"):
        cur_expt_time = esm1p6_expt.get_model_cur_expt_time()
        assert cur_expt_time is None

def test_read_start_date(um_only_ctrl_dir, esm1p6_um_only_config):
    # Initialise ESM1.6
    with cd(ctrldir):
        esm1p6_lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        esm1p6_expt = payu.experiment.Experiment(esm1p6_lab, reproduce=False)

    model = AccessEsm1p6(expt=esm1p6_expt, name="test_esm1p6", config={})
    nl_path = os.path.join(esm1p6_expt.work_path, 'atmosphere', 'namelists')
    os.makedirs(os.path.dirname(nl_path), exist_ok=True)
    nml = f90nml.Namelist()
    nml['top_key'] = {'key': 'value'}
    f90nml.write(nml, nl_path, force=True)
    with pytest.warns(UserWarning, match=f"model_basis_time not found in {nl_path}"):
        model.read_start_date(nl_path)

def test_convert_timestep(um_only_ctrl_dir, esm1p6_um_only_config):
    """ Test with an invalid log file"""
    # Initialise ESM1.6
    with cd(ctrldir):
        esm1p6_lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        esm1p6_expt = payu.experiment.Experiment(esm1p6_lab, reproduce=False)
    
    model = AccessEsm1p6(expt=esm1p6_expt, name="test_esm1p6", config={})
    log_path = os.path.join(esm1p6_expt.work_path, 'atmosphere', 'atm.fort6.pe0')
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    # write invalid content into log file
    with open(log_path, 'w') as f:
        f.write(f"U_MODEL: STEPS_PER_PERIODim=                    48\n")
        f.write(f"U_MODEL: SECS_PER_PERIODim=                 86400\n")
        f.write(f"There is no Atm_Step: Timestep\n")

    with pytest.warns(UserWarning, match=f"""Could not find all required entries in file {log_path}
                to calculate run time"""):
        model.convert_timestep(log_path)
