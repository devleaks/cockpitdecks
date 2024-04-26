"""
Button display and rendering abstraction.
"""

import logging
from .representation import (
    Representation,
    Icon,
    IconText,
    MultiTexts,
    MultiIcons,
    IconSide,
)
from .representation import LED, ColoredLED, MultiLEDs
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

from cockpitdecks import DECK_FEEDBACK

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

# ###############################
# format is representation: Classname
#
# - index: b2
#   name: Popup ND1
#   mytype: push
#   colored-led: (255, 128, 0)         <--------  Representation.name() keyword
#   label: ND1
#   command: AirbusFBW/PopUpND1
#   dataref: AirbusFBW/PopUpStateArray[4]
#
def all_subclasses(cls):

    if cls == type:
        raise ValueError("Invalid class - 'type' is not a class")

    subclasses = set()

    stack = []
    try:
        stack.extend(cls.__subclasses__())
    except (TypeError, AttributeError) as ex:
        raise ValueError("Invalid class" + repr(cls)) from ex

    while stack:
        sub = stack.pop()
        subclasses.add(sub)
        try:
            stack.extend(s for s in sub.__subclasses__() if s not in subclasses)
        except (TypeError, AttributeError):
           continue

    return list(subclasses)

try:
    from .external import LiveWeatherIcon
    logger.info(f"LiveWeatherIcon installed")
except ImportError:
    logger.warning(f"LiveWeatherIcon not installed")


REPRESENTATIONS = {s.name(): s for s in all_subclasses(Representation)}

def get_representations_for(feedback: DECK_FEEDBACK):
    return [a for a in REPRESENTATIONS.values() if feedback in a.get_required_capability()]
