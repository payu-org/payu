import copy
import os
import sys
import types
from unittest.mock import MagicMock

import pytest

import payu
from payu.datastore import MakeIntakeDatastore

from test.common import cd
from test.common import tmpdir, ctrldir, labdir
from test.common import config as config_orig
from test.common import write_config
from test.common import make_all_files, write_metadata

# Global config
config = copy.deepcopy(config_orig)

# Enable metadata
config.pop('metadata')


@pytest.fixture(autouse=True)
def setup_module(setup_test_dir):
    make_all_files()
    write_metadata()
    yield


@pytest.fixture
def mock_intake_catalog(monkeypatch):
    """Inject a stand-in access_nri_intake package, since the real
    (optional) dependency is not installed in the test environment."""
    builders_mod = types.ModuleType("access_nri_intake.source.builders")

    # Real (dummy) classes, not MagicMock instances - datastore.py checks
    # issubclass(builder, AccessEsm15Builder), which requires an actual
    # class, and AccessEsm16Builder really does subclass AccessEsm15Builder.
    class AccessEsm15Builder:
        def __init__(self, path, ensemble, **kwargs):
            pass

    class AccessEsm16Builder(AccessEsm15Builder):
        pass

    class AccessOm2Builder:
        def __init__(self, path, **kwargs):
            pass

    class AccessOm3Builder:
        def __init__(self, path, **kwargs):
            pass

    class Mom6Builder:
        def __init__(self, path, **kwargs):
            pass

    for name, cls in [("AccessEsm15Builder", AccessEsm15Builder),
                      ("AccessEsm16Builder", AccessEsm16Builder),
                      ("AccessOm2Builder", AccessOm2Builder),
                      ("AccessOm3Builder", AccessOm3Builder),
                      ("Mom6Builder", Mom6Builder)]:
        setattr(builders_mod, name, cls)

    experiment_mod = types.ModuleType("access_nri_intake.experiment")
    use_datastore_mock = MagicMock()
    experiment_mod.use_datastore = use_datastore_mock

    monkeypatch.setitem(sys.modules, "access_nri_intake",
                        types.ModuleType("access_nri_intake"))
    monkeypatch.setitem(sys.modules, "access_nri_intake.source",
                        types.ModuleType("access_nri_intake.source"))
    monkeypatch.setitem(sys.modules, "access_nri_intake.source.builders",
                        builders_mod)
    monkeypatch.setitem(sys.modules, "access_nri_intake.experiment",
                        experiment_mod)

    return use_datastore_mock


def setup_experiment(additional_config, monkeypatch):
    """Given additional configuration, return an initialised Experiment"""
    test_config = copy.deepcopy(config)
    test_config.update(additional_config)
    write_config(test_config)

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        experiment = payu.experiment.Experiment(lab, reproduce=False)

    return experiment


def test_datastore_built_in_archive_when_sync_disabled(monkeypatch,
                                                        mock_intake_catalog):
    experiment = setup_experiment({}, monkeypatch)
    experiment.model_name = 'access-om2'

    MakeIntakeDatastore(experiment).run()

    assert mock_intake_catalog.call_count == 1
    called_kwargs = mock_intake_catalog.call_args.kwargs
    assert called_kwargs['experiment_dir'] == experiment.archive_path


def test_datastore_built_in_sync_path_when_sync_enabled(monkeypatch,
                                                         mock_intake_catalog):
    remote_archive = str(tmpdir / 'remote')
    additional_config = {
        "sync": {
            "enable": True,
            "path": remote_archive,
        }
    }
    experiment = setup_experiment(additional_config, monkeypatch)
    experiment.model_name = 'access-om2'

    MakeIntakeDatastore(experiment).run()

    assert mock_intake_catalog.call_count == 1
    called_kwargs = mock_intake_catalog.call_args.kwargs
    assert called_kwargs['experiment_dir'] == remote_archive


def test_datastore_removes_stale_archive_datastore_when_sync_enabled(
        monkeypatch, mock_intake_catalog):
    """If a datastore was previously built in the archive directory (e.g.
    before syncing was turned on), it should be removed once syncing is
    enabled, so a stale copy doesn't linger there or get synced over the
    current one at the sync destination."""
    remote_archive = str(tmpdir / 'remote')
    additional_config = {
        "sync": {
            "enable": True,
            "path": remote_archive,
        }
    }
    experiment = setup_experiment(additional_config, monkeypatch)
    experiment.model_name = 'access-om2'

    stale_files = [
        "experiment_datastore.json",
        "experiment_datastore.csv",
        ".experiment_datastore.hash",
        "experiment_datastore_invalid_assets_2026-01-01-00:00:00.csv",
    ]
    for filename in stale_files:
        with open(os.path.join(experiment.archive_path, filename), 'w') as f:
            f.write("stale")

    unrelated_file = os.path.join(experiment.archive_path, "metadata.yaml")
    with open(unrelated_file, 'w') as f:
        f.write("keep me")

    MakeIntakeDatastore(experiment).run()

    for filename in stale_files:
        assert not os.path.exists(
            os.path.join(experiment.archive_path, filename)
        ), f"expected stale {filename} to be removed"

    assert os.path.exists(unrelated_file)


def test_datastore_passes_ensemble_kwarg_for_esm_builders(monkeypatch,
                                                            mock_intake_catalog):
    """AccessEsm15Builder/AccessEsm16Builder require an explicit `ensemble`
    kwarg (unlike the other builders); regression test for a bug where
    use_datastore() was called without it, raising a TypeError."""
    experiment = setup_experiment({}, monkeypatch)
    experiment.model_name = 'access-esm1.6'

    MakeIntakeDatastore(experiment).run()

    called_kwargs = mock_intake_catalog.call_args.kwargs
    assert called_kwargs['builder_kwargs'] == {'ensemble': False}


def test_datastore_skipped_for_unsupported_model(monkeypatch,
                                                   mock_intake_catalog):
    experiment = setup_experiment({}, monkeypatch)
    experiment.model_name = 'test'

    with pytest.warns(UserWarning, match="No intake datastore builder found"):
        MakeIntakeDatastore(experiment).run()

    assert mock_intake_catalog.call_count == 0


def test_datastore_skipped_when_intake_catalog_not_installed(monkeypatch):
    monkeypatch.delitem(sys.modules, "access_nri_intake", raising=False)
    monkeypatch.delitem(sys.modules, "access_nri_intake.source", raising=False)
    monkeypatch.delitem(sys.modules, "access_nri_intake.source.builders",
                        raising=False)
    monkeypatch.delitem(sys.modules, "access_nri_intake.experiment",
                        raising=False)

    experiment = setup_experiment({}, monkeypatch)
    experiment.model_name = 'access-om2'

    with pytest.warns(UserWarning, match="access-nri-intake-catalog not found"):
        MakeIntakeDatastore(experiment).run()
