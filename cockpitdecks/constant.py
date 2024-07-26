#
# C O C K P I T D E C K S
#
# Elgato Stream Decks, Loupedeck LoupedeckLive, and Berhinger X-Touch Mini to X-Plane Cockpit.
#
#
import os
import logging
from typing import List
from collections.abc import MutableMapping
from enum import Enum
import ruamel
from ruamel.yaml import YAML


# ##############################################################
# A few constants and default values
# Adjust with care...
#
# These are mainly used inside Cockpitdecks and should not be changed.
# Values that might need adjustments are isolated in network.py file.
#
# ROOT_DEBUG = "cockpitdecks.xplaneudp,cockpitdecks.xplane,cockpitdecks.button"
ROOT_DEBUG = ""
EXCLUDE_DECKS: List[str] = []  # list serial numbers of deck not usable by Streadecks
USE_COLLECTOR = False

# Files
CONFIG_FOLDER = "deckconfig"
CONFIG_FILE = "config.yaml"
SECRET_FILE = "secret.yaml"

DEFAULT_LAYOUT = "default"
DEFAULT_PAGE_NAME = "Default Page"

RESOURCES_FOLDER = "resources"
FONTS_FOLDER = "fonts"
ICONS_FOLDER = "icons"
DECKS_FOLDER = "decks"
DECK_TYPES = "types"
DECK_IMAGES = "images"

ICON_SIZE = 256  # px

# Virtual decks and web decks
VIRTUAL_DECK_DRIVER = "virtualdeck"
AIRCRAFT_ASSET_PATH = "/aircraft/decks/images/"  # this is an URL path, so forward slash are appropriate
COCKPITDECKS_ASSET_PATH = "/assets/decks/images/"  # this is an URL path

TEMPLATE_FOLDER = os.path.join(os.path.dirname(__file__), DECKS_FOLDER, RESOURCES_FOLDER, "templates")
ASSET_FOLDER = os.path.join(os.path.dirname(__file__), DECKS_FOLDER, RESOURCES_FOLDER, "assets")

AIRCRAFT_CHANGE_MONITORING_DATAREF = "sim/aircraft/view/acf_livery_path"


class ANNUNCIATOR_STYLES(Enum):
    KORRY = "k"  # k(orry): backlit, glowing
    VIVISUN = "v"  # v(ivisun): bright, sharp.


# internals
ID_SEP = "/"
DEFAULT_ATTRIBUTE_PREFIX = "default-"

# System default values
COCKPITDECKS_DEFAULT_VALUES = {
    "cache-icon": True,
    "cockpit-color": "cornflowerblue",
    "cockpit-texture": None,
    "cockpit-theme": "light",
    "system-font": "Monaco.ttf",  # alias
    DEFAULT_ATTRIBUTE_PREFIX + "annunciator-color": "black",
    DEFAULT_ATTRIBUTE_PREFIX + "annunciator-style": ANNUNCIATOR_STYLES.KORRY,
    DEFAULT_ATTRIBUTE_PREFIX + "annunciator-texture": None,
    DEFAULT_ATTRIBUTE_PREFIX + "font": "D-DIN.otf",
    DEFAULT_ATTRIBUTE_PREFIX + "home-page-name": "index",
    DEFAULT_ATTRIBUTE_PREFIX + "icon-color": "cornflowerblue",
    DEFAULT_ATTRIBUTE_PREFIX + "icon-name": "inop.png",
    DEFAULT_ATTRIBUTE_PREFIX + "icon-texture": None,
    DEFAULT_ATTRIBUTE_PREFIX + "interface-bg-color": "black",
    DEFAULT_ATTRIBUTE_PREFIX + "interface-fg-color": "white",
    DEFAULT_ATTRIBUTE_PREFIX + "label-color": "white",
    DEFAULT_ATTRIBUTE_PREFIX + "label-font": "D-DIN.otf",
    DEFAULT_ATTRIBUTE_PREFIX + "label-position": "ct",
    DEFAULT_ATTRIBUTE_PREFIX + "label-size": 10,
    DEFAULT_ATTRIBUTE_PREFIX + "light-off-intensity": 10,
    DEFAULT_ATTRIBUTE_PREFIX + "logo": "logo.png",
    DEFAULT_ATTRIBUTE_PREFIX + "system-font": "Monaco.ttf",
    DEFAULT_ATTRIBUTE_PREFIX + "text-color": "white",
    DEFAULT_ATTRIBUTE_PREFIX + "text-font": "D-DIN.otf",
    DEFAULT_ATTRIBUTE_PREFIX + "text-position": "cm",
    DEFAULT_ATTRIBUTE_PREFIX + "text-size": 32,
    DEFAULT_ATTRIBUTE_PREFIX + "wallpaper": "wallpaper.png",
}


# deckconfig attribute keywords
#
# Config.yaml
#
class CONFIG_KW(Enum):
    ANNUNCIATOR_MODEL = "model"
    BACKPAGE = "back"
    BUTTONS = "buttons"
    DATAREF = "dataref"
    DATAREFS = "multi-datarefs"
    DECKS = "decks"
    DECOR = "decor"
    DEVICE = "device"
    DISABLED = "disabled"
    DRIVER = "driver"
    ENABLED = "enabled"
    FORMULA = "formula"
    FRAME = "frame"
    GUARD = "guard"
    INCLUDES = "includes"
    INDEX = "index"
    INDEX_NUMERIC = "_index"
    INITIAL_VALUE = "initial-value"
    LAYOUT = "layout"
    MANAGED = "managed"
    MULTI_DATAREFS = "multi-datarefs"
    NAME = "name"
    NONE = "none"
    OPTIONS = "options"
    SERIAL = "serial"
    SET_DATAREF = "set-dataref"
    STRING_DATAREFS = "string-datarefs"
    TYPE = "type"
    VIEW = "view"
    VIEW_IF = "view-if"


class ACTIVATION_KW(Enum):
    NO_ACTIVATION = "none"
    LONG_PRESS = "long-press"
    OPTIONS = "options"


#
# Deck.yaml (decks/resources/*.yaml)
#
class DECK_KW(Enum):
    ACTION = "action"
    BACKGROUND = "background"
    BUTTONS = "buttons"
    DIMENSION = "dimension"
    DRIVER = "driver"
    FEEDBACK = "feedback"
    HANDLE = "handle"
    HARDWARE_REPRESENTATION = "hardware"
    IMAGE = "image"
    INDEX = "index"
    INT_NAME = "_intname"
    LAYOUT = "layout"
    NAME = "name"
    NONE = "none"
    OFFSET = "offset"
    OPTIONS = "options"
    POSITION = "position"
    PREFIX = "prefix"
    RANGE = "range"
    REPEAT = "repeat"
    SPACING = "spacing"


# ############################################################
#
# deck type action capabilities
#
class DECK_ACTIONS(Enum):
    NONE = "none"
    PRESS = "press"  # triggered automatically by Elgato firmwire, ONE event only (when pressed/touched)
    LONGPRESS = "longpress"  # triggered automatically by Elgato firmwire, ONE event only (when pressed/touched)
    PUSH = "push"  # TWO events, pressed and released
    ENCODER = "encoder"  # turn with clicks or stops
    CURSOR = "cursor"
    SWIPE = "swipe"


#
# deck type feedback capabilities
#
class DECK_FEEDBACK(Enum):
    NONE = "none"
    COLORED_LED = "colored-led"
    IMAGE = "image"
    LED = "led"
    ENCODER_LEDS = "encoder-leds"  # specific to X-Touch mini
    VIBRATE = "vibrate"


# ############################################################
#
# Prevent aliasing
# https://stackoverflow.com/questions/64716894/ruamel-yaml-disabling-alias-for-dumping
ruamel.yaml.representer.RoundTripRepresenter.ignore_aliases = lambda x, y: True

yaml = YAML(typ="safe", pure=True)
yaml.default_flow_style = False

init_logger = logging.getLogger("init/common")


#
#  Yaml config file reader
#
CONFIG_FILENAME = "__filename__"


class Config(MutableMapping):
    """
    A dictionary that loads from a yaml config file.
    """

    def __init__(self, filename: str):
        self.store = dict()
        if os.path.exists(filename):
            filename = os.path.abspath(filename)
            with open(filename, "r") as fp:
                self.store = yaml.load(fp)
                self.store[CONFIG_FILENAME] = filename
                dirname = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "")
                init_logger.info(f"loaded config from {os.path.abspath(filename).replace(dirname, '')}")
        else:
            init_logger.debug(f"no file {filename}")

    def __getitem__(self, key):
        return self.store[self._keytransform(key)]

    def __setitem__(self, key, value):
        self.store[self._keytransform(key)] = value

    def __delitem__(self, key):
        del self.store[self._keytransform(key)]

    def __iter__(self):
        return iter(self.store)

    def __len__(self):
        return len(self.store)

    def _keytransform(self, key) -> str:
        """Allows to alter key to internal hidden name"""
        return key

    def is_valid(self) -> bool:
        return self.store is not None and len(self.store) > 1
