# coding: utf-8

from payu.experiment import Experiment
from payu.laboratory import Laboratory
import payu.subcommands.args as args

title = 'setup'
parameters = {'description': 'Setup model work directory for run'}

arguments = [
    args.model,
    args.config,
    args.laboratory,
    args.reproduce,
    args.force,
    args.metadata_off,
    args.is_new_experiment,
]


def runcmd(model_type, config_path, lab_path,
           reproduce=False, force=False, metadata_off=False, is_new_experiment=False):

    lab = Laboratory(model_type, config_path, lab_path)
    expt = Experiment(lab, reproduce=reproduce, force=force,
                      metadata_off=metadata_off,
                      is_new_experiment=is_new_experiment)

    expt.setup()


runscript = runcmd
