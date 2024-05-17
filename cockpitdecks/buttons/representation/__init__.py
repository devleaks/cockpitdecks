"""
Button display and rendering abstraction.
"""

import logging

from .representation import Representation

# Image/icon based
from .icon import Icon, IconText, MultiTexts, MultiIcons
from .annunciator import Annunciator, AnnunciatorAnimate
from .draw import DataIcon, Switch, CircularSwitch, PushSwitch, Knob, Decor
from .animation import IconAnimation, DrawAnimationFTG

# Deck specific
from .led import LED, ColoredLED
from .xtouch import EncoderLEDs

# X-Plane specific
from .xp_rw import RealWeatherIcon
from .xp_xw import XPWeatherIcon
from .xp_iconside import IconSide
from .xp_acf import Aircraft

# Toliss Airbus specific
from .tl_fma import FMAIcon
from .tl_fcu import FCUIcon

from cockpitdecks import DECK_FEEDBACK, all_subclasses

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


# ###############################
# Optional representations
#
try:
    from .external import LiveWeatherIcon

    logger.info(f"LiveWeatherIcon installed")
except ImportError:
    logger.warning(f"LiveWeatherIcon not installed")


REPRESENTATIONS = {s.name(): s for s in all_subclasses(Representation)} | {DECK_FEEDBACK.NONE.value: Representation}


def get_representations_for(feedback: DECK_FEEDBACK):
    return [a for a in REPRESENTATIONS.values() if feedback in a.get_required_capability()]
