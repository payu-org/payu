import os
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

        os.rmdir(tmp_dir)

    def test_read_config(self):
        # TODO
        pass

    def test_default_lab_path(self):
        # TODO
        pass

    def test_lab_new(self):
        lab = payu.laboratory.Laboratory('model')

if __name__ == '__main__':
    unittest.main()
