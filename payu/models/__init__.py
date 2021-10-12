from payu.models.access import Access
from payu.models.accessom2 import AccessOm2
from payu.models.cesm_cmeps import AccessOm3
from payu.models.cable import Cable
from payu.models.cice import Cice
from payu.models.cice5 import Cice5
from payu.models.gold import Gold
from payu.models.matm import Matm
from payu.models.mitgcm import Mitgcm
from payu.models.mom import Mom
from payu.models.mom6 import Mom6
from payu.models.nemo import Nemo
from payu.models.oasis import Oasis
from payu.models.test import Test
from payu.models.um import UnifiedModel
from payu.models.ww3 import WW3
from payu.models.qgcm import Qgcm
from payu.models.yatm import Yatm

from payu.models.model import Model

index = {
    'access':     Access,
    'access-om2': AccessOm2,
    'access-om3': AccessOm3,
    'cice':       Cice,
    'cice5':      Cice5,
    'gold':       Gold,
    'matm':       Matm,
    'yatm':       Yatm,
    'mitgcm':     Mitgcm,
    'mom':        Mom,
    'nemo':       Nemo,
    'oasis':      Oasis,
    'test':       Test,
    'um':         UnifiedModel,
    'ww3':        WW3,
    'mom6':       Mom6,
    'qgcm':       Qgcm,
    'cable':      Cable,

    # Default
    'default':    Model,
    'model':      Model,
}
