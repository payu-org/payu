import os
import shutil
import tempfile

import pytest

import payu.models.cable as cable

from test.common import make_random_file


class TestGetForcingPath:
    """Tests for `payu.models.cable._get_forcing_path()`."""

    @pytest.fixture()
    def input_dir(self):
        """Create a temporary input directory and return its path."""
        _input_dir = tempfile.mkdtemp(prefix="payu_test_get_forcing_path")
        yield _input_dir
        shutil.rmtree(_input_dir)

    @pytest.fixture(autouse=True)
    def _make_forcing_inputs(self, input_dir):
        """Create forcing inputs from 1900 to 1903."""
        for year in [1900, 1901, 1903]:
            make_random_file(os.path.join(input_dir, f"crujra_LWdown_{year}.nc"))

    def test_get_forcing_path(self, input_dir):
        """Success case: test correct path can be inferred."""
        assert cable._get_forcing_path("LWdown", 1900, input_dir) == os.path.join(
            input_dir, "crujra_LWdown_1900.nc"
        )

    def test_year_offset(self, input_dir):
        """Success case: test correct path can be inferred with offset."""
        assert cable._get_forcing_path(
            "LWdown", 2000, input_dir, offset=[2000, 1900]
        ) == os.path.join(input_dir, "crujra_LWdown_1900.nc")

    def test_year_repeat(self, input_dir):
        """Success case: test correct path can be inferred with repeat."""
        assert cable._get_forcing_path(
            "LWdown", 1904, input_dir, repeat=[1900, 1903]
        ) == os.path.join(input_dir, "crujra_LWdown_1900.nc")

    def test_file_not_found_exception(self, input_dir):
        """Failure case: test exception is raised if path cannot be inferred."""
        with pytest.raises(
            FileNotFoundError,
            match="Unable to infer met forcing path for variable LWdown for year 1904.",
        ):
            _ = cable._get_forcing_path("LWdown", 1904, input_dir)
