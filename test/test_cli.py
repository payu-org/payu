import pdb
import pytest
import shlex

import payu
import payu.cli

from .common import cd, make_random_file, get_manifests
from .common import tmpdir, ctrldir, labdir, workdir
from .common import sweep_work, payu_init, payu_setup
from .common import config as config_orig
from .common import write_config
from .common import make_exe, make_inputs, make_restarts, make_all_files

verbose = True

parser = None


def test_generate_parser():

    global parser

    parser = payu.cli.generate_parser()


def test_parse():

    arguments = shlex.split("payu -h")

    with pytest.raises(SystemExit) as parse_error:
        parser.parse_args(arguments[1:])


def test_parse_list():

    arguments = shlex.split("payu list")

    args = vars(parser.parse_args(arguments[1:]))

    run_cmd = args.pop('run_cmd')

    assert run_cmd.__module__ == 'payu.subcommands.list_cmd'
    assert len(args) == 0


def test_parse_setup():

    cmd = 'setup'

    arguments = shlex.split('payu {cmd}'.format(cmd=cmd))

    args = vars(parser.parse_args(arguments[1:]))

    run_cmd = args.pop('run_cmd')

    assert run_cmd.__module__ == 'payu.subcommands.{cmd}_cmd'.format(cmd=cmd)

    assert args.pop('model_type') is None
    assert args.pop('config_path') is None
    assert args.pop('lab_path') is None
    assert args.pop('force_archive') is False
    assert args.pop('reproduce') is False
    assert args.pop('force') is False

    assert len(args) == 0

    # Test long options
    arguments = shlex.split('payu {cmd} '
                            '--model mom '
                            '--config path/to/config.yaml '
                            '--laboratory path/to/lab '
                            '--archive '
                            '--force '
                            '--reproduce'.format(cmd=cmd))

    args = vars(parser.parse_args(arguments[1:]))

    run_cmd = args.pop('run_cmd')

    assert run_cmd.__module__ == 'payu.subcommands.{cmd}_cmd'.format(cmd=cmd)

    assert args.pop('model_type') == 'mom'
    assert args.pop('config_path') == 'path/to/config.yaml'
    assert args.pop('lab_path') == 'path/to/lab'
    assert args.pop('force_archive') is True
    assert args.pop('reproduce') is True
    assert args.pop('force') is True

    assert len(args) == 0

    # Test short options
    arguments = shlex.split('payu {cmd} '
                            '-m mom '
                            '-c path/to/config.yaml '
                            '-l path/to/lab '
                            '-f '
                            '-r'.format(cmd=cmd))

    args = vars(parser.parse_args(arguments[1:]))

    run_cmd = args.pop('run_cmd')

    assert run_cmd.__module__ == 'payu.subcommands.{cmd}_cmd'.format(cmd=cmd)

    assert args.pop('model_type') == 'mom'
    assert args.pop('config_path') == 'path/to/config.yaml'
    assert args.pop('lab_path') == 'path/to/lab'
    assert args.pop('force_archive') is False
    assert args.pop('reproduce') is True
    assert args.pop('force') is True

    assert len(args) == 0


def test_parse_run():

    cmd = 'run'

    arguments = shlex.split('payu {cmd}'.format(cmd=cmd))

    args = vars(parser.parse_args(arguments[1:]))

    run_cmd = args.pop('run_cmd')

    assert run_cmd.__module__ == 'payu.subcommands.{cmd}_cmd'.format(cmd=cmd)

    assert args.pop('model_type') is None
    assert args.pop('config_path') is None
    assert args.pop('lab_path') is None
    assert args.pop('reproduce') is False
    assert args.pop('force') is False
    assert args.pop('init_run') is None
    assert args.pop('n_runs') is None

    assert len(args) == 0

    # Test long options
    arguments = shlex.split('payu {cmd} '
                            '--model mom '
                            '--config path/to/config.yaml '
                            '--laboratory path/to/lab '
                            '--force '
                            '--initial 99 '
                            '--nruns 999 '
                            '--reproduce'.format(cmd=cmd))

    args = vars(parser.parse_args(arguments[1:]))

    run_cmd = args.pop('run_cmd')

    assert run_cmd.__module__ == 'payu.subcommands.{cmd}_cmd'.format(cmd=cmd)

    assert args.pop('model_type') == 'mom'
    assert args.pop('config_path') == 'path/to/config.yaml'
    assert args.pop('lab_path') == 'path/to/lab'
    assert args.pop('reproduce') is True
    assert args.pop('force') is True
    assert args.pop('init_run') == '99'
    assert args.pop('n_runs') == '999'

    assert len(args) == 0

    # Test short options
    arguments = shlex.split('payu {cmd} '
                            '-m mom '
                            '-c path/to/config.yaml '
                            '-l path/to/lab '
                            '-f '
                            '-i 99 '
                            '-n 999 '
                            '-r'.format(cmd=cmd))

    args = vars(parser.parse_args(arguments[1:]))

    run_cmd = args.pop('run_cmd')

    assert run_cmd.__module__ == 'payu.subcommands.{cmd}_cmd'.format(cmd=cmd)

    assert args.pop('model_type') == 'mom'
    assert args.pop('config_path') == 'path/to/config.yaml'
    assert args.pop('lab_path') == 'path/to/lab'
    assert args.pop('reproduce') is True
    assert args.pop('force') is True
    assert args.pop('init_run') == '99'
    assert args.pop('n_runs') == '999'

    assert len(args) == 0


def test_parse_sweep():

    cmd = 'sweep'

    arguments = shlex.split('payu {cmd}'.format(cmd=cmd))

    args = vars(parser.parse_args(arguments[1:]))

    run_cmd = args.pop('run_cmd')

    assert run_cmd.__module__ == 'payu.subcommands.{cmd}_cmd'.format(cmd=cmd)

    assert args.pop('model_type') is None
    assert args.pop('config_path') is None
    assert args.pop('lab_path') is None
    assert args.pop('hard_sweep') is False

    assert len(args) == 0

    # Test long options
    arguments = shlex.split('payu {cmd} '
                            '--model mom '
                            '--config path/to/config.yaml '
                            '--laboratory path/to/lab '
                            '--hard'.format(cmd=cmd))

    args = vars(parser.parse_args(arguments[1:]))

    run_cmd = args.pop('run_cmd')

    assert run_cmd.__module__ == 'payu.subcommands.{cmd}_cmd'.format(cmd=cmd)

    assert args.pop('model_type') == 'mom'
    assert args.pop('config_path') == 'path/to/config.yaml'
    assert args.pop('lab_path') == 'path/to/lab'
    assert args.pop('hard_sweep') is True

    assert len(args) == 0

    # Test short options
    arguments = shlex.split('payu {cmd} '
                            '-m mom '
                            '-c path/to/config.yaml '
                            '-l path/to/lab '.format(cmd=cmd))

    args = vars(parser.parse_args(arguments[1:]))

    run_cmd = args.pop('run_cmd')

    assert run_cmd.__module__ == 'payu.subcommands.{cmd}_cmd'.format(cmd=cmd)

    assert args.pop('model_type') == 'mom'
    assert args.pop('config_path') == 'path/to/config.yaml'
    assert args.pop('lab_path') == 'path/to/lab'
    assert args.pop('hard_sweep') is False

    assert len(args) == 0


def test_parse_collate():

    cmd = 'collate'

    arguments = shlex.split('payu {cmd}'.format(cmd=cmd))

    args = vars(parser.parse_args(arguments[1:]))

    run_cmd = args.pop('run_cmd')

    assert run_cmd.__module__ == 'payu.subcommands.{cmd}_cmd'.format(cmd=cmd)

    assert args.pop('model_type') is None
    assert args.pop('config_path') is None
    assert args.pop('lab_path') is None
    assert args.pop('init_run') is None
    assert args.pop('dir_path') is None

    assert len(args) == 0

    # Test long options
    arguments = shlex.split('payu {cmd} '
                            '--model mom '
                            '--config path/to/config.yaml '
                            '--laboratory path/to/lab '
                            '--initial 99 '
                            '--directory path/to/files '.format(cmd=cmd))

    args = vars(parser.parse_args(arguments[1:]))

    run_cmd = args.pop('run_cmd')

    assert run_cmd.__module__ == 'payu.subcommands.{cmd}_cmd'.format(cmd=cmd)

    assert args.pop('model_type') == 'mom'
    assert args.pop('config_path') == 'path/to/config.yaml'
    assert args.pop('lab_path') == 'path/to/lab'
    assert args.pop('init_run') == '99'
    assert args.pop('dir_path') == 'path/to/files'

    assert len(args) == 0

    # Test short options
    arguments = shlex.split('payu {cmd} '
                            '-m mom '
                            '-c path/to/config.yaml '
                            '-l path/to/lab '
                            '-i 99 '
                            '-d path/to/files '.format(cmd=cmd))

    args = vars(parser.parse_args(arguments[1:]))

    run_cmd = args.pop('run_cmd')

    assert run_cmd.__module__ == 'payu.subcommands.{cmd}_cmd'.format(cmd=cmd)

    assert args.pop('model_type') == 'mom'
    assert args.pop('config_path') == 'path/to/config.yaml'
    assert args.pop('lab_path') == 'path/to/lab'
    assert args.pop('init_run') == '99'
    assert args.pop('dir_path') == 'path/to/files'

    assert len(args) == 0


def test_parse_init():

    cmd = 'init'

    arguments = shlex.split('payu {cmd}'.format(cmd=cmd))

    args = vars(parser.parse_args(arguments[1:]))

    run_cmd = args.pop('run_cmd')

    assert run_cmd.__module__ == 'payu.subcommands.{cmd}_cmd'.format(cmd=cmd)

    assert args.pop('model_type') is None
    assert args.pop('config_path') is None
    assert args.pop('lab_path') is None

    assert len(args) == 0

    # Test long options
    arguments = shlex.split('payu {cmd} '
                            '--model mom '
                            '--config path/to/config.yaml '
                            '--laboratory path/to/lab '.format(cmd=cmd))

    args = vars(parser.parse_args(arguments[1:]))

    run_cmd = args.pop('run_cmd')

    assert run_cmd.__module__ == 'payu.subcommands.{cmd}_cmd'.format(cmd=cmd)

    assert args.pop('model_type') == 'mom'
    assert args.pop('config_path') == 'path/to/config.yaml'
    assert args.pop('lab_path') == 'path/to/lab'

    assert len(args) == 0

    # Test short options
    arguments = shlex.split('payu {cmd} '
                            '-m mom '
                            '-c path/to/config.yaml '
                            '-l path/to/lab '.format(cmd=cmd))

    args = vars(parser.parse_args(arguments[1:]))

    run_cmd = args.pop('run_cmd')

    assert run_cmd.__module__ == 'payu.subcommands.{cmd}_cmd'.format(cmd=cmd)

    assert args.pop('model_type') == 'mom'
    assert args.pop('config_path') == 'path/to/config.yaml'
    assert args.pop('lab_path') == 'path/to/lab'

    assert len(args) == 0
