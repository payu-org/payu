import os
import sys

from payu import envmod
from payu.profilers.profiler import Profiler


class OpenSpeedShop(Profiler):

    def setup(self):
        os.environ['OPENSS_RAWDATA_DIR'] = self.expt.work_path
        os.environ['OPENSS_DB_DIR'] = self.expt.work_path

    def load_modules(self):
        envmod.module('load', 'openspeedshop')

    def wrapper(self, cmd):
        # TODO: Get this from the "profilers" entry, not a separate one
        oss = self.expt.config.get('openspeedshop')
        if oss:
            oss_runcmd = oss.get('runcmd')
            if not oss_runcmd:
                print('payu: error: OpenSpeedShop requires an executable.')
                sys.exit(1)

            cmd = '{0} "{1}"'.format(oss_runcmd, cmd)

            if oss_runcmd.startswith('osshwc'):
                oss_hwc = oss.get('hwc')
                if not oss_hwc:
                    print('payu: error: This OSS command requires hardware '
                          'counters.')
                    sys.exit(1)
                else:
                    cmd = ' '.join([cmd, oss_hwc])

        return cmd

    def postprocess(self):
        pass
