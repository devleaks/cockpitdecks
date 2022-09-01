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

DEFAULT_SYSTEM_FONT = "Helvetica.ttf"  # on MacOS

DEFAULT_LABEL_FONT = "DIN.ttf"
DEFAULT_LABEL_SIZE = "12"

MONITORING_POLL = 10.0  # seconds, 1.0 = polling every second

class STREAM_DECK_MODEL(Enum):
    STREAM_DECK_XL = 0
    STREAM_DECK = 1
    STREAM_DECK_MK_2 = 2
    STREAM_DECK_MINI = 3
    STREAM_DECK_PEDAL = 4

def add_ext(name: str, ext: str):
    rext = ext if not ext.startswith(".") else ext[1:]  # remove leading period from extension if any
    narr = name.split(".")
    if len(narr) < 2:  # has no extension
        return name + "." + rext
    nameext = narr[-1]
    if nameext.lower() == rext.lower():
        return ".".join(narr[:-1]) + "." + rext  # force extension to what is should
    else:  # did not finish with extention, so add it
        return name + "." + rext  # force extension to what is should

def has_ext(name: str, ext: str):
    rext = ext if not ext.startswith(".") else ext[1:]  # remove leading period from extension if any
    narr = name.split(".")
    return (len(narr) > 1) and (narr[-1].lower() == rext.lower())
