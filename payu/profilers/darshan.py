import os

from payu.profilers.profiler import Profiler


class Darshan(Profiler):

    def __init__(self, expt):
        super(Darshan, self).__init__(expt)
        # TODO: Generalise this
        self.lib_path = '/short/fp0/mxw900/libs/libdarshan.so'

    def setup(self):
        ld_preload = os.environ.get('LD_PRELOAD', '')
        os.environ['LD_PRELOAD'] = ':'.join([self.lib_path, ld_preload])

    def postprocess(self):
        pass
