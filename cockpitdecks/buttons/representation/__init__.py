"""
Button display and rendering abstraction.
"""

import logging
from .representation import (
    Representation,
    Icon,
    IconText,
    MultiTexts,
    MultiIcons
)
from .representation import LED, ColoredLED
from .annunciator import Annunciator, AnnunciatorAnimate
from .draw import DataIcon, Switch, CircularSwitch, PushSwitch, Knob, Decor
from .animation import IconAnimation, DrawAnimationFTG
from .xp_str import StringIcon
from .xp_ac import AircraftIcon
from .xp_rw import RealWeatherIcon
from .xp_xw import XPWeatherIcon
from .xp_fma import FMAIcon
from .xp_fcu import FCUIcon
from .xp_iconside import IconSide
from .xtouch import EncoderLEDs

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
