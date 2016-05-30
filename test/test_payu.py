import errno
import os
import stat
import sys
import unittest

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

        # Raise a non-EEXIST error (EACCES)
        tmp_tmp_dir = os.path.join(tmp_dir, 'more_tmp')
        os.chmod(tmp_dir, stat.S_IRUSR)
        self.assertRaises(OSError, payu.fsops.mkdir_p, tmp_tmp_dir)

        # Cleanup
        os.chmod(tmp_dir, stat.S_IWUSR)
        os.rmdir(tmp_dir)

    def test_read_config(self):
        config_path = 'config_mom5.yaml'
        config = payu.fsops.read_config(config_path)

    def test_default_lab_path(self):
        # TODO
        pass

    def test_lab_new(self):
        lab = payu.laboratory.Laboratory('model')

if __name__ == '__main__':
    unittest.main()
