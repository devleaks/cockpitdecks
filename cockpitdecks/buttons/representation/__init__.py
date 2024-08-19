"""
Button display and rendering abstraction.
"""

import logging

from .representation import Representation

# Image/icon based
from .icon import IconBase, Icon, IconText, MultiTexts, MultiIcons
from .icon_animation import IconAnimation

from .mosaic import Mosaic

# Drawing based representation
from .annunciator import Annunciator, AnnunciatorAnimate
from .draw import Decor
from .draw_animation import DrawAnimation, DrawAnimationFTG
from .switch import Switch, CircularSwitch, PushSwitch, Knob
from .data import DataIcon
from .chart import ChartIcon
from .gauge import TapeIcon, GaugeIcon

# Special Web Deck represenations for hardware button
from .hardware import VirtualEncoder, VirtualLLColoredButton, VirtualXTMLED, VirtualXTMMCLED

try:
    from .hardware import VirtualXTMEncoderLED
except:
    pass

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
    from .xp_ws import XPWeatherSummaryIcon

    logger.info(f"XPWeatherSummaryIcon installed")
except ImportError:
    logger.warning(f"XPWeatherSummaryIcon not installed")

try:
    from .xp_rw import XPRealWeatherIcon

    logger.info(f"XPRealWeatherIcon installed")
except ImportError:
    logger.warning(f"XPRealWeatherIcon not installed")

try:
    logger.info(f"WeatherMetarIcon installed")
except ImportError:
    logger.warning(f"WeatherMetarIcon not installed")

# NOT X-Plane related, uses real life METAR
try:
    from .external import WeatherMetarIcon

    logger.info(f"WeatherMetarIcon installed")
except ImportError:
    logger.warning(f"WeatherMetarIcon not installed")

REPRESENTATIONS = {s.name(): s for s in all_subclasses(Representation)} | {DECK_FEEDBACK.NONE.value: Representation}


def get_representations_for(feedback: DECK_FEEDBACK):
    return [a for a in REPRESENTATIONS.values() if feedback in a.get_required_capability()]
