import f90nml
import os
import pytest
import shutil

import payu

from test.common import cd
from test.common import tmpdir, ctrldir, labdir, expt_workdir, ctrldir_basename
from test.common import archive_dir
from test.common import write_config, write_metadata
from test.common import make_random_file, make_inputs, make_exe

verbose = True


def setup_module(module):
    """
    Put any test-wide setup code in here, e.g. creating test files
    """
    if verbose:
        print("setup_module      module:%s" % module.__name__)

    # Should be taken care of by teardown, in case remnants lying around
    try:
        shutil.rmtree(tmpdir)
    except FileNotFoundError:
        pass

    try:
        tmpdir.mkdir()
        labdir.mkdir()
        ctrldir.mkdir()
        expt_workdir.mkdir()
        archive_dir.mkdir()
    except Exception as e:
        print(e)

    config = {
        'laboratory': 'lab',
        'jobname': 'testrun',
        'model': 'staged_cable',
        'exe': 'cable',
        'experiment': ctrldir_basename,
        'metadata': {
            'enable': False
        }
    }
    write_config(config)

    stage1dir = ctrldir / 'stage_1'
    stage1dir.mkdir()
    stage2dir = ctrldir / 'stage_2'
    stage2dir.mkdir()

    # Build a stage config for testing
    stage_config = {
        'stage_1': {'count': 1},
        'stage_2': {'count': 1},
        'multistep_stage_1': {
            'stage_3': {'count': 3},
            'stage_4': {'count': 1},
        },
        'multistep_stage_2': {
            'stage_5': {'count': 1},
            'stage_6': {'count': 2},
        },
        'stage_7': {'count': 1}
    }

    write_config(stage_config, ctrldir / 'stage_config.yaml')

    # Prepare a master namelist and a stage 1 namelist
    master_nml = {
        'cablenml': {
            'option1': 1,
            'struct1': {
                'option2': 2,
                'option3': 3,
            },
            'option4': 4
        }
    }

    with open(ctrldir / 'cable.nml', 'w') as master_nml_f:
        f90nml.write(master_nml, master_nml_f)

    patch_nml = {
        'cablenml': {
            'option1': 10,
            'struct1': {
                'option2': 20,
                'option5': 50
            },
            'option6': 60
        }
    }

    with open(ctrldir / 'stage_1/cable.nml', 'w') as patch_nml_f:
        f90nml.write(patch_nml, patch_nml_f)


def teardown_module(module):
    """
    Put any test-wide teardown code in here, e.g. removing test outputs
    """
    if verbose:
        print("teardown_module   module:%s" % module.__name__)

    try:
        # shutil.rmtree(tmpdir)
        print('removing tmp')
    except Exception as e:
        print(e)


def test_staged_cable():
    """
    Test the preparing and archiving of a cable_stage.
    """

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        expt = payu.experiment.Experiment(lab, reproduce=False)
        model = expt.models[0]

    # Since we've called the initialiser, we should be able to inspect the
    # stages immediately (through the configuration log)
    expected_queued_stages = [
        'stage_1',
        'stage_2',
        'stage_3',
        'stage_4',
        'stage_3',
        'stage_3',
        'stage_5',
        'stage_6',
        'stage_6',
        'stage_7']
    assert model.configuration_log['queued_stages'] == expected_queued_stages

    # Now prepare for a stage- should see changes in the configuration log
    # and the patched namelist in the workdir
    model.setup()
    expected_current_stage = expected_queued_stages.pop(0)
    assert model.configuration_log['current_stage'] == expected_current_stage
    assert model.configuration_log['queued_stages'] == expected_queued_stages

    # Now check the namelist
    expected_namelist = {
        'cablenml': {
            'option1': 10,
            'struct1': {
                'option2': 20,
                'option3': 3,
                'option5': 50
            },
            'option4': 4,
            'option6': 60
        }
    }

    with open(expt_workdir / 'cable.nml') as stage_nml_f:
        stage_nml = f90nml.read(stage_nml_f)

    assert stage_nml == expected_namelist

    # Archive the stage and make sure the configuration log is correct
    model.archive()
    expected_comp_stages = [expected_current_stage]
    expected_current_stage = ''
    assert model.configuration_log['completed_stages'] == expected_comp_stages
    assert model.configuration_log['current_stage'] == expected_current_stage

    # Test the acquiring of restart files
    # First, perform setup() and archive to mimic the effect of running
    # 2 stages on the configuration log.
    model.setup()
    model.archive()

    # When running an experiment, we should have archive/output00{0, 1}/restart
    outputdir = ctrldir / 'archive' / 'restart000' / 'restart'
    outputdir.mkdir(parents=True)
    with open(outputdir / 'rst1.txt', 'w') as rstfile:
        rstfile.write("This is rst1.txt in restart000.")

    with open(outputdir / 'rst2.txt', 'w') as rstfile:
        rstfile.write("This is rst2.txt in restart000.")

    outputdir = ctrldir / 'archive' / 'restart001' / 'restart'
    outputdir.mkdir(parents=True)
    with open(outputdir / 'rst1.txt', 'w') as rstfile:
        rstfile.write('This is rst1.txt in restart001.')

    rstfiles = model.get_prior_restart_files()
    expected_restart_files = [
        str(ctrldir / 'archive' / 'restart001' / 'restart' / 'rst1.txt'),
        str(ctrldir / 'archive' / 'restart000' / 'restart' / 'rst2.txt')
    ]

    assert rstfiles == expected_restart_files
