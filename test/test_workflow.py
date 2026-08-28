import copy
from unittest.mock import Mock

import pytest

from payu.workflow import Workflow

from .common import config as config_orig

@pytest.mark.parametrize(
    "collate_value, sync_value, postscript, skip_step, expect_workflow", 
    [   
        # collate/postscript/sync enabled
        ({"enable": True}, {"enable": True}, "-v ${PBS_NCI_STORAGE} postscript.sh", 
         None, {"collate": None, "postscript": None, "sync": None}),

        # Manually disable collate and sync, postscript enabled
        ({"enable": False}, {"enable": False}, "-v ${PBS_NCI_STORAGE} postscript.sh",
         None, {"postscript": None}),

         # By default, collate is enabled, postscript is disabled, sync is disabled
        (None, None, None,
         None, {"collate": None}),

        # A case that no follow-up jobs are enabled
        ({"enable": False}, {"enable": False}, "",
         None, {}),

        # collate/postscript/sync enabled, but collate is skipped (e.g., workflow called by payu collate)
        ({"enable": True}, {"enable": True}, "-v ${PBS_NCI_STORAGE} postscript.sh", 
         "collate", {"postscript": None, "sync": None}),
    ]
)
def test_workflow_read_config(collate_value, sync_value, postscript, skip_step, expect_workflow):
    """Test the read_config class method include correct stage based on the config.yaml."""
    config = copy.deepcopy(config_orig)

    # Update the config based on the test
    for key, value in {"collate": collate_value, "postscript": postscript, "sync": sync_value}.items():
        if value is not None:
            config[key] = value
        else:
            config.pop(key, None)

    # Initialize the Workflow class and build the workflow
    workflow = Workflow.read_config(config, run_number=1, skip_step=skip_step)

    # Assert that the workflow_steps dictionary are as expected
    assert workflow.workflow_steps == expect_workflow


def test_submit_workflow(monkeypatch):
    """ Test that submit_workflow calls the corresponding subcommand functions
    and updates the workflow_steps dictionary with job IDs. """
    # Create mock functions
    mock_submit_collate = Mock(return_value="collate_job_id")
    mock_submit_postscript = Mock(return_value="postscript_job_id")
    mock_submit_sync = Mock(return_value="sync_job_id")

    # Initialise the workflow class and change the workflow_steps
    workflow = Workflow.read_config(config_orig, run_number=1)
    workflow.workflow_steps = {"collate": None, "postscript": None, "sync": None}

    # When workflow import subcommands, it returns the mock function instead of the real ones
    monkeypatch.setattr(
        workflow,
        "import_subcommands",
        lambda: {
            "collate": mock_submit_collate,
            "postscript": mock_submit_postscript,
            "sync": mock_submit_sync,
        },
    )

    # Call the submit_workflow and check the new workflow_steps dictionary
    assert workflow.submit_workflow("run_job_id") == {
        "collate": "collate_job_id",
        "postscript": "postscript_job_id",
        "sync": "sync_job_id",
    }

    # Assert the mock functions were called with correct dependencies
    mock_submit_collate.assert_called_once_with(1, "run_job_id", config_orig)
    mock_submit_postscript.assert_called_once_with(1, "collate_job_id", config_orig)
    mock_submit_sync.assert_called_once_with(1, "postscript_job_id", config_orig)