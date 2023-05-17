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

# ###############################
# format is representation: Classname
#
# - index: b2
#   name: Popup ND1
#   type: push
#   colored-led: (255, 128, 0)         <--------
#   label: ND1
#   command: AirbusFBW/PopUpND1
#   dataref: AirbusFBW/PopUpStateArray[4]
#
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

DEFAULT_REPRESENTATIONS = ["none"]

#
# ###############################
# OPTIONAL REPRESENTATIONS
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
# This estabishes the link between deck capabilities (view) and Representations
#
# - name: 0
#   prefix: e
#   action: push
#   view: image         <--------
#   image: [90, 90]
#   repeat: 6
#
images = ["icon", "text", "icon-color", "multi-icons", "multi-texts", "icon-animate", "side"]
drawn_buttons = ["data", "annunciator", "annunciator-animate", "switch", "circular-switch", "push-switch", "ftg"]

if "weather" in REPRESENTATIONS.keys():
    drawn_buttons.append("weather")

# ###############################
# format is view: [ representation ]
# view is used in deck definitions
#
DECK_REPRESENTATIONS = {
    "image": images + drawn_buttons,
    "lcd": images + drawn_buttons,
    "led": ["led"],
    "colored-led": ["led", "colored-led"],
    "encoder-leds": ["multi-leds"]
}
