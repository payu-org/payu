from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import addmeta
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
            "data": {"model": "mom6"},
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


def test_update_combines_data_and_metafiles_and_replaces_other_options():
    addmeta_obj = AddMeta.from_config({
        "data": {"experiment": "base"},
        "metafiles": ["base.yaml"],
        "verbose": False,
    })

    addmeta_obj.update(SimpleNamespace(
        data={"model": "mom6"},
        metafiles=["model.yaml"],
        verbose=True,
        files="output/*.nc",
    ))

    assert addmeta_obj.options.data == {"experiment": "base", "model": "mom6"}
    assert addmeta_obj.options.metafiles == ["base.yaml", "model.yaml"]
    assert addmeta_obj.options.verbose is True
    assert addmeta_obj.options.files == "output/*.nc"


def test_run_passes_configured_files_to_addmeta(monkeypatch):
    addmeta_obj = AddMeta.from_config({"files": "output/*.nc"})
    main = MagicMock()
    monkeypatch.setattr("addmeta.cli.main", main)

    addmeta_obj.run()

    expected_options = {'enable': True, 
                       'verbose': False, 
                       'update-history': False, 
                       'data': {}, 
                       'metafiles': [], 
                       'datafiles': [], 
                        'fnregex': '', 
                        'files': 'output/*.nc'}

    expected_options = SimpleNamespace(**expected_options)

    main.assert_called_once_with(expected_options)
