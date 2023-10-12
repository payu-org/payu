# coding: utf-8

from payu.experiment import Experiment
from payu.laboratory import Laboratory
import payu.subcommands.args as args

title = 'archive'
parameters = {'description': 'Archive model output after run'}

arguments = [args.model, args.config, args.laboratory,
             args.force_prune_restarts]


def runcmd(model_type, config_path, lab_path, force_prune_restarts):

    lab = Laboratory(model_type, config_path, lab_path)
    expt = Experiment(lab)

    expt.archive(force_prune_restarts)


runscript = runcmd
