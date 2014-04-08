# coding: utf-8

from drivers.access import Access
from drivers.cice import Cice
from drivers.gold import Gold
from drivers.matm import Matm
from drivers.mitgcm import Mitgcm
from drivers.mom import Mom
from drivers.oasis import Oasis
from drivers.um import UnifiedModel

from modeldriver import Model

index = {
    'access':   Access,
    'cice':     Cice,
    'gold':     Gold,
    'matm':     Matm,
    'mitgcm':   Mitgcm,
    'mom':      Mom,
    'oasis':    Oasis,
    'um':       UnifiedModel,
}
