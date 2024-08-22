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
    args.force_archive,
    args.reproduce,
    args.force,
    args.metadata_off
]


def runcmd(model_type, config_path, lab_path, force_archive,
           reproduce=False, force=False, metadata_off=False):

    lab = Laboratory(model_type, config_path, lab_path)
    expt = Experiment(lab, reproduce=reproduce, force=force,
                      metadata_off=metadata_off)

    expt.setup(force_archive=force_archive)


runscript = runcmd
