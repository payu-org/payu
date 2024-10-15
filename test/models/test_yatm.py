
from unittest.mock import Mock

import payu.experiment
import payu.models

def test_get_prior_restart_files(capsys, tmpdir):
    with capsys.disabled():
        expt = Mock(spec=payu.experiment.Experiment)
        model_config = {'model': 'yatm'}
        model = payu.models.Yatm(expt, 'atmosphere', model_config)
        model.prior_restart_path = str(tmpdir / 'unexistent_dir')

    restart_files = model.get_prior_restart_files()

    # Check nothing written to standard output
    captured = capsys.readouterr()
    assert captured.out == ''
    assert captured.err == ''

    assert restart_files == []
