"""
Application constants

"""
from enum import Enum

EXCLUDE_DECKS = []  # list serial numbers of deck not usable by Streadecks

CONFIG_DIR = "esdconfig"
CONFIG_FILE = "config.yaml"

DEFAULT_LAYOUT = "default"
INIT_PAGE = "Index"

FONTS_FOLDER = "fonts"
DEFAULT_SYSTEM_FONT = "Monaco.ttf"  # on MacOS
DEFAULT_LABEL_FONT = "DIN.ttf"
DEFAULT_LABEL_SIZE = 12
DEFAULT_LABEL_COLOR = "white"

ICONS_FOLDER = "icons"
DEFAULT_ICON_NAME = "_default_icon.png"
DEFAULT_ICON_COLOR = (0, 0, 150)

DEFAULT_WALLPAPER = "wallpaper.png"
DEFAULT_LOGO = "logo.png"


MONITORING_POLL = 10.0  # seconds, 1.0 = polling every second

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

def convert_color(instr: str):
    if "," in instr:
        a = instr.replace("(", "").replace(")", "").split(",")
        return tuple([int(e) for e in a])
    return instr
