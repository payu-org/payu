from contextlib import contextmanager
import os
from pathlib import Path

import yaml

import payu

# Namespace clash if import setup_cmd.runcmd as setup. For
# consistency use payu_ prefix for all commands
from payu.subcommands.init_cmd import runcmd as payu_init
from payu.subcommands.setup_cmd import runcmd as payu_setup_orignal
from payu.subcommands.sweep_cmd import runcmd as payu_sweep

testdir = Path().cwd() / Path('test')
tmpdir = testdir / 'tmp'
ctrldir = tmpdir / 'ctrl'
labdir = tmpdir / 'lab'
workdir = ctrldir / 'work'
payudir = tmpdir / 'payu'

print('tmpdir: {}'.format(tmpdir))

config = {
            'shortpath': '..',
            'laboratory': 'lab',
            'queue': 'normal',
            'project': 'aa30',
            'walltime': '0:30:00',
            'ncpus': 64,
            'mem': '64GB',
            'jobname': 'testrun',
            'model': 'test',
            'exe': 'test.exe',
            'input': 'testrun_1',
            'manifest': {
                        'scaninputs': False,
                        'reproduce': {
                                        'input': False,
                                        'exe': False
                                        }
                        }
            }

@contextmanager
def cd(directory):
    """
    Context manager to change into a directory and
    change back to original directory when complete
    """
    old_dir = Path.cwd()
    os.chdir(directory)
    try:
        yield
    finally:
        os.chdir(old_dir)


def make_random_file(filename, size=1000**2):
    """
    Make a file of specified size filled with some
    random content
    """
    with open(filename, 'wb') as fout:
        fout.write(os.urandom(size))


def get_manifests(mfdir):
    """
    Read in all manifests and return as a dict
    """
    manifests = {}
    for mf in ['exe', 'input', 'restart']:
        mfpath = Path(mfdir)/"{}.yaml".format(mf)
        with mfpath.open() as fh:
            manifests[mfpath.name] = list(yaml.safe_load_all(fh))[1]
    return manifests


def sweep_work(hard_sweep=False):
    # Sweep workdir
    with cd(ctrldir):
        payu_sweep(model_type=None,
                   config_path=None,
                   hard_sweep=hard_sweep,
                   lab_path=str(labdir))


def payu_setup(model_type=None,
               config_path=None,
               lab_path=None,
               force_archive=None,
               reproduce=None,
               sweep=True,
               force=False):
    """
    Wrapper around original setup command to provide default arguments
    and run in ctrldir
    """
    with cd(ctrldir):
        if sweep:
            payu_sweep(model_type=None,
                       config_path=None,
                       hard_sweep=False,
                       lab_path=str(labdir))
        payu_setup_orignal(model_type,
                           config_path,
                           lab_path,
                           force_archive,
                           reproduce,
                           force)


def write_config(config):
    with (ctrldir / 'config.yaml').open('w') as file:
        file.write(yaml.dump(config, default_flow_style=False))


def make_exe():
    # Create a fake executable file
    bindir = labdir / 'bin'
    bindir.mkdir(parents=True, exist_ok=True)
    exe = config['exe']
    exe_size = 199
    make_random_file(bindir/exe, exe_size)


def make_payu_exe():
    # Create a fake payu executable
    bindir = payudir / 'bin'
    bindir.mkdir(parents=True, exist_ok=True)
    exe_size = 199
    make_random_file(bindir/'payu-run', exe_size)
    make_random_file(bindir/'payu-collate', exe_size)


def make_inputs():
    # Create some fake input files
    inputdir = labdir / 'input' / config['input']
    inputdir.mkdir(parents=True, exist_ok=True)
    for i in range(1, 4):
        make_random_file(inputdir/'input_00{i}.bin'.format(i=i),
                         1000**2 + i)


def make_restarts(fnames=None):
    # Create some fake restart files
    restartdir = labdir / 'archive' / 'restarts'
    restartdir.mkdir(parents=True, exist_ok=True)
    if fnames is None:
        fnames = ['restart_00{i}.bin'.format(i=i) for i in range(1, 4)]
    for i, fname in enumerate(fnames):
        make_random_file(restartdir/fname, 5000**2 + i)


def make_all_files():
    make_inputs()
    make_exe()
    make_restarts()
