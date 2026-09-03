import copy
import shutil
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from access_nri_intake.source import builders as builders

import payu
from test.common import cd
from test.common import tmpdir, ctrldir, labdir
from test.common import config as config_orig
from test.common import write_config, make_inputs

# Global config
config = copy.deepcopy(config_orig)

# Enable metadata
config.pop('metadata')


@pytest.fixture(autouse=True)
def setup_and_teardown():
    # Create tmp, lab and control directories
    try:
        tmpdir.mkdir()
        labdir.mkdir()
        ctrldir.mkdir()
    except Exception as e:
        print(e)

    yield

    # Remove tmp directory
    try:
        shutil.rmtree(tmpdir)
    except Exception as e:
        print(e)


def setup_experiment(additional_config=None, model=None):
    """Helper function to initialize an experiment with a given config."""
    test_config = copy.deepcopy(config)
    if additional_config is not None:
        test_config.update(additional_config)
    if model is not None:
        test_config['model'] = model

    write_config(test_config)
    make_inputs()

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab)
        return expt


def mock_make_intake_datastore(expt_name, expt_uuid, datastore_path):
    """Write a mock datastore description in the destination directory."""
    description = f"Intake-ESM datastores for experiment {expt_name} ({expt_uuid})"
    datastore_file = Path(datastore_path) / 'test_datastore.txt'
    with open(datastore_file, 'w') as f:
        f.write(description)

    
def check_intake_datastore_contents(datastore_path, expt_name, expt_uuid):
    """Check that the datastore file contains the expected description."""
    datastore_file = Path(datastore_path) / 'test_datastore.txt'
    with open(datastore_file, 'r') as f:
        content = f.read()
        expected_description = f"Intake-ESM datastores for experiment {expt_name} ({expt_uuid})"
        assert content == expected_description


@pytest.mark.parametrize("sync_config, sync", [
    (None, False),
    ({
        'sync': {
            'enable': True,
            'path': str(tmpdir / "sync_path"),
        }
    }, True),
    ({
        'sync': {
            'enable': True,
            'base_path': None,
            'path': None,
        }
    }, False),
])
def test_expt_make_datastore(monkeypatch, sync_config, sync):
    """Test the make_datastore choose sync path when sync is enabled, 
    and choose archive path when sync is disabled or unconfigured."""
    expt = setup_experiment(sync_config)

    # Mock the model.make_intake_datastore method
    expt.model.make_intake_datastore = MagicMock(side_effect=mock_make_intake_datastore)

    # Mock the remove_datastore function
    remove_datastore = MagicMock()
    monkeypatch.setattr(payu.experiment, 'remove_datastore', remove_datastore)

    expt.make_datastore()

    if sync:
        check_intake_datastore_contents(
            sync_config['sync']['path'], expt.name, expt.metadata.uuid)
    
        remove_datastore.assert_called_once_with(expt.archive_path)
    else:
        check_intake_datastore_contents(
            expt.archive_path, expt.name, expt.metadata.uuid)



def test_datastore_raises_error_for_unsupported_model():
    """Test that a NotImplementedError is raised for unsupported models."""
    expt = setup_experiment()

    with pytest.raises(NotImplementedError, match='Datastore generation is not implemented for this model.'):
        expt.make_datastore()


@pytest.mark.parametrize(
    "model_type, model_module, builder, builder_kwargs",
    [
        ('access', payu.models.access,
        builders.AccessEsm15Builder, {'ensemble': False}),
        ('access-esm1.6', payu.models.access_esm1p6,
         builders.AccessEsm16Builder, {'ensemble': False}),
        ('access-om2', payu.models.accessom2,
        builders.AccessOm2Builder, {}),
        ('mom6', payu.models.mom6,
         builders.Mom6Builder, {}),
    ]
)
def test_datastore_generation_uses_correct_builder(
        monkeypatch, model_type, model_module, builder, builder_kwargs):
    """Test each supported model calls use_datastore with its builder."""
    expt = setup_experiment(model=model_type)
    use_datastore = MagicMock()
    monkeypatch.setattr(model_module, 'use_datastore', use_datastore)

    expt.make_datastore()

    use_datastore.assert_called_once_with(
        experiment_dir=expt.archive_path,
        description=(
            f'Intake-ESM datastores for experiment {expt.name} '
            f'({expt.metadata.uuid})'
        ),
        builder=builder,
        builder_kwargs=builder_kwargs,
    )


def test_datastore_generation_skips_when_access_nri_intake_not_found(monkeypatch):
    """Test that a warning is issued and datastore generation is skipped when
    access_nri_intake is not found."""
    expt = setup_experiment(model='access-om2')

    def mock_import(name, *args, **kwargs):
        if name.startswith("access_nri_intake"):
            raise ImportError

    monkeypatch.setattr("builtins.__import__", mock_import)

    with pytest.warns(UserWarning, match="access_nri_intake not found, skip datastore generation."):
        expt.make_datastore()
