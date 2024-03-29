"""
Button display and rendering abstraction.
"""
import logging
from .representation import Representation, Icon, IconText, MultiTexts, MultiIcons, IconSide
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

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

# ###############################
# format is representation: Classname
#
# - index: b2
#   name: Popup ND1
#   mytype: push
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
    "knob": Knob,
    "circular-switch": CircularSwitch,
    "push-switch": PushSwitch,
    "data": DataIcon,
    "ftg": DrawAnimationFTG,
    "decor": Decor,
    "real-weather": RealWeatherIcon,
    "xp-weather": XPWeatherIcon,
    "strings": StringIcon,
    "fma": FMAIcon,
    "fcu": FCUIcon,
    "aircraft": AircraftIcon,
}

DEFAULT_REPRESENTATIONS = ["none"]

#
# ###############################
# OPTIONAL REPRESENTATIONS
#
# Will only load if AVWX is installed
try:
    from .external import LiveWeatherIcon

    REPRESENTATIONS["live-weather"] = LiveWeatherIcon
    logger.info(f"LiveWeatherIcon installed")
except ImportError:
    logger.warning(f"LiveWeatherIcon not installed")
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
drawn_buttons = [
    "decor",
    "data",
    "annunciator",
    "annunciator-animate",
    "switch",
    "circular-switch",
    "push-switch",
    "ftg",
    "knob",
    "strings",
    "fma",
    "fcu",
    "real-weather",
    "xp-weather",
    "aircraft",
]

if "live-weather" in REPRESENTATIONS.keys():
    drawn_buttons.append("live-weather")

# ###############################
# format is view: [ representation ]
# view is used in deck definitions
#
DECK_REPRESENTATIONS = {
    "image": images + drawn_buttons,
    "lcd": images + drawn_buttons,
    "led": ["led"],
    "colored-led": ["led", "colored-led"],
    "encoder-leds": ["multi-leds"],
}
