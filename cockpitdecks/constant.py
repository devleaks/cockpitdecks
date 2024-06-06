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
from datetime import datetime
import ruamel
from ruamel.yaml import YAML

from .network import *


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

# Files
CONFIG_FOLDER = "deckconfig"
CONFIG_FILE = "config.yaml"
SECRET_FILE = "secret.yaml"

DEFAULT_LAYOUT = "default"
DEFAULT_PAGE_NAME = "X-Plane"

RESOURCES_FOLDER = "resources"
FONTS_FOLDER = "fonts"
ICONS_FOLDER = "icons"
DECKS_FOLDER = "decks"

ICON_SIZE = 256  # px

# Virtual decks and web decks
VIRTUAL_DECK_DRIVER = "virtualdeck"

class ANNUNCIATOR_STYLES(Enum):
    KORRY = "k"  # k(orry): backlit, glowing
    VIVISUN = "v"  # v(ivisun): bright, sharp.


COCKPITDECKS_DEFAULT_VALUES = {
    "cache-icon": True,
    "cockpit-color": "cornflowerblue",
    "cockpit-texture": None,
    "cockpit-theme": "light",
    "default-annunciator-color": "black",
    "default-annunciator-style": ANNUNCIATOR_STYLES.VIVISUN,
    "default-annunciator-texture": None,
    "default-home-page-name": "index",
    "default-icon-color": "cornflowerblue",
    "default-icon-name": "1.png",
    "default-icon-texture": None,
    "default-interface-bg-color": "black",
    "default-interface-fg-color": "white",
    "default-label-color": "white",
    "default-label-font": "DIN.ttf",
    "default-label-position": "ct",
    "default-label-size": 10,
    "default-light-off-intensity": 10,
    "default-logo": "logo.png",
    "default-system-font": "Monaco.ttf",
    "default-text-color": "white",
    "default-text-font": "DIN.ttf",
    "default-text-position": "cm",
    "default-text-size": 32,
    "default-wallpaper": "wallpaper.png",
    "system-font": "Monaco.ttf",  # alias
}

# internals
ID_SEP = "/"


# deckconfig attribute keywords
#
# Config.yaml
#
class CONFIG_KW(Enum):
    ADDRESS = "address"  # could be host, hostname
    ANNUNCIATOR_MODEL = "model"
    BACKPAGE = "back"
    BUTTONS = "buttons"
    DATAREF = "dataref"
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
    LAYOUT = "layout"
    MANAGED = "managed"
    NAME = "name"
    NONE = "none"
    PORT = "port"
    SERIAL = "serial"
    STRING_DATAREFS = "string-datarefs"
    TYPE = "type"
    VIEW = "view"


#
# Deck.yaml (decks/resources/*.yaml)
#
class DECK_KW(Enum):
    ACTION = "action"
    BUTTONS = "buttons"
    DRIVER = "driver"
    FEEDBACK = "feedback"
    IMAGE = "image"
    LAYOUT = "layout"
    NAME = "name"
    NONE = "none"
    PREFIX = "prefix"
    RANGE = "range"
    REPEAT = "repeat"
    TYPE = "type"


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

init_logger = logging.getLogger("init/common")


#
#  Yaml config file reader
#
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
                self.store["__filename__"] = filename
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
