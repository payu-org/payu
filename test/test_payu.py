import errno
import os
import stat
import sys
import unittest

try:
    # Python 2.x (str)
    from cStringIO import StringIO
except ImportError:
    # Python 3.x (unicode)
    from io import StringIO

sys.path.insert(1, '../')
import payu

# Submodules
import payu.fsops
import payu.laboratory

class Test(unittest.TestCase):

    def setUp(self):
        # Data here
        pass

    # fsops tests
    def test_mkdir_p(self):
        tmp_dir = os.path.join(os.getcwd(), 'tmp_dir')
        payu.fsops.mkdir_p(tmp_dir)

        # Re-create existing directory
        payu.fsops.mkdir_p(tmp_dir)

        # Raise a non-EEXIST error (e.g. EACCES)
        tmp_tmp_dir = os.path.join(tmp_dir, 'more_tmp')
        os.chmod(tmp_dir, stat.S_IRUSR)
        self.assertRaises(OSError, payu.fsops.mkdir_p, tmp_tmp_dir)

        # Cleanup
        os.chmod(tmp_dir, stat.S_IWUSR)
        os.rmdir(tmp_dir)

    def test_read_config(self):
        config_path = 'config_mom5.yaml'
        config = payu.fsops.read_config(config_path)

        # Raise a non-ENOENT error (e.g. EACCES)
        config_tmp = 'config_tmp.yaml'
        try:
            config_file = open(config_tmp, 'w')
            os.chmod(config_tmp, 0)
            self.assertRaises(IOError, payu.fsops.read_config, config_tmp)
        finally:
            os.chmod(config_tmp, stat.S_IWUSR)
            config_file.close()
            os.remove(config_tmp)

    def test_make_symlink(self):
        tmp_path = 'tmp_file'
        tmp_sym = 'tmp_sym'
        tmp_alt_path = 'tmp_alt'
        tmp_dir = 'tmp_dir'

        # Simple symlink test
        tmp = open(tmp_path, 'w')
        payu.fsops.make_symlink(tmp_path, tmp_sym)

        # Override an existing symlink
        tmp_alt = open(tmp_alt_path, 'w')
        payu.fsops.make_symlink(tmp_alt_path, tmp_sym)

        # Try to create symlink when filename already exists
        # TODO: validate stdout
        sys.stdout = StringIO()
        payu.fsops.make_symlink(tmp_path, tmp_alt_path)
        sys.stdout = sys.__stdout__

        # Raise a non-EEXIST signal (EACCESS)
        tmp_dir_sym = os.path.join(tmp_dir, tmp_sym)
        os.mkdir(tmp_dir)
        os.chmod(tmp_dir, 0)
        self.assertRaises(OSError, payu.fsops.make_symlink,
                          tmp_path, tmp_dir_sym)

        # Cleanup
        tmp.close()
        tmp_alt.close()

        os.rmdir(tmp_dir)
        os.remove(tmp_sym)
        os.remove(tmp_path)
        os.remove(tmp_alt_path)

    def test_splitpath(self):

        # Absolute path
        paths = payu.fsops.splitpath('/a/b/c')
        self.assertEqual(paths, ('/', 'a', 'b', 'c'))

        # Relative path
        paths = payu.fsops.splitpath('a/b/c')
        self.assertEqual(paths, ('a', 'b', 'c'))

        # Single local path
        paths = payu.fsops.splitpath('a')
        self.assertEqual(paths, ('a',))

    def test_default_lab_path(self):
        # TODO
        pass

    def test_lab_new(self):
        # TODO: validate stdout
        sys.stdout = StringIO()
        lab = payu.laboratory.Laboratory('model')
        sys.stdout = sys.__stdout__

if __name__ == '__main__':
    unittest.main()
