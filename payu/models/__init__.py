from payu.models.access import Access
from payu.models.cice import Cice
from payu.models.gold import Gold
from payu.models.matm import Matm
from payu.models.mitgcm import Mitgcm
from payu.models.mom import Mom
from payu.models.oasis import Oasis
from payu.models.um import UnifiedModel
from payu.models.ww3 import WW3

from payu.models.mom6 import Mom6

index = {
    'access':   Access,
    'cice':     Cice,
    'gold':     Gold,
    'matm':     Matm,
    'mitgcm':   Mitgcm,
    'mom':      Mom,
    'oasis':    Oasis,
    'um':       UnifiedModel,
    'ww3':      WW3,
    'mom6':     Mom6,
}
