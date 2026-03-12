import copy
import os
import shutil
import pytest

import payu
import cftime

from test.common import cd, tmpdir, ctrldir, labdir, workdir, write_config, config_path
from test.common import config as config_orig
from test.common import make_inputs, make_exe
from test.common import list_expt_archive_dirs, make_expt_archive_dir, remove_expt_archive_dirs

MODEL = 'access-om2'

def setup_module(module):
    """
    Put any test-wide setup code in here, e.g. creating test files
    """

    # Should be taken care of by teardown, in case remnants lying around
    try:
        shutil.rmtree(tmpdir)
    except FileNotFoundError:
        pass

    try:
        tmpdir.mkdir()
        labdir.mkdir()
        ctrldir.mkdir()
        workdir.mkdir()
        # archive_dir.mkdir()
        make_inputs()
        make_exe()
    except Exception as e:
        print(e)


def cmeps_config(ncpu):
    # Create a config.yaml and nuopc.runconfig file

    config = copy.deepcopy(config_orig)
    config['model'] = MODEL
    config['ncpus'] = ncpu

    write_config(config)

    with open(os.path.join(ctrldir, 'nuopc.runconfig'), "w") as f:
        f.close()

def teardown_cmeps_config():
    # Teardown
    os.remove(config_path)

def test_get_cur_expt_time(tmp_path):
    """ Test if get_cur_expt_time correctly parses the model date from the log file. """
    cmeps_config(1)

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)
        model = expt.models[0]

        log_path = os.path.join(model.work_path, "atmosphere", "log", "matmxx.pe00000.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "w") as f:
            f.write('{ "cur_exp-datetime" :  "1900-01-31T00:00:00" }')

        cur_expt_time = model.get_cur_expt_time()

        assert cur_expt_time == "1900-01-31T00:00:00"

    teardown_cmeps_config()

def test_get_cur_expt_time_no_log(tmp_path):
    """ Test if get_cur_expt_time returns None if log file is missing. """
    cmeps_config(1)

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)
        model = expt.models[0]

        log_path = os.path.join(model.work_path, "atmosphere", "log", "matmxx.pe00000.log")
        if os.path.exists(log_path):
            os.remove(log_path)

        with pytest.warns(
            UserWarning, 
            match=rf"Log file {log_path} does not exist or does not contain current model time."
        ):
            cur_expt_time = model.get_cur_expt_time()
        assert cur_expt_time is None

    teardown_cmeps_config()

def test_get_cur_expt_time_no_date(tmp_path):
    """ Test if get_cur_expt_time returns None if log file does not contain model date. """
    cmeps_config(1)

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)
        model = expt.models[0]

        log_path = os.path.join(model.work_path, "atmosphere", "log", "matmxx.pe00000.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "w") as f:
            f.write("This log file does not contain the model date.\n")

        with pytest.warns(
            UserWarning, 
            match=rf"Log file {log_path} does not exist or does not contain current model time."
        ):
            cur_expt_time = model.get_cur_expt_time()
        assert cur_expt_time is None

    teardown_cmeps_config()