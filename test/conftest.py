import shutil
import pytest
from test.common import cd, tmpdir, ctrldir, labdir, workdir, make_inputs, make_exe, expt_workdir

@pytest.fixture()
def setup_test_dir():
    """
    A fixture that setup the test directories and files.
    Yield to run the tests, and then clean up when exiting the tests.
    """
    try:
        shutil.rmtree(tmpdir)
    except FileNotFoundError:
        pass

    try:
        tmpdir.mkdir()
        labdir.mkdir()
        ctrldir.mkdir()
        workdir.mkdir()
        make_inputs()
        make_exe()
    except Exception as e:
        print(e)

    # Run test
    yield

    # Teardown the tmp directory after tests have run
    try:
        shutil.rmtree(tmpdir)
        print('[Cleanup] removing tmp directory')
    except Exception as e:
        print(e)

@pytest.fixture()
def empty_workdir(setup_test_dir):
    """
    A fixture that set up a clean work directory and symlink from
    the control directory.
    """
    expt_workdir.mkdir(parents=True)
    # Symlink must exist for setup to use correct locations
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.symlink_to(expt_workdir)

    yield expt_workdir
    workdir.unlink()