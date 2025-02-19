import copy
import os
import shutil

import pytest

import payu

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
