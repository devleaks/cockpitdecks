"""
Button display and rendering abstraction.
"""

import logging
from .representation import Representation, Icon, IconText, MultiTexts, MultiIcons
from .representation import LED, ColoredLED
from .annunciator import Annunciator, AnnunciatorAnimate
from .draw import DataIcon, Switch, CircularSwitch, PushSwitch, Knob, Decor
from .animation import IconAnimation, DrawAnimationFTG
from .xp_rw import RealWeatherIcon
from .xp_xw import XPWeatherIcon
from .xp_iconside import IconSide
from .xtouch import EncoderLEDs
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
