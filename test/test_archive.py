import copy
import shutil

import pytest

import payu

from test.common import cd, ctrldir, expt_archive_dir, labdir, tmpdir
from test.common import make_exe, make_inputs, make_random_file
from test.common import payu_setup, write_config
from test.common import config as config_orig


@pytest.fixture(autouse=True)
def directories():
    tmpdir.mkdir()
    labdir.mkdir()
    ctrldir.mkdir()
    yield
    shutil.rmtree(tmpdir)


@pytest.mark.parametrize("from_restart", [False, True],
                         ids=["initial conditions", "restart: in config.yaml"])
def test_repeat_runs_archive(from_restart):
    config = copy.deepcopy(config_orig)
    config["repeat"] = True
    if from_restart:
        spinup = tmpdir / "spinup" / "restart000"
        spinup.mkdir(parents=True)
        (spinup / "restart.nc").write_text("spun up")
        config["restart"] = str(spinup)
    write_config(config)
    make_inputs()
    make_exe()
    # The files the test model needs
    for name in ["data", "diag", "input.nml"]:
        make_random_file(ctrldir / name, 29)

    for run in range(3):
        payu_setup(lab_path=str(labdir))
        with cd(ctrldir):
            expt = payu.experiment.Experiment(
                payu.laboratory.Laboratory(lab_path=str(labdir)))
            assert expt.counter == run
            expt.archive()

        outputs = sorted(path.name
                         for path in expt_archive_dir.glob("output*"))
        assert outputs == [f"output{n:03}" for n in range(run + 1)]
        # A repeat run keeps no restart of its own
        assert not list(expt_archive_dir.glob("restart*"))

    if from_restart:
        # The restart the runs start from is left alone
        assert (spinup / "restart.nc").read_text() == "spun up"
