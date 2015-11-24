import os
import shutil

from payu.profilers.profiler import Profiler
from payu.fsops import mkdir_p


class Gprof(Profiler):

    def __init__(self, expt):
        super(Gprof, self).__init__(expt)
        self.runscript = '/apps/pgprof/parallel_gprof'

    def postprocess(self):
        gmon_dir = os.path.join(self.expt.work_path, 'gmon')
        mkdir_p(gmon_dir)

        gmon_fnames = [f for f in os.listdir(self.expt.work_path)
                       if f.startswith('gmon.out')]

        for gmon in gmon_fnames:
            f_src = os.path.join(self.expt.work_path, gmon)
            f_dst = os.path.join(gmon_dir, gmon)
            shutil.move(f_src, f_dst)
