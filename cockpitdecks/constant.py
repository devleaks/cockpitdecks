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
#
VIRTUAL_DECK_DRIVER = "virtualdeck"
AIRCRAFT_ASSET_PATH = "/aircraft/decks/images/"  # this is an URL path, so forward slash are appropriate
COCKPITDECKS_ASSET_PATH = "/assets/decks/images/"  # this is an URL path

TEMPLATE_FOLDER = os.path.join(os.path.dirname(__file__), DECKS_FOLDER, RESOURCES_FOLDER, TEMPLATES_FOLDER)
ASSET_FOLDER = os.path.join(os.path.dirname(__file__), DECKS_FOLDER, RESOURCES_FOLDER, ASSETS_FOLDER)


# Mostly common X-Plane simulator variables
# of general interest
# Used to determine Cockpitdecks behavior
#
AIRCRAFT_PATH_VARIABLE = "sim/aircraft/view/acf_relative_path"
AIRCRAFT_ICAO_VARIABLE = "sim/aircraft/view/acf_ICAO"
LIVERY_PATH_VARIABLE = "sim/aircraft/view/acf_livery_path"
LIVERY_INDEX_VARIABLE = "sim/aircraft/view/acf_livery_index"

RELOAD_ON_LIVERY_CHANGE = False  # we only reload on AIRCRAFT_PATH_VARIABLE change
RELOAD_ON_ICAO_CHANGE = False  # we only reload on AIRCRAFT_PATH_VARIABLE change


# Rendez-vous Internal Variables
#
AIRCRAFT_CHANGE_MONITORING = "aircraft-name"
AIRCRAFT_ICAO_MONITORING = "aircraft-icao"
LIVERY_CHANGE_MONITORING = "livery-name"
WEATHER_STATION_MONITORING = "weather-station"
DAYTIME = "daytime"
LIVERY_INDEX_MONITORING = "livery-index"


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
MONITOR_RESOURCE_USAGE = True


# environment attributes
class ENVIRON_KW(Enum):
    API_HOST = "API_HOST"
    API_PATH = "API_PATH"
    API_PORT = "API_PORT"
    API_VERSION = "API_VERSION"
    APP_HOST = "APP_HOST"
    APP_PORT = "APP_PORT"
    COCKPITDECKS_EXTENSION_NAME = "COCKPITDECKS_EXTENSION_NAME"
    COCKPITDECKS_EXTENSION_PATH = "COCKPITDECKS_EXTENSION_PATH"
    COCKPITDECKS_PATH = "COCKPITDECKS_PATH"
    DEBUG = "DEBUG"
    MODE = "mode"
    SIMULATOR_HOME = "SIMULATOR_HOME"
    SIMULATOR_HOST = "SIMULATOR_HOST"
    SIMULATOR_NAME = "SIMULATOR_NAME"
    VERBOSE = "verbose"


# "System" default values
# "Cockpitdecks-level" default values
# Please handle with care, might break entire system. You're warned.
COCKPITDECKS_DEFAULT_VALUES = {
    "cache-icon": True,
    "system-font": "Monaco.ttf",  # alias
    "cockpit-color": "cornflowerblue",  # there are no default-* for the following three values, just cockpit-* values
    "cockpit-texture": None,  # in other words, cockpit-* values ARE cockpitdecks-level, global default values.
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
    ACTION = "action"
    ACTIONS = "actions"
    ANNUNCIATOR_MODEL = "model"
    BACKPAGE = "back"
    BEGIN_END = "begin-end-command"  # pressed, execution remains while pressed, then released
    BUTTONS = "buttons"
    COCKPIT_THEME = "cockpit-theme"
    COCKPITDECKS = "COCKPITDECKS"
    COMMAND = "command"
    COMMANDS = "commands"
    CONDITION = "condition"
    DATA_TYPE = "data-type"
    DECK = "deck"
    DECKS = "decks"
    DECOR = "decor"
    DEFAULT_VALUE = "default-value"
    DELAY = "delay"
    DEVICE = "device"
    DISABLE = "disable"
    DISABLED = "disabled"
    DRIVER = "driver"
    ENABLE = "enable"
    ENABLED = "enabled"
    EVENT = "event"
    EVENTS = "events"
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
    LONG_PRESS = "long-press"  # pressed for a long time, action triggers on release
    MANAGED = "managed"
    NAME = "name"
    NAMED_COLORS = "named-colors"
    NONE = "none"
    OBSERVABLE = "observable"
    OBSERVABLES = "observables"
    ONCHANGE = "onchange"
    OPTIONS = "options"
    PAGE = "page"
    SERIAL = "serial"
    SET_SIM_VARIABLE = "set-dataref"
    SIM_VARIABLE = "dataref"
    TEXT = "text"
    THEME = "theme"
    TOGGLE = "toggle"
    TRIGGER = "trigger"
    TYPE = "type"
    VALUE_COUNT = "value-count"
    VALUE_INC = "value-inc"
    VALUE_MAX = "value-max"
    VALUE_MIN = "value-min"
    VIEW = "view"
    VIEW_IF = "view-if"
    WALLPAPER = "wallpaper"


class CONFIG_KW_ALIASES(Enum):
    SIM_VARIABLE = {"dataref", "simvar", "simdata"}
    SET_VARIABLE = {"set-dataref", "set-simvar"}
    INSTRUCTION = {"command", "view", "begin-end", "instruction"}
    FORMULA = {"formula", "condition", "view-if"}


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
    LONGPRESS = "longpress"  # triggered automatically by Elgato firmwire, ONE event only (when pressed/touched) for more than ~0.5 sec
    PUSH = "push"  # TWO events, pressed and released
    ENCODER = "encoder"  # turn with clicks or stops, either clockwise and/or counter-clockwise
    CURSOR = "cursor"  # continuous value between range
    SWIPE = "swipe"  # several events from touch (one event) to swipe (two events), each event has position and timing


# deck type feedback capabilities
#
class DECK_FEEDBACK(Enum):
    NONE = "none"
    COLORED_LED = "colored-led"  # color and/or intensite
    IMAGE = "image"  # width and height, assumed RGB
    LED = "led"  # just on or off
    ENCODER_LEDS = "encoder-leds"  # specific to X-Touch mini, a "ramp" of LEDs
    VIBRATE = "vibrate"  # emit vibration or non chgeable sound/beep
    SOUND = "sound"  # play a sound (short wav/mp3 file)


# ############################################################
#
# Prevent aliasing
# https://stackoverflow.com/questions/64716894/ruamel-yaml-disabling-alias-for-dumping
ruamel.yaml.representer.RoundTripRepresenter.ignore_aliases = lambda x, y: True

yaml = YAML(typ="safe", pure=True)
yaml.default_flow_style = False

init_logger = logging.getLogger(__name__)
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
        if filename is not None:
            if os.path.exists(filename):
                filename = os.path.abspath(filename)
                dirname = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "")
                try:
                    with open(filename, "r") as fp:
                        self.store = yaml.load(fp)
                        init_logger.info(f"loaded config from {os.path.abspath(filename).replace(dirname, '')}")
                    self.store[CONFIG_FILENAME] = filename
                except:
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

    def filename(self) -> str | None:
        return self.store.get(CONFIG_FILENAME)

    def from_filename(self) -> bool:
        return self.filename() is not None and self.filename() != ""
