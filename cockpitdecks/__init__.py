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

__NAME__ = "cockpitdecks"
__DESCRIPTION__ = "Elgato Stream Decks, Loupedeck LoupedeckLive, and Berhinger X-Touch Mini to X-Plane Cockpit"
__LICENSE__ = "MIT"
__LICENSEURL__ = "https://mit-license.org"
__COPYRIGHT__ = f"© 2022-{datetime.now().strftime('%Y')} Pierre M <pierre@devleaks.be>"
__version__ = "8.0.14"
__version_info__ = tuple(map(int, __version__.split(".")))
__version_name__ = "production"
__authorurl__ = "https://github.com/devleaks/cockpitdecks"
__documentation_url__ = "https://devleaks.github.io/cockpitdecks-docs/"
#
#
# ##########################################################################

# Prevent aliasing
# https://stackoverflow.com/questions/64716894/ruamel-yaml-disabling-alias-for-dumping
ruamel.yaml.representer.RoundTripRepresenter.ignore_aliases = lambda x, y: True
yaml = YAML(typ="safe", pure=True)

SPAM_LEVEL = 15
SPAM = "SPAM"
LOGFILE = "cockpitdecks.log"
FORMAT = "[%(asctime)s] %(levelname)s %(threadName)s %(filename)s:%(funcName)s:%(lineno)d: %(message)s"
init_logger = logging.getLogger("init/common")


# ##############################################################
# Utility functions
# (mainly unit conversion functions)
#
def now():
    return datetime.now().astimezone()


def to_fl(m, r: int = 10):
    # Convert meters to flight level (1 FL = 100 ft). Round flight level to r if provided, typically rounded to 10, at Patm = 1013 mbar
    fl = m / 30.48
    if r is not None and r > 0:
        fl = r * int(fl / r)
    return fl


def to_m(fl):
    # Convert flight level to meters, at Patm = 1013 mbar
    return round(fl * 30.48)


# ##############################################################
# A few constants and default values
# Adjust with care...
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


class ANNUNCIATOR_STYLES(Enum):
    KORRY = "k"  # k(orry): backlit, glowing
    VIVISUN = "v"  # v(ivisun): bright, sharp.


GLOBAL_DEFAULTS = {
    "cache-icon": True,
    "cockpit-color": "cornflowerblue",
    "cockpit-texture": None,
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
    "cockpit-theme": "light",
    "default-wallpaper": "wallpaper.png",
    "system-font": "Monaco.ttf",  # alias
}

# internals
ID_SEP = "/"


# deckconfig attribute keywords
class KW(Enum):
    ACTION = "action"
    ACTIVATION = "activation"
    ACTIVATIONS = "activations"
    ANNUNCIATOR_MODEL = "model"
    BACKPAGE = "back"
    BUTTONS = "buttons"
    COLORED_LED = "colored-led"
    DATAREF = "dataref"
    DEVICE = "device"
    DISABLED = "disabled"
    DRIVER = "driver"
    ENABLED = "enabled"
    FORMULA = "formula"
    FRAME = "frame"
    GUARD = "guard"
    IMAGE = "image"
    INCLUDES = "includes"
    INDEX = "index"
    INDEX_NUMERIC = "_index"
    LAYOUT = "layout"
    MANAGED = "managed"
    NAME = "name"
    NONE = "none"
    PREFIX = "prefix"
    REPEAT = "repeat"
    REPRESENTATION = "representation"
    REPRESENTATIONS = "representations"
    SERIAL = "serial"
    TYPE = "type"
    VIEW = "feedback"


class Config(MutableMapping):
    """
    A dictionary that loads from a yaml config file.
    """

    def __init__(self, filename: str):
        self.store = dict()
        if os.path.exists(filename):
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

    def _keytransform(self, key):
        return key

    def is_valid(self):
        return self.store is not None and len(self.store) > 1

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
from .cockpit import Cockpit, CockpitBase
