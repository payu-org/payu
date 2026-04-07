import pytest
from unittest.mock import patch, MagicMock

import payu
from payu.subcommands import support_cmd

expect_output_list = [
    "Payu Version",
    "Payu Path",
    "Python Version",
    "Python Path",
    "Machine Info",]

mock_machine_info = MagicMock(return_value="Rocky Linux-8.10-x86_64")
mock_os_release = {
        'NAME': 'Rocky Linux',
        'VERSION_ID': '8.10'
    }

mock_payu_env_vars = {'PAYU_PATH': '/path/to/payu'}
mock_environ = {
    'PYTHONPATH': '/path/to/python',
    'LOADEDMODULES': 'module1 module2'
}

def test_support_cmd(capsys):
    """Test the support command runs as expected"""
    with patch('payu.subcommands.support_cmd.get_machine_info', mock_machine_info),\
        patch('payu.subcommands.support_cmd.cli.set_env_vars', return_value=mock_payu_env_vars),\
        patch.dict('os.environ', mock_environ):
        support_cmd.runcmd()
        captured = capsys.readouterr()
        for expected in expect_output_list:
            assert expected in captured.out
        assert "Python Path from Environment" in captured.out
        assert "LOADEDMODULES" in captured.out


def test_support_cmd_empty_env(capsys):
    """Test the support command with empty environment variables"""
    with patch('payu.subcommands.support_cmd.get_machine_info', mock_machine_info),\
        patch('payu.subcommands.support_cmd.cli.set_env_vars', return_value={}),\
        patch.dict('os.environ', {}, clear=True):
        support_cmd.runcmd()
        captured = capsys.readouterr()
        for expected in expect_output_list:
            assert expected in captured.out
        assert "Python Path from Environment" not in captured.out
        assert "LOADEDMODULES" not in captured.out


def test_get_machine_info():
    """Test get_machine_info returns expected format"""
    with patch('platform.freedesktop_os_release', MagicMock(return_value=mock_os_release)),\
        patch('platform.machine', MagicMock(return_value="x86_64")):
        machine_info = support_cmd.get_machine_info()
        assert machine_info == "Rocky Linux-8.10-x86_64"
