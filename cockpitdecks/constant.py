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
DEFAULT_FREQUENCY = 3

# File & folder names
ENVIRON_FILE = "environ.yaml"
CONFIG_FILE = "config.yaml"
SECRET_FILE = "secret.yaml"
OBSERVABLES_FILE = "observables.yaml"

CONFIG_FOLDER = "deckconfig"
RESOURCES_FOLDER = "resources"
FONTS_FOLDER = "fonts"
SOUNDS_FOLDER = "sounds"
ICONS_FOLDER = "icons"
DECKS_FOLDER = "decks"
DECK_TYPES = "types"
DECK_IMAGES = "images"
TYPES_FOLDER = "types"

ASSETS_FOLDER = "assets"
TEMPLATES_FOLDER = "templates"

DEFAULT_LAYOUT = "default"
DEFAULT_PAGE_NAME = "Default Page"

ICON_SIZE = 256  # px
DEFAULT_LABEL_POSITION = "cm"
DEFAULT_LABEL_SIZE = 12
NAMED_COLORS = {}  # name: tuple()

# Virtual decks and web decks
VIRTUAL_DECK_DRIVER = "virtualdeck"
AIRCRAFT_ASSET_PATH = "/aircraft/decks/images/"  # this is an URL path, so forward slash are appropriate
COCKPITDECKS_ASSET_PATH = "/assets/decks/images/"  # this is an URL path

TEMPLATE_FOLDER = os.path.join(os.path.dirname(__file__), DECKS_FOLDER, RESOURCES_FOLDER, TEMPLATES_FOLDER)
ASSET_FOLDER = os.path.join(os.path.dirname(__file__), DECKS_FOLDER, RESOURCES_FOLDER, ASSETS_FOLDER)

AIRCRAFT_CHANGE_MONITORING_DATAREF = "sim/aircraft/view/acf_livery_path"
MONITOR_DATAREF_USAGE = True

# the following extensions are supposed to always be available
# although they strictly are not mandatory for Cockpitdecks to run.
#
COCKPITDECKS_INTERNAL_EXTENSIONS = {
    "cockpitdecks_xp",
    "cockpitdecks_ext",
    "cockpitdecks_wm",
    "cockpitdecks_sd",
    "cockpitdecks_ld",
    "cockpitdecks_bx",
}


class ANNUNCIATOR_STYLES(Enum):
    KORRY = "k"  # k(orry): backlit, glowing
    VIVISUN = "v"  # v(ivisun): bright, sharp.


# internals
ID_SEP = "/"
DEFAULT_ATTRIBUTE_NAME = "default"
DEFAULT_ATTRIBUTE_PREFIX = DEFAULT_ATTRIBUTE_NAME + "-"  # cannot be "", must be at lesat one char
DARK_THEME_NAME = "dark"
DARK_THEME_PREFIX = DARK_THEME_NAME + "-"  # night
LIGHT_THEME_NAME = "light"
LIGHT_THEME_PREFIX = LIGHT_THEME_NAME + "-"  # day
# dusk/dawn?


# environment attributes
class ENVIRON_KW(Enum):
    SIMULATOR_NAME = "SIMULATOR_NAME"
    SIMULATOR_HOST = "SIMULATOR_HOST"
    SIMULATOR_HOME = "SIMULATOR_HOME"
    API_HOST = "API_HOST"
    API_PORT = "API_PORT"
    API_PATH = "API_PATH"
    APP_HOST = "APP_HOST"
    APP_PORT = "APP_PORT"
    COCKPITDECKS_EXTENSION_PATH = "COCKPITDECKS_EXTENSION_PATH"
    COCKPITDECKS_EXTENSION_NAME = "COCKPITDECKS_EXTENSION_NAME"
    COCKPITDECKS_PATH = "COCKPITDECKS_PATH"
    DEBUG = "DEBUG"


# System default values
COCKPITDECKS_DEFAULT_VALUES = {
    "cache-icon": True,
    "system-font": "Monaco.ttf",  # alias
    "cockpit-color": "cornflowerblue",  # there are no default-* for the following three values
    "cockpit-texture": None,
    "cockpit-theme": "light",
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
    ACTIONS = "actions"
    ACTION = "action"
    ANNUNCIATOR_MODEL = "model"
    BACKPAGE = "back"
    BUTTONS = "buttons"
    COCKPIT_THEME = "cockpit-theme"
    COMMAND = "command"
    COMMANDS = "commands"
    CONDITION = "condition"
    DECK = "deck"
    DECKS = "decks"
    DECOR = "decor"
    DELAY = "delay"
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
    INTERNAL_KEY = "_key"
    LABEL = "label"
    LAYOUT = "layout"
    MANAGED = "managed"
    NAME = "name"
    NAMED_COLORS = "named-colors"
    NONE = "none"
    OBSERVABLES = "observables"
    OBSERVABLE = "observable"
    ONCHANGE = "onchange"
    OPTIONS = "options"
    SERIAL = "serial"
    SET_SIM_DATUM = "set-dataref"
    SIM_DATUM = "dataref"
    SIM_DATA = "multi-datarefs"
    STRING_SIM_DATA = "string-datarefs"
    STRING_PREFIX = "string:"
    THEME = "theme"
    TRIGGER = "trigger"
    TYPE = "type"
    VALUE_MIN = "value-min"
    VALUE_MAX = "value-max"
    VALUE_INC = "value-inc"
    VALUE_COUNT = "value-count"
    VIEW = "view"
    VIEW_IF = "view-if"
    WALLPAPER = "wallpaper"
    COCKPITDECKS = "COCKPITDECKS"


class CONFIG_KW_ALIASES(Enum):
    SIM_DATUM = {"dataref", "simvar", "simdata"}
    SIM_DATA = {"multi-datarefs", "multi-simvars", "multi-simdata"}


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
    BACKGROUND_IMAGE_PATH = "background-image-path"
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
    MOSAIC = "mosaic"
    NAME = "name"
    NONE = "none"
    OFFSET = "offset"
    OPTIONS = "options"
    POSITION = "position"
    PREFIX = "prefix"
    RANGE = "range"
    REPEAT = "repeat"
    SPACING = "spacing"
    TILES = "tiles"


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


#
# Flight Phases
#
FLIGHT_PHASE_ECAM = [
    "OFF",  # 0
    "ELEC POWER",
    "FIRST ENG STARTED",
    "FIRST ENG TO POWER",
    "80KT",
    "LIFT OFF",
    "1500 FT",
    "800 FT",
    "TOUCHDOWN",
    "80KT",
    "2ND ENG SHUTDOWN",
    "5 MIN AFTER",  # 10
]

FLIGHT_PHASE_QPAC = [
    "OFF",  # 0
    "ELEC POWER",
    "SECOND ENGINE START",
    "FIRST ENG T.O. POWER",
    "70KT",
    "LIFT OFF",
    "LIST OFF + 1 MINUTE OR 400FT",
    "1000FT",
    "1000FT",
    "400FT",
    "TOUCH DOWN",
    "70KT",
    "FIRST ENG SHUTDOWN",
    "5 MINUTES AFTER SECOND ENG SHUT DOWN",  # 13
]

# ############################################################
#
# Prevent aliasing
# https://stackoverflow.com/questions/64716894/ruamel-yaml-disabling-alias-for-dumping
ruamel.yaml.representer.RoundTripRepresenter.ignore_aliases = lambda x, y: True

yaml = YAML(typ="safe", pure=True)
yaml.default_flow_style = False

init_logger = logging.getLogger("init/common")
init_logger.setLevel(logging.WARNING)

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
            dirname = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "")
            try:
                with open(filename, "r") as fp:
                    self.store = yaml.load(fp)
                    self.store[CONFIG_FILENAME] = filename
                    init_logger.info(f"loaded config from {os.path.abspath(filename).replace(dirname, '')}")
            except:
                self.store[CONFIG_FILENAME] = filename
                init_logger.warning(f"error loading config from {os.path.abspath(filename).replace(dirname, '')}", exc_info=True)
        else:
            init_logger.warning(f"no file {filename}")

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
        return self.store is not None and len(self.store) > 1  # because there always is self.store[CONFIG_FILENAME]
