"""
Button display and rendering abstraction.
"""
import logging
from .button_representation import Representation, Icon, IconText, MultiIcons, IconAnimation, IconSide
from .button_representation import LED, ColoredLED, MultiLEDs
from .button_representation import LED, ColoredLED, MultiLEDs
from .button_annunciator import Annunciator, AnnunciatorAnimate
from .button_draw import DataIcon, Switch, CircularSwitch, PushSwitch, DrawAnimationFTG

logger = logging.getLogger("Representation")
# logger.setLevel(logging.DEBUG)


REPRESENTATIONS = {
    "none": Representation,
    "icon": Icon,
    "text": IconText,
    "icon-color": Icon,
    "multi-icons": MultiIcons,
    "icon-animate": IconAnimation,
    "side": IconSide,
    "led": LED,
    "colored-led": ColoredLED,
    "multi-leds": MultiLEDs,
    "annunciator": Annunciator,
    "annunciator-animate": AnnunciatorAnimate,
    "switch": Switch,
    "circular-switch": CircularSwitch,
    "push-switch": PushSwitch,
    "data": DataIcon,
    "ftg": DrawAnimationFTG
}

#
# ###############################
# OPTIONAL REPRESENTATIONS
#
#
# Will only load if AVWX is installed
try:
    from .button_ext import WeatherIcon
    REPRESENTATIONS["weather"] = WeatherIcon
    logger.info(f"WeatherIcon installed")
except ImportError:
    pass
