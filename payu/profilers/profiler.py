class Profiler(object):

    def __init__(self, expt):
        self.expt = expt
        self.flags = None
        self.runscript = None

    def wrapper(self, cmd):
        return cmd

    def postprocess(self):
        raise NotImplementedError
