import errno
import os
import stat
import sys
import unittest

try:
    from io import StringIO
except ImportError:
    from cStringIO import StringIO

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

        # Read a nonexistent file
        sys.stdout = StringIO()
        config = payu.fsops.read_config('no_such_file.yaml')
        self.assertEqual(config, {})
        sys.stdout = sys.__stdout__

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

    def test_default_lab_path(self):
        # TODO
        pass

    def test_lab_new(self):
        lab = payu.laboratory.Laboratory('model')

if __name__ == '__main__':
    unittest.main()
