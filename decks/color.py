"""
Helper class for color management
"""
import logging
import colorsys

from PIL import ImageColor

logger = logging.getLogger("Color")

DEFAULT_COLOR = (128, 128, 128)


def is_integer(s):
    if type(s) == int:
        return True
    if type(s) == str:
        return s.isdigit() or (s.startswith('-') and s[1:].isdigit())
    return False

def convert_color(instr):
    # process either a color name or a color tuple as a string "(1, 2, 3)"
    # and returns a tuple of 3 or 4 intergers in range [0,255].
    # If case of failure to convert, returns middle DEFAULT_COLOR values.
    if type(instr) == tuple or type(instr) == list:
        return tuple(instr)

    if type(instr) != str:
        logger.debug(f"convert_color: color {instr} ({type(instr)}) not found, using {DEFAULT_COLOR}")
        return DEFAULT_COLOR

    # it's a string...
    instr = instr.strip()
    if "," in instr and instr.startswith("("):  # "(255, 7, 2)"
        a = instr.replace("(", "").replace(")", "").split(",")
        return tuple([int(e) for e in a])
    else:  # it may be a color name...
        try:
            color = ImageColor.getrgb(instr)
        except ValueError:
            logger.debug(f"convert_color: fail to convert color {instr} ({type(instr)}), using {DEFAULT_COLOR}")
            color = DEFAULT_COLOR
        return color
    logger.debug(f"convert_color: not a string {instr} ({type(instr)}), using {DEFAULT_COLOR}")
    return DEFAULT_COLOR


def light_off(color, lightness: float = 0.10):
    # Darkens (or lighten) a color
    if type(color) not in [tuple, list]:
        color = convert_color(color)
    a = list(colorsys.rgb_to_hls(*[c / 255 for c in color]))
    a[1] = lightness
    return tuple([int(c * 256) for c in colorsys.hls_to_rgb(*a)])


def has_ext(name: str, ext: str):
    rext = ext if not ext.startswith(".") else ext[1:]  # remove leading period from extension if any
    narr = name.split(".")
    return (len(narr) > 1) and (narr[-1].lower() == rext.lower())


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
