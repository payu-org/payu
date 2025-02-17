from contextlib import contextmanager
import os
import stat
from pathlib import Path
import re
import shutil

import yaml

# Namespace clash if import setup_cmd.runcmd as setup. For
# consistency use payu_ prefix for all commands
from payu.subcommands.init_cmd import runcmd as payu_init
from payu.subcommands.setup_cmd import runcmd as payu_setup_orignal
from payu.subcommands.sweep_cmd import runcmd as payu_sweep

ctrldir_basename = 'ctrl'

testdir = Path().cwd() / Path('test')
tmpdir = testdir / 'tmp'
ctrldir = tmpdir / ctrldir_basename
labdir = tmpdir / 'lab'
workdir = ctrldir / 'work'
payudir = tmpdir / 'payu'

archive_dir = labdir / 'archive'

# Note: These are using a fixed archive name which is set in config.yaml
expt_archive_dir = archive_dir / ctrldir_basename
expt_workdir = labdir / 'work' / ctrldir_basename

config_path = ctrldir / 'config.yaml'
metadata_path = ctrldir / 'metadata.yaml'

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
                'reproduce': {
                    'input': False,
                    'exe': False
                }
            },
            'runlog': False,
            "experiment": ctrldir_basename,
            "metadata": {
                "enable": False
            }
            }

metadata = {
    "experiment_uuid": "testUuid",
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
                   lab_path=str(labdir),
                   metadata_off=False)


def payu_setup(model_type=None,
               config_path=None,
               lab_path=None,
               force_archive=None,
               reproduce=None,
               sweep=True,
               force=False,
               metadata_off=False):
    """
    Wrapper around original setup command to provide default arguments
    and run in ctrldir
    """
    with cd(ctrldir):
        if sweep:
            payu_sweep(model_type=None,
                       config_path=None,
                       hard_sweep=False,
                       lab_path=str(labdir),
                       metadata_off=False)
        payu_setup_orignal(model_type,
                           config_path,
                           lab_path,
                           force_archive,
                           reproduce,
                           force,
                           metadata_off=False)


def write_config(config, path=config_path):
    with path.open('w') as file:
        file.write(yaml.dump(config, default_flow_style=False,
                   sort_keys=False))


def make_exe(exe_name=None):
    # Create a fake executable file
    bindir = labdir / 'bin'
    bindir.mkdir(parents=True, exist_ok=True)
    if not exe_name:
        exe_name =  config['exe']
    exe_path = bindir / exe_name
    exe_size = 199
    make_random_file(exe_path, exe_size)
    exe_path.chmod(exe_path.stat().st_mode | stat.S_IEXEC)


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


def make_expt_archive_dir(type='restart', index=0, additional_path=None):
    """Make experiment archive directory of given type (i.e. restart or
     output)"""
    dir_path = os.path.join(expt_archive_dir, f'{type}{index:03d}')
    if additional_path:
        dir_path = os.path.join(dir_path, additional_path)

    os.makedirs(dir_path)
    return dir_path


def list_expt_archive_dirs(type='restart', full_path=True):
    """Return a list of output/restart paths in experiment archive
     path"""
    dirs = []
    if os.path.exists(expt_archive_dir):
        if os.path.isdir(expt_archive_dir):
            naming_pattern = re.compile(fr"^{type}[0-9][0-9][0-9]$")
            dirs = [d for d in os.listdir(expt_archive_dir)
                    if naming_pattern.match(d)]

            if full_path:
                dirs = [os.path.join(expt_archive_dir, d) for d in dirs]
    return dirs


def remove_expt_archive_dirs(type='restart'):
    """Remove experiment archive directories of the given type (i.e. restart
    or output). Useful for cleaning up archive between tests"""
    for dir_path in list_expt_archive_dirs(type):
        try:
            shutil.rmtree(dir_path)
        except Exception as e:
            print(e)


def write_metadata(metadata=metadata, path=metadata_path):
    with path.open('w') as file:
        file.write(yaml.dump(metadata, default_flow_style=False))


def make_all_files():
    make_inputs()
    make_exe()
    make_restarts()
