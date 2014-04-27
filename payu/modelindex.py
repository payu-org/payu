# coding: utf-8

from payu.drivers.access import Access
from payu.drivers.cice import Cice
from payu.drivers.gold import Gold
from payu.drivers.matm import Matm
from payu.drivers.mitgcm import Mitgcm
from payu.drivers.mom import Mom
from payu.drivers.oasis import Oasis
from payu.drivers.um import UnifiedModel

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
