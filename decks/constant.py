"""
Application constants

"""
from enum import Enum

EXCLUDE_DECKS = []  # list serial numbers of deck not usable by Streadecks

CONFIG_DIR = "deckconfig"
CONFIG_FILE = "config.yaml"
SERIAL_FILE = "secret.yaml"
RESOURCES_FOLDER = "resources"

DEFAULT_LAYOUT = "default"
INIT_PAGE = "Index"
DEFAULT_PAGE_NAME = "X-Plane"

FONTS_FOLDER = "fonts"
DEFAULT_SYSTEM_FONT = "Monaco.ttf"  # on MacOS
DEFAULT_LABEL_FONT = "DIN.ttf"
DEFAULT_LABEL_SIZE = 12
DEFAULT_LABEL_COLOR = "white"

ICONS_FOLDER = "icons"
DEFAULT_ICON_NAME = "_default_icon.png"
DEFAULT_ICON_COLOR = (0, 0, 100)

DEFAULT_WALLPAPER = "wallpaper.png"
DEFAULT_LOGO = "logo.png"

UDP_PORT = 49000

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

def convert_color(instr):
    # convert a string (1, 2, 3) to a tuple of integers.
    # (Could be extended and generalized with ast.literal_eval...)
    if type(instr) != str:
        return instr  # (255, 7, 2)
    if "," in instr:  # "(255, 7, 2)"
        a = instr.replace("(", "").replace(")", "").split(",")
        return tuple([int(e) for e in a])
    return instr  # white, blue...

def make_icon_name(top_txt, top_color, bot_txt, bot_color, bot_framed=False):
    r = [top_txt.upper(), top_color.upper(), bot_txt.upper()]
    if bot_framed:
        r.append("FR")
    r.append(bot_color.upper())
    return "_".join(r)

# #############################################################
# Constants for Loupedeck Live
#
BIG_ENDIAN = "big"
WS_UPGRADE_HEADER = b"""GET /index.html
HTTP/1.1
Connection: Upgrade
Upgrade: websocket
Sec-WebSocket-Key: 123abc

"""
WS_UPGRADE_RESPONSE = 'HTTP/1.1'

# Various constants used by the Loupedeck firmware

# Maximum brightness value
MAX_BRIGHTNESS = 10
LIGHT_OFF_BRIGHTNESS = 10  # pct

# How long until trying to reconnect after a disconnect
RECONNECT_INTERVAL = 3000

# How long without ticks until a connection is considered "timed out"
CONNECTION_TIMEOUT = 3000

# Actions and response identifications
HEADERS = {
    "CONFIRM": 0x0302,
    "SERIAL_OUT": 0x0303,
    "VERSION_OUT": 0x0307,
    "TICK": 0x0400,
    "SET_BRIGHTNESS": 0x0409,
    "CONFIRM_FRAMEBUFF": 0x0410,
    "SET_VIBRATION": 0x041b,
    "BUTTON_PRESS": 0x0500,
    "KNOB_ROTATE": 0x0501,
    "RESET": 0x0506,
    "DRAW": 0x050f,
    "SET_COLOR": 0x0702,
    "TOUCH": 0x094d,
    "TOUCH_END": 0x096d,
    "VERSION_IN": 0x0c07,
    "MCU": 0x180d,
    "SERIAL_IN": 0x1f03,
    "WRITE_FRAMEBUFF": 0xff10
}

# Button names
BUTTONS = {
    0x01: 'knobTL',
    0x02: 'knobCL',
    0x03: 'knobBL',
    0x04: 'knobTR',
    0x05: 'knobCR',
    0x06: 'knobBR',
    0x07: 'circle',
    0x08: '1',
    0x09: '2',
    0x0a: '3',
    0x0b: '4',
    0x0c: '5',
    0x0d: '6',
    0x0e: '7'
}

# Displays
DISPLAYS = {
    "center": { "id": bytes('\x00A'.encode("ascii")), "width": 360, "height": 270 }, # "A"
    "left":   { "id": bytes('\x00L'.encode("ascii")), "width": 60,  "height": 270 }, # "L"
    "right":  { "id": bytes('\x00R'.encode("ascii")), "width": 60,  "height": 270 }, # "R"
}

# Haptic feedbacks
HAPTIC = {
    "SHORT": 0x01,
    "MEDIUM": 0x0a,
    "LONG": 0x0f,
    "LOW": 0x31,
    "SHORT_LOW": 0x32,
    "SHORT_LOWER": 0x33,
    "LOWER": 0x40,
    "LOWEST": 0x41,
    "DESCEND_SLOW": 0x46,
    "DESCEND_MED": 0x47,
    "DESCEND_FAST": 0x48,
    "ASCEND_SLOW": 0x52,
    "ASCEND_MED": 0x53,
    "ASCEND_FAST": 0x58,
    "REV_SLOWEST": 0x5e,
    "REV_SLOW": 0x5f,
    "REV_MED": 0x60,
    "REV_FAST": 0x61,
    "REV_FASTER": 0x62,
    "REV_FASTEST": 0x63,
    "RISE_FALL": 0x6a,
    "BUZZ": 0x70,
    "RUMBLE5": 0x77, # lower frequencies in descending order
    "RUMBLE4": 0x78,
    "RUMBLE3": 0x79,
    "RUMBLE2": 0x7a,
    "RUMBLE1": 0x7b,
    "VERY_LONG": 0x76, # 10 sec high freq (!)
}


# ################################
# AIRBUS_DEFAULTS
#
AIRBUS_DEFAULTS = {                     # May be externalized (constant) one day...
    "background": (94, 111, 130),       # Button frame color, light blueish airbus dashboard. Needs tuning.
    "color": (20, 20, 20),              # Button background color
    "blurr": 16,
    "title": {                          # This is printed on top of the button
        "font": "DIN.ttf",
        "size": 42,                     # ~3/16
        "color": "white"
    },
    "display": {                        # This is what is display on the button, text or LED for now
        "font": "DIN Bold.ttf",
        "size": 64,                     # 4/16
        "color": (0, 0, 220)
    },
    "dual": {                           # This is what is printed on the button
        "font": "DIN Bold.ttf",
        "size": 80,                     # 5/16
        "color": "deepskyblue"
    }
}


AIRBUS_DEFAULTS_STREAMDECK = {                     # May be externalized (constant) one day...
    "background": (94, 111, 130),       # Button frame color, light blueish airbus dashboard. Needs tuning.
    "color": (20, 20, 20),              # Button background color
    "blurr": 16,
    "title": {                          # This is printed on top of the button
        "font": "DIN.ttf",
        "size": 42,                     # ~3/16
        "color": "white"
    },
    "display": {                        # This is what is display on the button, text or LED for now
        "font": "DIN Bold.ttf",
        "size": 64,                     # 4/16
        "color": (0, 0, 220)
    },
    "dual": {                           # This is what is printed on the button
        "font": "DIN Bold.ttf",
        "size": 80,                     # 5/16
        "color": "deepskyblue"
    }
}

AIRBUS_DEFAULTS_LOUPEDECK = {                     # May be externalized (constant) one day...
    "background": (94, 111, 130),       # Button frame color, light blueish airbus dashboard. Needs tuning.
    "color": (20, 20, 20),              # Button background color
    "blurr": 16,
    "title": {                          # This is printed on top of the button
        "font": "DIN.ttf",
        "size": 42,                     # ~3/16
        "color": "white"
    },
    "display": {                        # This is what is display on the button, text or LED for now
        "font": "DIN Bold.ttf",
        "size": 64,                     # 4/16
        "color": (0, 0, 220)
    },
    "dual": {                           # This is what is printed on the button
        "font": "DIN Bold.ttf",
        "size": 80,                     # 5/16
        "color": "deepskyblue"
    }
}

AIRBUS_DEFAULTS_ALL = {
    "streamdeck": AIRBUS_DEFAULTS_STREAMDECK,
    "loupedeck": AIRBUS_DEFAULTS_LOUPEDECK
}
