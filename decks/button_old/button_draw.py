# ###########################
# Button with Drawing Rendering rather than icons.
#
import logging
import threading
import time
import colorsys

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter, ImageColor
from mergedeep import merge

from .button_core import Button
from .rpc import RPC

logger = logging.getLogger("DrawButton")
# logger.setLevel(logging.DEBUG)


class DrawButton(Button):

    def __init__(self, config: dict, page: "Page"):
        Button.__init__(self, config=config, page=page)
