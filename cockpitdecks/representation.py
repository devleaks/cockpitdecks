"""
Button display and rendering abstraction.
"""
import logging
from .button_representation import Representation, Icon, IconText, MultiTexts, MultiIcons, IconAnimation, IconSide
from .button_representation import LED, ColoredLED, MultiLEDs
from .button_annunciator import Annunciator, AnnunciatorAnimate
from .button_draw import DataIcon, Switch, CircularSwitch, PushSwitch, DrawAnimationFTG

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


REPRESENTATIONS = {
    "none": Representation,
    "icon": Icon,
    "text": IconText,
    "icon-color": Icon,
    "multi-icons": MultiIcons,
    "multi-texts": MultiTexts,
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

#
# ###############################
# DECK DISPLAY MAP
#
#
# Will only load if AVWX is installed
images = ["icon", "text", "icon-color", "multi-icons", "multi-texts", "icon-animate", "side"]
drawn_buttons = ["data", "annunciator", "annunciator-animate", "switch", "circular-switch", "push-switch", "ftg"]

if "weather" in REPRESENTATIONS.keys():
    drawn_buttons.append("weather")

DECK_REPRESENTATIONS = {
    "lcd": images + drawn_buttons,
    "led": ["led"],
    "colored-led": ["led", "colored-led"],
    "encoder-leds": ["multi-leds"]
}
