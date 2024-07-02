"""
Button display and rendering abstraction.
"""

import logging

from .representation import Representation

# Image/icon based
from .icon import IconBase, Icon, IconText, MultiTexts, MultiIcons
from .hardware import VirtualEncoder, VirtualLLColoredButton, VirtualXTMLED, VirtualXTMMCLED

try:
    from .hardware import VirtualXTMEncoderLED
except:
    pass

from .annunciator import Annunciator, AnnunciatorAnimate
from .draw import DataIcon, Switch, CircularSwitch, PushSwitch, Knob, Decor
from .animation import IconAnimation, DrawAnimationFTG

from cockpitdecks import DECK_FEEDBACK, all_subclasses

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

# ###############################
# Optional representations
#
# Some of these representations require some optional python packages
# If package is not installed, representation is not loaded.

# X-Plane specific
from .xp_acf import Aircraft

# Toliss Airbus specific
from .tl_fma import FMAIcon
from .tl_fcu import FCUIcon

# Deck specific
try:
    from .led import LED, ColoredLED

    logger.info(f"LED, ColoredLED installed")
except ImportError:
    logger.warning(f"LED, ColoredLED not installed")

try:
    from .xtouch import EncoderLEDs

    logger.info(f"EncoderLEDs installed")
except ImportError:
    logger.warning(f"EncoderLEDs not installed")

try:
    from .xp_iconside import IconSide

    logger.info(f"IconSide installed")
except ImportError:
    logger.warning(f"IconSide not installed")

try:
    from .xp_rw import RealWeatherIcon

    logger.info(f"RealWeatherIcon installed")
except ImportError:
    logger.warning(f"RealWeatherIcon not installed")

try:
    from .xp_xw import XPWeatherIcon

    logger.info(f"XPWeatherIcon installed")
except ImportError:
    logger.warning(f"XPWeatherIcon not installed")

try:
    logger.info(f"LiveWeatherIcon installed")
except ImportError:
    logger.warning(f"LiveWeatherIcon not installed")

try:
    from .external import LiveWeatherIcon

    logger.info(f"LiveWeatherIcon installed")
except ImportError:
    logger.warning(f"LiveWeatherIcon not installed")

try:
    from .external import LiveWeatherIcon

    logger.info(f"LiveWeatherIcon installed")
except ImportError:
    logger.warning(f"LiveWeatherIcon not installed")


REPRESENTATIONS = {s.name(): s for s in all_subclasses(Representation)} | {DECK_FEEDBACK.NONE.value: Representation}


def get_representations_for(feedback: DECK_FEEDBACK):
    return [a for a in REPRESENTATIONS.values() if feedback in a.get_required_capability()]
