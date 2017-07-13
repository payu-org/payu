# coding: utf-8

from payu.experiment import Experiment
from payu.laboratory import Laboratory
from payu.runlog import Runlog
import payu.subcommands.args as args

title = 'ghsetup'
parameters = {'description': 'Create authentication keys for github'}

arguments = [args.model, args.config, args.laboratory]


def runcmd(model_type, config_path, lab_path):

    lab = Laboratory(model_type, config_path, lab_path)
    expt = Experiment(lab)
    runlog = Runlog(expt)

    runlog.github_setup()


runscript = runcmd
