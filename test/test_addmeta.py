from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from payu.addmeta import AddMeta


@pytest.mark.parametrize(
    "config, expected_files, expected_enable, expected_verbose, expected_metafiles",
    [
        ({"files": "output/*.nc", "verbose": True},
         "output/*.nc", True, True, []),
        ({"files": "restart/*.nc", "enable": False},
         "restart/*.nc", False, False, []),
        ({
            "files": "diagnostics/*.nc",
            "datavar": {"model": "mom6"},
            "metafiles": ["model.yaml"],
            "fnregex": r".*\\.nc$",
        }, "diagnostics/*.nc", True, False, ["model.yaml"]),
        ({}, None, True, False, []),
    ],
)
def test_from_config_merges_with_default_options(
    config, expected_files, expected_enable, expected_verbose, expected_metafiles
):
    addmeta_obj = AddMeta.from_config(config)

    assert getattr(addmeta_obj.options, "files", None) == expected_files
    assert addmeta_obj.options.enable is expected_enable
    assert addmeta_obj.options.verbose is expected_verbose
    assert addmeta_obj.options.metafiles == expected_metafiles


def test_update_combines_datavar_and_metafiles_and_replaces_other_options():
    addmeta_obj = AddMeta.from_config({
        "datavar": {"experiment": "base"},
        "metafiles": ["base.yaml"],
        "verbose": False,
    })

    addmeta_obj.update(SimpleNamespace(
        datavar={"model": "mom6"},
        metafiles=["model.yaml"],
        verbose=True,
        files="output/*.nc",
    ))

    assert addmeta_obj.options.datavar == {"experiment": "base", "model": "mom6"}
    assert addmeta_obj.options.metafiles == ["base.yaml", "model.yaml"]
    assert addmeta_obj.options.verbose is True
    assert addmeta_obj.options.files == "output/*.nc"


EXPECTED_META_DICT = {
    'global': {
        'experiment_uuid': "{{ metadata.experiment_uuid }}",
        'run_id': "{{ env.PAYU_RUN_ID}}",
    },
}


@pytest.mark.parametrize(
    "config, cli_namespace, expected_options",
    [
        (
            {"files": "output/*.nc"},
            None,
            {
                "enable": True, "verbose": False, "update_history": False,
                "data": {}, "metafiles": [], "datafiles": [], "fnregex": "",
                "datavar": {}, "metalist": "", "sort": True,
                "files": "output/*.nc",
            },
        ),
        (
            {"files": "restart/*.nc", "enable": False},
            None,
            {
                "enable": False, "verbose": False, "update_history": False,
                "data": {}, "metafiles": [], "datafiles": [], "fnregex": "",
                "datavar": {}, "metalist": "", "sort": True,
                "files": "restart/*.nc",
            },
        ),
        (
            {"files": "output/*.nc"},
            SimpleNamespace(verbose=True, files="output/*.nc"),
            {
                "enable": True, "verbose": True, "update_history": False,
                "data": {}, "metafiles": [], "datafiles": [], "fnregex": "",
                "datavar": {}, "metalist": "", "sort": True,
                "files": "output/*.nc",
            },
        ),
        (
            {"files": "diagnostics/*.nc", "metafiles": ["model.yaml"]},
            SimpleNamespace(metafiles=["run.yaml"], datavar={"model": "mom6"}),
            {
                "enable": True, "verbose": False, "update_history": False,
                "data": {}, "metafiles": ["model.yaml", "run.yaml"],
                "datafiles": [], "fnregex": "", "datavar": {"model": "mom6"},
                "metalist": "", "sort": True, "files": "diagnostics/*.nc",
            },
        ),
        (
            {"files": "output/*.nc", "datavar": {"experiment": "base"}},
            SimpleNamespace(datavar={"model": "mom6"}, fnregex=r"access-esm1p6\.\w+(?:\.\dd)?\.(?P<var>\w+)\.(?P<freq>\w{2,4})(?:\.\w+)?(?:\.\d{4})?\.nc"),
            {
                "enable": True, "verbose": False, "update_history": False,
                "data": {}, "metafiles": [], "datafiles": [],
                "fnregex": r"access-esm1p6\.\w+(?:\.\dd)?\.(?P<var>\w+)\.(?P<freq>\w{2,4})(?:\.\w+)?(?:\.\d{4})?\.nc",
                "datavar": {"experiment": "base", "model": "mom6"},
                "metalist": "", "sort": True, "files": "output/*.nc",
            },
        ),
    ],
)
def test_run_passes_configured_files_to_addmeta(
    monkeypatch, config, cli_namespace, expected_options
):
    addmeta_obj = AddMeta.from_config(config)
    if cli_namespace is not None:
        addmeta_obj.update(cli_namespace)

    assert vars(addmeta_obj.options) == expected_options

    addmeta_main = MagicMock()
    monkeypatch.setattr("payu.addmeta.addmeta_cli.main", addmeta_main)

    addmeta_obj.run(EXPECTED_META_DICT)

    addmeta_main.assert_called_once_with(addmeta_obj.options, EXPECTED_META_DICT)
