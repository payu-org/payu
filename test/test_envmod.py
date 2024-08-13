import pytest
from unittest.mock import patch

from payu.envmod import check_modulefile


@patch('payu.envmod.run_module_cmd')
def test_check_modulefile_unique(mock_module_cmd):
    # Mock module avail command
    mock_module_cmd.return_value.stderr = """/path/to/modulefiles:
test-module/1.0.0
"""
    # Test runs without an error
    check_modulefile('test-module/1.0.0')


@patch('payu.envmod.run_module_cmd')
def test_check_modulefile_without_version(mock_module_cmd):
    # Mock module avail command
    mock_module_cmd.return_value.stderr = """/path/to/modulefiles:
test-module/1.0.0
test-module/2.0.0
"""

    # Expect an error raised
    with pytest.raises(ValueError) as exc_info:
        check_modulefile('test-module')
        exc_info.value.startswith(
            "There are multiple modules available for test-module"
        )


@patch('payu.envmod.run_module_cmd')
def test_check_modulefile_exact_match(mock_module_cmd):
    # Mock module avail command
    mock_module_cmd.return_value.stderr = """/path/to/modulefiles:
test-module/1.0.0
test-module/1.0.0-debug
"""

    # Test runs without an error
    check_modulefile('test-module/1.0.0')


@patch('payu.envmod.run_module_cmd')
def test_check_modulefile_multiple_modules(mock_module_cmd):
    # Mock module avail command
    mock_module_cmd.return_value.stderr = """/path/to/modulefiles:
test-module/1.0.0
/another/module/path:
test-module/1.0.0
"""

    # Expect an error raised
    with pytest.raises(ValueError) as exc_info:
        check_modulefile('test-module/1.0.0')
        exc_info.value.startswith(
            "There are multiple modules available for test-module"
        )


@patch('payu.envmod.run_module_cmd')
def test_check_modulefile_no_modules_found(mock_module_cmd):
    # Mock module avail command
    mock_module_cmd.return_value.stderr = ""

    # Expect an error raised
    with pytest.raises(ValueError) as exc_info:
        check_modulefile('test-module/1.0.0')
        exc_info.value.startswith("Module is not found: test-module")
