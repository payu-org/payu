class Profiler(object):

    def __init__(self, expt):
        self.expt = expt
        self.wrapper = None
        self.flags = None

    def postprocess(self):
        raise NotImplementedError
