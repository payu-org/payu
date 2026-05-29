import pytest
import shlex
import sys
from unittest.mock import patch
import warnings
import logging

import payu
import payu.cli

from .common import cd, make_random_file, get_manifests
from .common import tmpdir, ctrldir, labdir, workdir
from .common import sweep_work, payu_init, payu_setup
from .common import config as config_orig
from .common import write_config
from .common import make_exe, make_inputs, make_restarts, make_all_files

verbose = True
ORIGINAL_WARNING = warnings.formatwarning

def test_parse_no_args(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["payu"])

    payu.cli.parse()
    assert "usage: payu [-h] [--version]" in capsys.readouterr().out

@pytest.fixture
def parser():
    return payu.cli.generate_parser()

def parse_args(parser, cmd):
    arguments = shlex.split(cmd.format(cmd=cmd))
    args = vars(parser.parse_args(arguments[1:]))
    run_cmd = args.pop("run_cmd")
    stacktrace = args.pop("stacktrace")
    log_level = args.pop("log_level")
    return run_cmd, args

def test_parse(parser):

    arguments = shlex.split("payu -h")

    with pytest.raises(SystemExit) as parse_error:
        parse_args(parser, "payu -h")


def test_parse_list(parser):

    run_cmd, args = parse_args(parser, 'payu list')

    assert run_cmd.__module__ == 'payu.subcommands.list_cmd'
    assert len(args) == 0


def test_parse_setup(parser):
    cmd = 'setup'
    run_cmd, args = parse_args(parser, f'payu {cmd}')

    assert run_cmd.__module__ == 'payu.subcommands.{cmd}_cmd'.format(cmd=cmd)

    assert args.pop('model_type') is None
    assert args.pop('config_path') is None
    assert args.pop('lab_path') is None
    assert args.pop('reproduce') is False
    assert args.pop('force') is False
    assert args.pop('metadata_off') is False

    assert len(args) == 0

    # Test long options
    long_cmd = (
                    f"payu {cmd} "
                    "--model mom "
                    "--config path/to/config.yaml "
                    "--laboratory path/to/lab "
                    "--force "
                    "--reproduce "
                    "--metadata-off"
                )

    run_cmd, args = parse_args(parser, long_cmd)

    assert run_cmd.__module__ == 'payu.subcommands.{cmd}_cmd'.format(cmd=cmd)

    assert args.pop('model_type') == 'mom'
    assert args.pop('config_path') == 'path/to/config.yaml'
    assert args.pop('lab_path') == 'path/to/lab'
    assert args.pop('reproduce') is True
    assert args.pop('force') is True
    assert args.pop('metadata_off') is True

    assert len(args) == 0

    # Test short options
    short_cmd = (
                    f"payu {cmd} "
                    "-m mom "
                    "-c path/to/config.yaml "
                    "-l path/to/lab "
                    "-f "
                    "-r "
                    "-M")

    run_cmd, args = parse_args(parser, short_cmd)
    assert run_cmd.__module__ == 'payu.subcommands.{cmd}_cmd'.format(cmd=cmd)

    assert args.pop('model_type') == 'mom'
    assert args.pop('config_path') == 'path/to/config.yaml'
    assert args.pop('lab_path') == 'path/to/lab'
    assert args.pop('reproduce') is True
    assert args.pop('force') is True
    assert args.pop('metadata_off') is True

    assert len(args) == 0


def test_parse_run(parser):

    cmd = 'run'

    run_cmd, args = parse_args(parser, f'payu {cmd}')

    assert run_cmd.__module__ == 'payu.subcommands.{cmd}_cmd'.format(cmd=cmd)

    assert args.pop('model_type') is None
    assert args.pop('config_path') is None
    assert args.pop('lab_path') is None
    assert args.pop('reproduce') is False
    assert args.pop('force') is False
    assert args.pop('init_run') is None
    assert args.pop('n_runs') is None
    assert args.pop('force_prune_restarts') is False

    assert len(args) == 0

    # Test long options
    long_cmd = (
            f"payu {cmd} "
            "--model mom "
            "--config path/to/config.yaml "
            "--laboratory path/to/lab "
            "--force "
            "--initial 99 "
            "--nruns 999 "
            "--reproduce "
            "--force-prune-restarts")

    run_cmd, args = parse_args(parser, long_cmd)

    assert run_cmd.__module__ == 'payu.subcommands.{cmd}_cmd'.format(cmd=cmd)

    assert args.pop('model_type') == 'mom'
    assert args.pop('config_path') == 'path/to/config.yaml'
    assert args.pop('lab_path') == 'path/to/lab'
    assert args.pop('reproduce') is True
    assert args.pop('force') is True
    assert args.pop('init_run') == '99'
    assert args.pop('n_runs') == '999'
    assert args.pop('force_prune_restarts') is True

    assert len(args) == 0

    # Test short options
    short_cmd = (
                f"payu {cmd} "
                "-m mom "
                "-c path/to/config.yaml "
                "-l path/to/lab "
                "-f "
                "-i 99 "
                "-n 999 "
                "-r "
                "-F"
            )
    run_cmd, args = parse_args(parser, short_cmd)

    assert run_cmd.__module__ == 'payu.subcommands.{cmd}_cmd'.format(cmd=cmd)

    assert args.pop('model_type') == 'mom'
    assert args.pop('config_path') == 'path/to/config.yaml'
    assert args.pop('lab_path') == 'path/to/lab'
    assert args.pop('reproduce') is True
    assert args.pop('force') is True
    assert args.pop('init_run') == '99'
    assert args.pop('n_runs') == '999'
    assert args.pop('force_prune_restarts') is True

    assert len(args) == 0


def test_parse_sweep(parser):

    cmd = 'sweep'
    run_cmd, args = parse_args(parser, f'payu {cmd}')

    assert run_cmd.__module__ == 'payu.subcommands.{cmd}_cmd'.format(cmd=cmd)

    assert args.pop('model_type') is None
    assert args.pop('config_path') is None
    assert args.pop('lab_path') is None
    assert args.pop('hard_sweep') is False
    assert args.pop('metadata_off') is False

    assert len(args) == 0

    # Test long options
    long_cmd = (
        f"payu {cmd} "
        "--model mom "
        "--config path/to/config.yaml "
        "--laboratory path/to/lab "
        "--hard "
        "--metadata-off"
    )

    run_cmd, args = parse_args(parser, long_cmd)

    assert run_cmd.__module__ == 'payu.subcommands.{cmd}_cmd'.format(cmd=cmd)

    assert args.pop('model_type') == 'mom'
    assert args.pop('config_path') == 'path/to/config.yaml'
    assert args.pop('lab_path') == 'path/to/lab'
    assert args.pop('hard_sweep') is True
    assert args.pop('metadata_off') is True

    assert len(args) == 0

    # Test short options
    short_cmd = (
        f"payu {cmd} "
        "-m mom "
        "-c path/to/config.yaml "
        "-l path/to/lab "
        "-M"
    )
    run_cmd, args = parse_args(parser, short_cmd)

    assert run_cmd.__module__ == 'payu.subcommands.{cmd}_cmd'.format(cmd=cmd)

    assert args.pop('model_type') == 'mom'
    assert args.pop('config_path') == 'path/to/config.yaml'
    assert args.pop('lab_path') == 'path/to/lab'
    assert args.pop('hard_sweep') is False
    assert args.pop('metadata_off') is True

    assert len(args) == 0


def test_parse_collate(parser):

    cmd = 'collate'

    run_cmd, args = parse_args(parser, f'payu {cmd}')

    assert run_cmd.__module__ == 'payu.subcommands.{cmd}_cmd'.format(cmd=cmd)

    assert args.pop('model_type') is None
    assert args.pop('config_path') is None
    assert args.pop('lab_path') is None
    assert args.pop('init_run') is None
    assert args.pop('dir_path') is None

    assert len(args) == 0

    # Test long options
    long_cmd = (
        f"payu {cmd} "
        "--model mom "
        "--config path/to/config.yaml "
        "--laboratory path/to/lab "
        "--initial 99 "
        "--directory path/to/files "
    )

    run_cmd, args = parse_args(parser, long_cmd)

    assert run_cmd.__module__ == 'payu.subcommands.{cmd}_cmd'.format(cmd=cmd)

    assert args.pop('model_type') == 'mom'
    assert args.pop('config_path') == 'path/to/config.yaml'
    assert args.pop('lab_path') == 'path/to/lab'
    assert args.pop('init_run') == '99'
    assert args.pop('dir_path') == 'path/to/files'

    assert len(args) == 0

    # Test short options
    short_cmd = (
        f"payu {cmd} "
        "-m mom "
        "-c path/to/config.yaml "
        "-l path/to/lab "
        "-i 99 "
        "-d path/to/files "
    )
    run_cmd, args = parse_args(parser, short_cmd)

    assert run_cmd.__module__ == 'payu.subcommands.{cmd}_cmd'.format(cmd=cmd)

    assert args.pop('model_type') == 'mom'
    assert args.pop('config_path') == 'path/to/config.yaml'
    assert args.pop('lab_path') == 'path/to/lab'
    assert args.pop('init_run') == '99'
    assert args.pop('dir_path') == 'path/to/files'

    assert len(args) == 0


def test_parse_init(parser):

    cmd = 'init'

    run_cmd, args = parse_args(parser, f'payu {cmd}')

    assert run_cmd.__module__ == 'payu.subcommands.{cmd}_cmd'.format(cmd=cmd)

    assert args.pop('model_type') is None
    assert args.pop('config_path') is None
    assert args.pop('lab_path') is None

    assert len(args) == 0

    # Test long options
    long_cmd = (
        f"payu {cmd} "
        "--model mom "
        "--config path/to/config.yaml "
        "--laboratory path/to/lab "
    )
    run_cmd, args = parse_args(parser, long_cmd)

    assert run_cmd.__module__ == 'payu.subcommands.{cmd}_cmd'.format(cmd=cmd)

    assert args.pop('model_type') == 'mom'
    assert args.pop('config_path') == 'path/to/config.yaml'
    assert args.pop('lab_path') == 'path/to/lab'

    assert len(args) == 0

    # Test short options
    short_cmd = (
        f"payu {cmd} "
        "-m mom "
        "-c path/to/config.yaml "
        "-l path/to/lab "
    )
    run_cmd, args = parse_args(parser, short_cmd)

    assert run_cmd.__module__ == 'payu.subcommands.{cmd}_cmd'.format(cmd=cmd)

    assert args.pop('model_type') == 'mom'
    assert args.pop('config_path') == 'path/to/config.yaml'
    assert args.pop('lab_path') == 'path/to/lab'

    assert len(args) == 0

def test_parse_clone(parser):
    cmd = 'clone'
    short_cmd = (
        f"payu {cmd} "
        "test_repo "
        "local_dir "
    )
    run_cmd, args = parse_args(parser, short_cmd)

    assert run_cmd.__module__ == 'payu.subcommands.{cmd}_cmd'.format(cmd=cmd)

    assert args.pop('repository') == 'test_repo'
    assert args.pop('local_directory') == 'local_dir'


@pytest.mark.parametrize(
    "stacktrace_flag, stacktrace_env, expected_stacktrace", 
    [   
        # Running `payu-cmd`` with no stacktrace flag
        (False, None, False),

        # Running `payu cmd` to submit PBS job with no stacktrace flag
        (False, False, False),

        # Running `payu-cmd`` with --stacktrace flag
        (True, None, True),
        (True, False, True),

        # Running `payu cmd` to submit PBS job with --stacktrace flag passed through environment variable
        (False, True, True),
    ]
)
def test_set_stacktrace_runscript(stacktrace_flag, stacktrace_env, expected_stacktrace, monkeypatch):
    """Test that set_stacktrace_runscript configure the stacktrace settings for the runscript."""
    monkeypatch.setattr(warnings, "formatwarning", ORIGINAL_WARNING)
    if stacktrace_env is None:
        monkeypatch.delenv("PAYU_STACKTRACE", raising=False)
    else:
        monkeypatch.setenv("PAYU_STACKTRACE", stacktrace_env)

    with pytest.warns(UserWarning) as caught:
        payu.cli.set_stacktrace_runscript(stacktrace_flag)
        warnings.warn("Test Warning")

    w = caught[0]
    formatted = warnings.formatwarning(
        w.message, w.category, w.filename, w.lineno, w.line
    )

    if expected_stacktrace:
        assert "Test Warning" in formatted
        assert "UserWarning" in formatted
        assert str(w.filename) in formatted
        assert str(w.lineno) in formatted
    else:
        assert formatted == "Test Warning"


@pytest.mark.parametrize(
    "log_level_arg, log_level_env, expected_log_level",
    [
        # Running `payu-cmd` with no log level flag 
        ('INFO', None, 'INFO'),

        # Running `payu cmd` with no log level flag 
        ('INFO', 'INFO', 'INFO'),

        # Running `payu-cmd` with --log-level=DEBUG flag
        ('DEBUG', None, 'DEBUG'),

        # Running `payu cmd` with --log-level=DEBUG flag passed through environment variable
        ('INFO', 'DEBUG', 'DEBUG'),

        # Confirm that CLI > Environment variable for log level
        ('DEBUG', 'INFO', 'DEBUG'),
    ]
)
def test_set_logger_runscript(log_level_arg, log_level_env, expected_log_level, monkeypatch):
    """Test that set_logger_runscript configure the logging settings for the runscript."""
    if log_level_env is None:
        monkeypatch.delenv("PAYU_LOG_LEVEL", raising=False)
    else:
        monkeypatch.setenv("PAYU_LOG_LEVEL", log_level_env)
    payu.cli.set_logger_runscript(log_level_arg)
    logger = payu.cli.logging.getLogger()
    print(logger.level)
    assert logging.getLevelName(logger.level) == expected_log_level
     

def test_parse_arg_count(capsys, monkeypatch):
    """Test that the parser correctly excludes --stacktrace when counting arguments."""
    # confirm print help is triggered when only --stacktrace is provided
    monkeypatch.setattr(sys, "argv", ["payu --stacktrace"])
    payu.cli.parse()
    assert "usage: payu --stacktrace [-h] [--version]" in capsys.readouterr().out

    # confirm print help is not triggered when a subcommand is provided, even with --stacktrace
    monkeypatch.setattr(sys, "argv", ["payu", "list", "--stacktrace"])
    monkeypatch.setattr("payu.subcommands.list_cmd.runcmd", lambda *args, **kwargs: None)
    payu.cli.parse()
    assert "usage: payu" not in capsys.readouterr().out
    assert "[-h] [--version]" not in capsys.readouterr().out
