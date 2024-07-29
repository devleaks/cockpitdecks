# ###########################
# Buttons that are drawn on render()
#
import logging
import math
from random import randint
from enum import Enum

from PIL import Image, ImageDraw

from cockpitdecks import ICON_SIZE
from cockpitdecks.resources.iconfonts import ICON_FONTS

from cockpitdecks.resources.color import TRANSPARENT_PNG_COLOR, convert_color, light_off
from .icon import IconBase  # explicit Icon from file to avoid circular import

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


#
# ###############################
# DRAWN REPRESENTATION (using Pillow)
#
#
class DrawBase(IconBase):

    REPRESENTATION_NAME = "draw-base"

    def __init__(self, button: "Button"):
        IconBase.__init__(self, button=button)

        self.icon_texture = self._config.get("icon-texture", None)
        self.icon_color = self._config.get("icon-color", None)
        self.cockpit_texture = self._config.get("cockpit-texture", self.button.get_attribute("cockpit-texture"))
        self.cockpit_color = self._config.get("cockpit-color", self.button.get_attribute("cockpit-color"))

        # Reposition for move_and_send()
        self.draw_scale = float(self._config.get("scale", 1))
        if self.draw_scale < 0.5 or self.draw_scale > 2:
            logger.warning(f"button {self.button.name}: invalid scale {self.draw_scale}, must be in interval [0.5, 2]")
            self.draw_scale = 1
        self.draw_left = self._config.get("left", 0) - self._config.get("right", 0)
        self.draw_up = self._config.get("up", 0) - self._config.get("down", 0)

    def double_icon(self, width: int = ICON_SIZE * 2, height: int = ICON_SIZE * 2):
        """Or any size icon, default is to double ICON_SIZE to allow for room around center."""
        image = Image.new(mode="RGBA", size=(width, height), color=TRANSPARENT_PNG_COLOR)
        draw = ImageDraw.Draw(image)
        return image, draw

    def move_and_send(self, image):
        # 1. Scale whole drawing if requested
        if self.draw_scale != 1:
            l = int(image.width * self.draw_scale)
            image = image.resize((l, l))
        # 2a. Move whole drawing around
        a = 1
        b = 0
        c = self.draw_left
        d = 0
        e = 1
        f = self.draw_up
        if c != 0 or f != 0:
            image = image.transform(image.size, Image.AFFINE, (a, b, c, d, e, f))
        # 2b. Crop center to ICON_SIZExICON_SIZE
        cl = image.width / 2 - ICON_SIZE / 2
        ct = image.height / 2 - ICON_SIZE / 2
        image = image.crop((cl, ct, cl + ICON_SIZE, ct + ICON_SIZE))

        # 3. Paste image on cockpit background and return it.
        bg = self.button.deck.get_icon_background(
            name=self.button_name(),
            width=ICON_SIZE,
            height=ICON_SIZE,
            texture_in=self.cockpit_texture,
            color_in=self.cockpit_color,
            use_texture=True,
            who="Annunciator",
        )
        bg.alpha_composite(image)
        return bg

    def graphic_default(self, attribute, default=None):
        dflt = self.button.deck.cockpit.defaults_prefix()
        attrname = f"{dflt}{attribute}"
        value = self.button.get_attribute(attrname)
        if value is None:
            logger.debug(f"no default value {attrname}, using hardcoded default")
        return value if value is not None else default


#
# ###############################
# SWITCH BUTTON REPRESENTATION
#
#
DECOR = {
    "A": "corner upper left",
    "B": "straight horizontal",
    "C": "corner upper right",
    "D": "corner lower left",
    "E": "corner lower right",
    "F": "straight vertical",
    "G": "cross",
    "+": "cross",
    "H": "cross over horizontal",
    "I": "straight vertical",
    "J": "cross over vertical",
    "K": "T",
    "T": "T",
    "L": "T invert",
    "M": "T left",
    "N": "T right",
}


class Decor(DrawBase):

    REPRESENTATION_NAME = "decor"

    def __init__(self, button: "Button"):
        DrawBase.__init__(self, button=button)

        self.decor = self._config.get("decor")

        if self.decor is None:
            logger.warning("no decor configuration")
            return

        self.type = self.decor.get("type", "line")
        self.code = self.decor.get("code", "")
        self.decor_width_horz = 10
        self.decor_width_vert = 10
        decor_width = self.decor.get("width")  # now accepts two width 10/20, for horizontal and/ vertical lines
        if decor_width is not None:
            a = str(decor_width).split("/")
            if len(a) > 1:
                self.decor_width_horz = int(a[0])
                self.decor_width_vert = int(a[1])
            else:
                self.decor_width_horz = int(decor_width)
                self.decor_width_vert = int(decor_width)
        self.decor_color = self.decor.get("color", "lime")
        self.decor_color = convert_color(self.decor_color)

    def get_image_for_icon(self):
        def draw_segment(d, code):
            # From corners 1
            if "A" in code:
                d.line(
                    [(0, 0), (ICON_SIZE - r, ICON_SIZE - r)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
            if "C" in code:
                d.line(
                    [(ICON_SIZE + r, ICON_SIZE - r), (FULL_WIDTH, 0)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
            if "R" in code:
                d.line(
                    [(ICON_SIZE - r, ICON_SIZE + r), (0, FULL_HEIGHT)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
            if "T" in code:
                d.line(
                    [(ICON_SIZE + r, ICON_SIZE + r), (FULL_WIDTH, FULL_HEIGHT)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
            # From corners 2
            if "D" in code:
                d.line(
                    [(ICON_SIZE - r, ICON_SIZE - r), (ICON_SIZE - s, ICON_SIZE - s)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
            if "E" in code:
                d.line(
                    [(ICON_SIZE + s, ICON_SIZE - s), (ICON_SIZE + r, ICON_SIZE - r)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
            if "P" in code:
                d.line(
                    [(ICON_SIZE - r, ICON_SIZE + r), (ICON_SIZE - s, ICON_SIZE + s)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
            if "Q" in code:
                d.line(
                    [(ICON_SIZE + s, ICON_SIZE + s), (ICON_SIZE + r, ICON_SIZE + r)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
            # From corners 3
            if "A" in code:
                d.line(
                    [(ICON_SIZE - r, ICON_SIZE - r), (ICON_SIZE, ICON_SIZE)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
            if "C" in code:
                d.line(
                    [(ICON_SIZE, ICON_SIZE), (ICON_SIZE + r, ICON_SIZE - r)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
            if "R" in code:
                d.line(
                    [(ICON_SIZE - r, ICON_SIZE + r), (ICON_SIZE, ICON_SIZE)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
            if "T" in code:
                d.line(
                    [(ICON_SIZE, ICON_SIZE), (ICON_SIZE + r, ICON_SIZE + r)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
            # Horizontal bars
            if "I" in code:
                d.line(
                    [(0, ICON_SIZE), (ICON_SIZE - r, ICON_SIZE)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
            if "J" in code:
                d.line(
                    [(ICON_SIZE - r, ICON_SIZE), (ICON_SIZE, ICON_SIZE)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
            if "K" in code:
                d.line(
                    [(ICON_SIZE, ICON_SIZE), (ICON_SIZE + r, ICON_SIZE)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
            if "L" in code:
                d.line(
                    [(ICON_SIZE + r, ICON_SIZE), (FULL_WIDTH, ICON_SIZE)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
            # Vertical bars
            if "B" in code:
                d.line(
                    [(ICON_SIZE, 0), (ICON_SIZE, ICON_SIZE - r)],
                    fill=self.decor_color,
                    width=self.decor_width_vert,
                )
            if "G" in code:
                d.line(
                    [(ICON_SIZE, ICON_SIZE - r), (ICON_SIZE, ICON_SIZE)],
                    fill=self.decor_color,
                    width=self.decor_width_vert,
                )
            if "N" in code:
                d.line(
                    [(ICON_SIZE, ICON_SIZE), (ICON_SIZE, ICON_SIZE + r)],
                    fill=self.decor_color,
                    width=self.decor_width_vert,
                )
            if "S" in code:
                d.line(
                    [(ICON_SIZE, ICON_SIZE + r), (ICON_SIZE, FULL_HEIGHT)],
                    fill=self.decor_color,
                    width=self.decor_width_vert,
                )
            # Circle
            if "0" in code:
                d.arc(
                    tl + br,
                    start=180,
                    end=225,
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
            if "1" in code:
                d.arc(
                    tl + br,
                    start=225,
                    end=270,
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
            if "2" in code:
                d.arc(
                    tl + br,
                    start=270,
                    end=315,
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
            if "3" in code:
                d.arc(
                    tl + br,
                    start=315,
                    end=0,
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
            if "4" in code:
                d.arc(
                    tl + br,
                    start=0,
                    end=45,
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
            if "6" in code:
                d.arc(
                    tl + br,
                    start=45,
                    end=90,
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
            if "6" in code:
                d.arc(
                    tl + br,
                    start=90,
                    end=135,
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
            if "7" in code:
                d.arc(
                    tl + br,
                    start=135,
                    end=180,
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )

        def draw_line(d, code):
            if code == "A":
                d.line(
                    [(cw, ch), (FULL_WIDTH, ch)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
                d.line(
                    [(cw, ch), (cw, FULL_HEIGHT)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
            if code in "BG+J":
                d.line(
                    [(0, ch), (FULL_WIDTH, ch)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
            if code == "C":
                d.line(
                    [(0, ch), (ICON_SIZE, ch)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
                d.line(
                    [(cw, ch), (cw, FULL_HEIGHT)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
            if code == "D":
                d.line(
                    [(cw, ch), (FULL_WIDTH, ch)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
                d.line(
                    [(cw, ch), (cw, 0)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
            if code == "E":
                d.line(
                    [(0, ch), (ICON_SIZE, ch)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
                d.line(
                    [(cw, ch), (cw, 0)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
            if code in "FIG+H":
                d.line(
                    [(ICON_SIZE, 0), (ICON_SIZE, FULL_HEIGHT)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
            if code == "H":
                d.line(
                    [(0, ch), (ICON_SIZE - r, ch)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
                d.line(
                    [(ICON_SIZE + r, ch), (FULL_WIDTH, ch)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
                tl = [cw - r, ch - r]
                br = [cw + r, ch + r]
                d.arc(
                    tl + br,
                    start=180,
                    end=0,
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
            if code == "J":
                r = ICON_SIZE / 4
                d.line(
                    [(cw, 0), (cw, ICON_SIZE - r)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
                d.line(
                    [(cw, ICON_SIZE + r), (cw, FULL_HEIGHT)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
                d.arc(
                    tl + br,
                    start=90,
                    end=270,
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
            if code in "KT":
                d.line(
                    [(0, ch), (FULL_WIDTH, ch)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
                d.line(
                    [(cw, ch), (cw, FULL_HEIGHT)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
            if code in "L":
                d.line(
                    [(0, ch), (FULL_WIDTH, ch)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
                d.line(
                    [(cw, ch), (cw, 0)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
            if code in "M":
                d.line(
                    [(0, ch), (ICON_SIZE, ch)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
                d.line(
                    [(ICON_SIZE, 0), (ICON_SIZE, FULL_HEIGHT)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
            if code in "N":
                d.line(
                    [(ICON_SIZE, 0), (ICON_SIZE, FULL_HEIGHT)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )
                d.line(
                    [(cw, ch), (FULL_WIDTH, ch)],
                    fill=self.decor_color,
                    width=self.decor_width_horz,
                )

        image, draw = self.double_icon()

        # Square icons so far...
        FULL_WIDTH = 2 * ICON_SIZE
        FULL_HEIGHT = 2 * ICON_SIZE
        center = [ICON_SIZE, ICON_SIZE]
        cw = center[0]
        ch = center[1]
        d = int(ICON_SIZE / 2)
        r = int(ICON_SIZE / 4)
        s = int(r * math.sin(math.radians(45)))
        tl = [cw - r, ch - r]
        br = [cw + r, ch + r]

        DECOR_TYPES = ["line", "segment"]

        if self.type not in DECOR_TYPES:
            draw.line([(0, ch), (FULL_WIDTH, ch)], fill="red", width=int(ICON_SIZE / 2))
            return self.move_and_send(image)

        # SEGMENT
        if self.type == "segment":
            draw_segment(draw, self.code)
            return self.move_and_send(image)

        # LINE
        if self.code not in DECOR.keys():
            draw.line([(0, ch), (FULL_WIDTH, ch)], fill="red", width=int(ICON_SIZE / 2))
            return self.move_and_send(image)
        draw_line(draw, self.code)
        return self.move_and_send(image)
