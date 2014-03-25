# coding: utf-8

from cice import Cice
from gold import Gold
from mitgcm import Mitgcm
from mom import Mom
from oasis import Oasis

from modeldriver import Model

index = {
    'access':   Model,  # dummy
    'cice':     Cice,
    'gold':     Gold,
    'matm':     Model,  # dummy
    'mitgcm':   Mitgcm,
    'mom':      Mom,
    'oasis':    Oasis,  # dummy
}
