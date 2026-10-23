import os
from unittest.mock import MagicMock
import pytest
from payu.subcommands import collate_cmd, postscript_cmd, sync_cmd


def mock_experiment(lab):
    """ A mock experiment object with return values for counters and set_userscript_env_vars """
    experiment = MagicMock()
    experiment.scheduler_name = "pbs"
    experiment.set_userscript_env_vars.return_value = {}

    return experiment

@pytest.mark.parametrize(
    "command_mod, config",
    [
        (collate_cmd, {"collate": {}}),
        (postscript_cmd, {"postscript": "postscript.sh"}),
        (sync_cmd, {"sync": {}}),
    ],
)
def test_runcmd_preserves_zero_init_run(monkeypatch, command_mod, config):
    monkeypatch.setattr(command_mod, "read_config", lambda _: config.copy())
    monkeypatch.setattr(command_mod, "Laboratory", MagicMock())
    monkeypatch.setattr(command_mod, "Experiment", mock_experiment)

    monkeypatch.setattr(command_mod.cli, "set_env_vars", MagicMock(return_value={}))
    submit_job = MagicMock(return_value="1000-gadi.pbs")
    monkeypatch.setattr(command_mod.cli, "submit_job", submit_job)

    assert command_mod.runcmd(init_run=0) == "1000-gadi.pbs"
    assert submit_job.call_args.kwargs["current_run"] == 0


@pytest.mark.parametrize(
    "init_run, expected_seen_run",
    [
        (0, "0"),
        (7, "7"),
        (None, "2"),
    ],
)
def test_postscript_runcmd_updates_current_run_before_experiment_init(monkeypatch, init_run, expected_seen_run):
    monkeypatch.setenv("PAYU_CURRENT_RUN", "2")
    monkeypatch.setattr(postscript_cmd, "read_config", lambda _: {"postscript": "postscript.sh"})
    monkeypatch.setattr(postscript_cmd, "Laboratory", MagicMock())

    current_run_seen_by_experiment = []

    def experiment_stub(lab):
        current_run_seen_by_experiment.append(os.environ["PAYU_CURRENT_RUN"])
        return mock_experiment(lab)

    monkeypatch.setattr(postscript_cmd, "Experiment", experiment_stub)
    monkeypatch.setattr(postscript_cmd.cli, "submit_job", MagicMock(return_value="1000-gadi.pbs"))

    postscript_cmd.runcmd(init_run=init_run)
    assert current_run_seen_by_experiment == [expected_seen_run]
    