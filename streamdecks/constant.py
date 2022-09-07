"""
Application constants

"""
from enum import Enum

EXCLUDE_DECKS = []  # list serial numbers of deck not usable by Streadecks

CONFIG_DIR = "esdconfig"
CONFIG_FILE = "config.yaml"
RESOURCES_FOLDER = "resources"

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

def make_icon_name(top_txt, top_color, bot_txt, bot_color, bot_framed=False):
    r = [top_txt.upper(), top_color.upper(), bot_txt.upper()]
    if bot_framed:
        r.append("FR")
    r.append(bot_color.upper())
    return "_".join(r)
