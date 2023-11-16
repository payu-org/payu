import os
import copy
import shutil

import pytest

import payu
from payu.metadata import Metadata

from test.common import cd
from test.common import tmpdir, ctrldir, labdir, expt_archive_dir
from test.common import config as config_orig
from test.common import write_config
from test.common import make_all_files, make_random_file
from test.common import make_expt_archive_dir

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


@pytest.mark.parametrize(
    "uuid, experiment, previous_uuid, previous_metadata, expected_metadata",
    [
        (
            "A012345678910",
            "test_experiment-test_branch-A012345",
            None,
            (
                "contact: TestName",
                "email: test@email.com",
                "created: 2023-11-15",
                "description: |-",
                "  Test description etc",
                "  More description",
                "notes: |-",
                "  Test notes",
                "  More notes",
                "keywords:",
                "- test",
                "- testKeyword"
            ),
            (
                "contact: TestName",
                "email: test@email.com",
                "created: 2023-11-15",
                "description: |-",
                "  Test description etc",
                "  More description",
                "notes: |-",
                "  Test notes",
                "  More notes",
                "keywords:",
                "- test",
                "- testKeyword",
                "uuid: A012345678910",
                "experiment: test_experiment-test_branch-A012345\n"
            )

        )
    ]
)
def test_update_file(uuid,
                     experiment,
                     previous_uuid,
                     previous_metadata,
                     expected_metadata):
    # Create pre-existing metadata file
    metadata_path = ctrldir / 'metadata.yaml'
    if previous_metadata is not None:
        previous_metadata = '\n'.join(previous_metadata)
        metadata_path.write_text(previous_metadata)
    expected_metadata = '\n'.join(expected_metadata)

    with cd(ctrldir):
        lab = payu.laboratory.Laboratory(lab_path=str(labdir))
        metadata = Metadata(lab)

    metadata.uuid = uuid
    metadata.previous_uuid = previous_uuid
    metadata.experiment_name = experiment

    # Function to test
    metadata.update_file()

    assert metadata_path.exists and metadata_path.is_file
    assert metadata_path.read_text() == expected_metadata
