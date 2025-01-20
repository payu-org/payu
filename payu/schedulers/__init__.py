from payu.schedulers.pbs import PBS
from payu.schedulers.slurm import Slurm

from payu.schedulers.scheduler import Scheduler

index = {
    'pbs': PBS,
    'slurm': Slurm,
}

DEFAULT_SCHEDULER_CONFIG = 'pbs'
