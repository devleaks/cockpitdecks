"""
Application constants

"""
from enum import Enum

CONFIG_DIR = "esdconfig"
CONFIG_FILE = "config.yaml"

ICONS_FOLDER = "icons"
FONTS_FOLDER = "fonts"

DEFAULT_LAYOUT = "default"

INIT_PAGE = "Index"
WALLPAPER = "wallpaper.png"

DEFAULT_SYSTEM_FONT = "arial.ttf"

DEFAULT_LABEL_FONT = "DIN.ttf"
DEFAULT_LABEL_SIZE = "12"

class STREAM_DECK_MODEL(Enum):
    STREAM_DECK_XL = 0
    STREAM_DECK = 1
    STREAM_DECK_MK_2 = 2
    STREAM_DECK_MINI = 3
    STREAM_DECK_PEDAL = 4
