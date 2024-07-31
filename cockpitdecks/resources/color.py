"""
Helper class for color management
"""

import logging
import colorsys
from typing import Tuple

# import numpy as np

from PIL import Image, ImageDraw
from PIL import ImageColor

logger = logging.getLogger(__name__)

TRANSPARENT_PNG_COLOR = (255, 255, 255, 0)  # white
TRANSPARENT_PNG_COLOR_BLACK = (0, 0, 0, 0)  # black-based

DEFAULT_COLOR = (128, 128, 128)
DEFAULT_COLOR_NAME = "grey"


def is_integer(s) -> bool:
    if type(s) is int:
        return True
    if type(s) is str:
        return s.isdigit() or (s.startswith("-") and s[1:].isdigit())
    return False


def convert_color(instr) -> Tuple[int, int, int] | Tuple[int, int, int, int]:
    # process either a color name or a color tuple as a string "(1, 2, 3)"
    # and returns a tuple of 3 or 4 integers in range [0,255].
    # If case of failure to convert, returns middle DEFAULT_COLOR values.
    if instr is None:
        return DEFAULT_COLOR

    if type(instr) in [tuple, list]:
        return tuple(instr)

    if type(instr) != str:
        logger.debug(f"color {instr} ({type(instr)}) not found, using {DEFAULT_COLOR}")
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
            logger.debug(f"fail to convert color {instr} ({type(instr)}), using {DEFAULT_COLOR}")
            color = DEFAULT_COLOR
        return tuple(color)
    logger.debug(f"not a string {instr} ({type(instr)}), using {DEFAULT_COLOR}")
    return DEFAULT_COLOR


def convert_color_hsl(instr) -> Tuple[int, int, int] | Tuple[int, int, int, int]:
    # process either a color name or a color tuple as a string "(1, 2, 3)"
    # and returns a tuple of 3 or 4 integers in range [0,255].
    # If case of failure to convert, returns middle DEFAULT_COLOR values.
    return colorsys.rgb_to_hls(*convert_color(instr)[0:3])


def light_off(color: str | Tuple[int, int, int], lightness: float = 0.10) -> Tuple[int, int, int]:
    # Darkens (or lighten) a color
    if type(color) not in [tuple, list]:
        color = convert_color(color)
    a = list(colorsys.rgb_to_hls(*[c / 255 for c in color]))
    a[1] = lightness
    return tuple([int(c * 256) for c in colorsys.hls_to_rgb(*a)])


def has_ext(name: str, ext: str) -> bool:
    rext = ext if not ext.startswith(".") else ext[1:]  # remove leading period from extension if any
    narr = name.split(".")
    return (len(narr) > 1) and (narr[-1].lower() == rext.lower())


def add_ext(name: str, ext: str) -> str:
    rext = ext if not ext.startswith(".") else ext[1:]  # remove leading period from extension if any
    narr = name.split(".")
    if len(narr) < 2:  # has no extension
        return name + "." + rext
    nameext = narr[-1]
    if nameext.lower() == rext.lower():
        return ".".join(narr[:-1]) + "." + rext  # force extension to what is should
    else:  # did not finish with extention, so add it
        return name + "." + rext  # force extension to what is should


# # https://stackoverflow.com/questions/66837477/pillow-how-to-gradient-fill-drawn-shapes
# # Draw polygon with linear gradient from point 1 to point 2 and ranging
# # from color 1 to color 2 on given image
# def linear_gradient(i, poly, p1, p2, c1, c2):
#     # Draw initial polygon, alpha channel only, on an empty canvas of image size
#     ii = Image.new('RGBA', i.size, (0, 0, 0, 0))
#     draw = ImageDraw.Draw(ii)
#     draw.polygon(poly, fill=(0, 0, 0, 255), outline=None)

#     # Calculate angle between point 1 and 2
#     p1 = np.array(p1)
#     p2 = np.array(p2)
#     angle = np.arctan2(p2[1] - p1[1], p2[0] - p1[0]) / np.pi * 180

#     # Rotate and crop shape
#     temp = ii.rotate(angle, expand=True)
#     temp = temp.crop(temp.getbbox())
#     wt, ht = temp.size

#     # Create gradient from color 1 to 2 of appropriate size
#     gradient = np.linspace(c1, c2, wt, True).astype(np.uint8)
#     gradient = np.tile(gradient, [2 * h, 1, 1])
#     gradient = Image.fromarray(gradient)

#     # Paste gradient on blank canvas of sufficient size
#     temp = Image.new('RGBA', (max(i.size[0], gradient.size[0]),
#                               max(i.size[1], gradient.size[1])), (0, 0, 0, 0))
#     temp.paste(gradient)
#     gradient = temp

#     # Rotate and translate gradient appropriately
#     x = np.sin(angle * np.pi / 180) * ht
#     y = np.cos(angle * np.pi / 180) * ht
#     gradient = gradient.rotate(-angle, center=(0, 0),
#                                translate=(p1[0] + x, p1[1] - y))

#     # Paste gradient on temporary image
#     ii.paste(gradient.crop((0, 0, ii.size[0], ii.size[1])), mask=ii)

#     # Paste temporary image on actual image
#     i.paste(ii, mask=ii)

#     return i


# # Draw polygon with radial gradient from point to the polygon border
# # ranging from color 1 to color 2 on given image
# def radial_gradient(i, poly, p, c1, c2):

#     # Draw initial polygon, alpha channel only, on an empty canvas of image size
#     ii = Image.new('RGBA', i.size, (0, 0, 0, 0))
#     draw = ImageDraw.Draw(ii)
#     draw.polygon(poly, fill=(0, 0, 0, 255), outline=None)

#     # Use polygon vertex with highest distance to given point as end of gradient
#     p = np.array(p)
#     max_dist = max([np.linalg.norm(np.array(v) - p) for v in poly])

#     # Calculate color values (gradient) for the whole canvas
#     x, y = np.meshgrid(np.arange(i.size[0]), np.arange(i.size[1]))
#     c = np.linalg.norm(np.stack((x, y), axis=2) - p, axis=2) / max_dist
#     c = np.tile(np.expand_dims(c, axis=2), [1, 1, 3])
#     c = (c1 * (1 - c) + c2 * c).astype(np.uint8)
#     c = Image.fromarray(c)

#     # Paste gradient on temporary image
#     ii.paste(c, mask=ii)

#     # Paste temporary image on actual image
#     i.paste(ii, mask=ii)

#     return i
