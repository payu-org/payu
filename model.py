# coding: utf-8

from mom import Mom
from mom4 import mom4
from mitgcm import Mitgcm
from gold import Gold
from cice import Cice

index = {
    'mom':      Mom,
    'mom4':     mom4,
    'mitgcm':   Mitgcm,
    'gold':     Gold,
    'cice':     Cice,
}
