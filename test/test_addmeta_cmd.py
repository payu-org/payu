from pathlib import Path
from unittest.mock import MagicMock

import pytest

from payu.subcommands import addmeta_cmd


def _patch_command_dependencies(monkeypatch, config=None):
    experiment = MagicMock()
    experiment.timings = {"addmeta": 0.1}
    experiment.scheduler = MagicMock()
    experiment.config = {"addmeta": {}}
    experiment.archive_path = "/archive"
    experiment.get_job_file.return_value = "/archive/addmeta.job"

    monkeypatch.setattr(addmeta_cmd, "read_config", lambda _: config or {})
    monkeypatch.setattr(addmeta_cmd, "Laboratory", MagicMock())
    monkeypatch.setattr(addmeta_cmd, "Experiment", MagicMock(return_value=experiment))
    monkeypatch.setattr(addmeta_cmd.cli, "set_env_vars", MagicMock(return_value={"PAYU_CURRENT_RUN": 0}))
    return experiment


def test_submit_addmeta_passes_counter_and_dependency(monkeypatch):
    runcmd = MagicMock(return_value="123.server")
    monkeypatch.setattr(addmeta_cmd, "runcmd", runcmd)

    result = addmeta_cmd.submit_addmeta(0, depends_on="122.server", config={})

    assert result == "123.server"
    runcmd.assert_called_once_with(init_run=0, depends_on="122.server")


def test_submit_addmeta_wraps_submission_errors(monkeypatch):
    monkeypatch.setattr(addmeta_cmd, "runcmd", MagicMock(side_effect=RuntimeError("scheduler down")))

    with pytest.raises(addmeta_cmd.errors.PayuRuntimeError, match="Failed to submit sync job: scheduler down"):
        addmeta_cmd.submit_addmeta(1)


def test_runcmd_builds_addmeta_job_config(monkeypatch):
    submit_job = MagicMock(return_value="123.server")
    _patch_command_dependencies(
        monkeypatch,
        {"addmeta": {"queue": "debug", "mem": "1GB"}},
    )
    monkeypatch.setattr(addmeta_cmd.cli, "submit_job", submit_job)

    result = addmeta_cmd.runcmd(
        model_type="mom6",
        config_path="config.yaml",
        init_run=0,
        lab_path="lab",
        dir_path="/tmp/model-output",
        depends_on="122.server",
    )

    assert result == "123.server"
    job_config = submit_job.call_args.args[1]
    assert job_config == {
        "ncpus": 1,
        "queue": "debug",
        "mem": "1GB",
        "walltime": "0:30:00",
        "qsub_flags": "",
        "jobname": "model-output_a",
    }
    # Remove the experiment object from the call args for comparison
    submit_job.call_args.kwargs.pop("expt")  
    assert submit_job.call_args.kwargs == {
        "current_run": 0,
        "type": "addmeta",
        "depends_on": "122.server",
    }


def test_runscript_records_success(monkeypatch):
    experiment = _patch_command_dependencies(monkeypatch)
    record_run = MagicMock()
    monkeypatch.setattr(addmeta_cmd, "record_run", record_run)

    addmeta_cmd.runscript(
        model_type="mom6",
        config_path="config.yaml",
        init_run=0,
        lab_path="lab",
        dir_path="output",
    )

    experiment.set_counters.assert_called_once_with(keep_run_number=True)
    experiment.add_file_metadata.assert_called_once_with()
    record_run.assert_called_once_with(
        timings=experiment.timings,
        scheduler=experiment.scheduler,
        status=0,
        config=experiment.config,
        file_path="/archive/addmeta.job",
        archive_path=Path("/archive"),
        type="addmeta",
        stage="exited",
    )


def test_runscript_records_failure_and_reraises(monkeypatch):
    experiment = _patch_command_dependencies(monkeypatch)
    experiment.add_file_metadata.side_effect = RuntimeError("metadata failed")
    record_run = MagicMock()
    monkeypatch.setattr(addmeta_cmd, "record_run", record_run)

    with pytest.raises(RuntimeError, match="metadata failed"):
        addmeta_cmd.runscript(
            model_type="mom6",
            config_path="config.yaml",
            init_run=0,
            lab_path="lab",
            dir_path="output",
        )

    assert record_run.call_args.kwargs["status"] == 1
