# ##########################################################################
#
# C O C K P I T D E C K S
#
# Elgato Streamdeck, Loupedeck LoupedeckLive, and Berhinger X-Touch Mini to X-Plane Cockpit.
#
#
import os
import logging
from collections.abc import MutableMapping
from enum import Enum
from datetime import datetime
import ruamel
from ruamel.yaml import YAML

__NAME__ = "cockpitdecks"
__DESCRIPTION__ = "Elgato Streamdeck, Loupedeck LoupedeckLive, and Berhinger X-Touch Mini to X-Plane Cockpit"
__LICENSE__ = "MIT"
__LICENSEURL__ = "https://mit-license.org"
__COPYRIGHT__ = f"© 2022-{datetime.now().strftime('%Y')} Pierre M <pierre@devleaks.be>"
__version__ = "7.9.6"
__version_info__ = tuple(map(int, __version__.split(".")))
__version_name__ = "development"
__authorurl__ = "https://github.com/devleaks/cockpitdecks"
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
FORMAT = "[%(asctime)s] p%(process)s %(levelname)s {%(filename)s:%(funcName)s:%(lineno)d}: %(message)s"
# logging.basicConfig(level=logging.INFO, format=FORMAT)
logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)
# if LOGFILE is not None:
#     formatter = logging.Formatter(FORMAT)
#     handler = logging.FileHandler(
#         LOGFILE, mode="a"
#     )
#     handler.setFormatter(formatter)
#     logger.addHandler(handler)


# ##############################################################
# Utility functions
# (mainly unit conversion functions)
#
def now():
    return datetime.now().astimezone()


def to_fl(m, r: int = None):
    # Convert meters to flight level (1 FL = 100 ft). Round flight level to r if provided.
    ft = m * 0.03048
    if r is not None and r > 0:
        ft = r * int(ft / r)
    return ft


def to_m(fl):
    # Convert flight level to meters
    return round(fl * 30, 48)


# ##############################################################
# A few constants and default values
# Adjust with care...
#
# ROOT_DEBUG = "cockpitdecks.xplaneudp,cockpitdecks.xplane,cockpitdecks.button"
ROOT_DEBUG = ""
EXCLUDE_DECKS = []  # list serial numbers of deck not usable by Streadecks

# Files
CONFIG_FOLDER = "deckconfig"
CONFIG_FILE = "config.yaml"
SECRET_FILE = "secret.yaml"

DEFAULT_AIRCRAFT = "AIRCRAFT"

RESOURCES_FOLDER = "resources"

DEFAULT_WALLPAPER = "wallpaper.png"
DEFAULT_LOGO = "logo.png"

DEFAULT_LAYOUT = "default"
HOME_PAGE = "index"
DEFAULT_PAGE_NAME = "X-Plane"

# Fonts
FONTS_FOLDER = "fonts"
DEFAULT_SYSTEM_FONT = "Monaco.ttf"  # on MacOS, if above not found

DEFAULT_LABEL_FONT = "DIN.ttf"
DEFAULT_LABEL_SIZE = 10
DEFAULT_LABEL_COLOR = "white"
DEFAULT_LABEL_POSITION = "ct"

# Icons
ICONS_FOLDER = "icons"
ICON_SIZE = 256  # px
DEFAULT_ICON_NAME = "_default_icon.png"
DEFAULT_ICON_COLOR = (0, 0, 100)
DEFAULT_ICON_TEXTURE = None
DEFAULT_ANNUNCIATOR_COLOR = (0, 0, 0)

# Decor, colors
COCKPIT_COLOR = (94, 111, 130)  # tuple (r, g, b) or string of PILLOW color name
COCKPIT_TEXTURE = None

DEFAULT_LIGHT_OFF_INTENSITY = 10  # %

# internals
ID_SEP = "/"


class ANNUNCIATOR_STYLES(Enum):
    KORRY = "k"  # k(orry): backlit, glowing
    VIVISUN = "v"  # v(ivisun): bright, sharp.


DEFAULT_ANNUNCIATOR_STYLE = ANNUNCIATOR_STYLES.KORRY


# deckconfig attribute keywords
class KW(Enum):
    ACTION = "action"
    ACTIVATIONS = "activations"
    ANNUNCIATOR_MODEL = "model"
    BACKPAGE = "back"
    BUTTONS = "buttons"
    COLORED_LED = "colored-led"
    DATAREF = "dataref"
    FORMULA = "formula"
    FRAME = "frame"
    GUARD = "guard"
    IMAGE = "image"
    INCLUDES = "includes"
    INDEX = "index"
    INDEX_NUMERIC = "_index"
    MANAGED = "managed"
    MODEL = "model"
    NAME = "name"
    NONE = "none"
    PREFIX = "prefix"
    REPEAT = "repeat"
    REPRESENTATIONS = "representations"
    VIEW = "view"


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
                logger.debug(f"loaded config from {filename}")
        else:
            logger.debug(f"no file {filename}")

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


from .cockpit import Cockpit, CockpitBase
from .simulators.xplane import XPlane
