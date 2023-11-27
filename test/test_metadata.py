import copy
import shutil

import pytest
from unittest.mock import patch

import payu
from payu.metadata import Metadata

from test.common import cd
from test.common import tmpdir, ctrldir, labdir
from test.common import config as config_orig
from test.common import write_config
from test.common import make_all_files

verbose = True

# Global config
config = copy.deepcopy(config_orig)


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
        make_all_files()
    except Exception as e:
        print(e)

    write_config(config)


def teardown_module(module):
    """
    Put any test-wide teardown code in here, e.g. removing test outputs
    """
    if verbose:
        print("teardown_module   module:%s" % module.__name__)

    try:
        shutil.rmtree(tmpdir)
        print('removing tmp')
    except Exception as e:
        print(e)


def mocked_get_git_user_info(repo_path, config_key, example_value):
    if config_key == 'name':
        return 'mockUser'
    elif config_key == 'email':
        return 'mock@email.com'
    else:
        return None


@pytest.mark.parametrize(
    "uuid, experiment, previous_metadata, expected_metadata",
    [
        (
            "A012345678910",
            "test_experiment-test_branch-A012345",
            """contact: TestUser
email: Test@email.com
description: |-
  Test description etc
  More description
keywords:
- test
- testKeyword
# Test Comment
uuid: A012345678910
experiment: test_experiment-test_branch-A012345
""",
            """contact: TestUser
email: Test@email.com
description: |-
  Test description etc
  More description
keywords:
- test
- testKeyword
# Test Comment
uuid: A012345678910
experiment: test_experiment-test_branch-A012345
"""
        ),
        (
            "A012345678910",
            "test_experiment-test_branch-A012345",
            None,
            """uuid: A012345678910
experiment: test_experiment-test_branch-A012345
contact: mockUser
email: mock@email.com
"""
        ),
        (
            "NewUuid",
            "NewExperimentName",
            """uuid: PreviousUuid
experiment: PreviousExperimentName
contact: Add your name here
email: Add your email address here
""",
            """uuid: NewUuid
experiment: NewExperimentName
contact: mockUser
email: mock@email.com
previous_uuid: PreviousUuid
"""
        ),
        (
            "NewUuid",
            "NewExperimentName",
            """
contact: AdD Your nAme hEre
email: #
""",
            """contact: mockUser
email: mock@email.com #
uuid: NewUuid
experiment: NewExperimentName
"""
        )
    ]
)
def test_update_file(uuid,
                     experiment,
                     previous_metadata,
                     expected_metadata):
    # Create pre-existing metadata file
    metadata_path = ctrldir / 'metadata.yaml'
    if previous_metadata is not None:
        metadata_path.write_text(previous_metadata)

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        metadata = Metadata(lab)

    metadata.uuid = uuid
    metadata.experiment_name = experiment

    # Function to test
    with patch('payu.metadata.get_git_user_info',
               side_effect=mocked_get_git_user_info):
        metadata.update_file()

    assert metadata_path.exists and metadata_path.is_file
    assert metadata_path.read_text() == expected_metadata

    # Remove metadata file
    metadata_path.unlink()
