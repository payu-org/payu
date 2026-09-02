from unittest.mock import MagicMock
import pytest
from payu.subcommands import collate_cmd, postscript_cmd, sync_cmd


@pytest.mark.parametrize(
    "command_mod, config",
    [
        (collate_cmd, {"collate": {}}),
        (postscript_cmd, {"postscript": "postscript.sh"}),
        (sync_cmd, {"sync": {}}),
    ],
)
def test_runcmd_preserves_zero_init_run(monkeypatch, command_mod, config):
    experiment = MagicMock()
    experiment.scheduler_name = "pbs"
    experiment.set_userscript_env_vars.return_value = {}

    monkeypatch.setattr(command_mod, "read_config", lambda _: config.copy())
    monkeypatch.setattr(command_mod, "Laboratory", MagicMock())
    monkeypatch.setattr(
        command_mod,
        "Experiment",
        MagicMock(return_value=experiment),
    )
    monkeypatch.setattr(command_mod.cli, "set_env_vars", MagicMock(return_value={}))
    submit_job = MagicMock(return_value="12")
    monkeypatch.setattr(command_mod.cli, "submit_job", submit_job)

    assert command_mod.runcmd(init_run=0) == "12"
    assert submit_job.call_args.kwargs["current_run"] == 0
