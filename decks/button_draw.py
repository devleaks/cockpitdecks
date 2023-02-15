# ###########################
# Special Airbus Button Rendering
#
import logging
import threading
import time
import colorsys
import traceback
import math

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter, ImageColor
# from mergedeep import merge
from metar import Metar

from .constant import DATAREF_RPN, ANNUNCIATOR_DEFAULTS, ANNUNCIATOR_STYLES, LIGHT_OFF_BRIGHTNESS, WEATHER_ICON_FONT, ICON_FONT
from .color import convert_color, light_off
from .rpc import RPC
from .resources.icons import icons as FA_ICONS        # Font Awesome Icons
from .resources.weathericons import WEATHER_ICONS     # Weather Icons
from .button_representation import Icon

logger = logging.getLogger("Annunciator")
# logger.setLevel(logging.DEBUG)


# Yeah, shouldn't be globals.
# Localized here for convenience
# Can be moved lated.
ICON_SIZE = 256 # px
DEFAULT_INVERT_COLOR = "white"


class CircularSwitch(Icon):

    def __init__(self, config: dict, button: "Button"):

        Icon.__init__(self, config=config, button=button)

        self.switch = config.get("circular-switch")
        self.button_size = config.get("button-size", int(2 * ICON_SIZE / 3))
        self.button_fill_color = config.get("button-fill-color", "yellow")
        self.button_stroke_color = config.get("button-stroke-color", "red")
        self.button_stroke_width = config.get("button-stroke-width", 4)
        self.switch_style = self.switch.get("switch-style")
        self.tick_from = self.switch.get("tick-from")
        self.tick_to = self.switch.get("tick-to")
        self.tick_steps = self.switch.get("tick-steps")
        self.tick_space = self.switch.get("tick-space", 10)
        self.tick_length = self.switch.get("tick-length", 10)
        self.tick_width = self.switch.get("tick-width", 4)
        self.tick_color = self.switch.get("tick-color", "lime")
        if self.tick_steps < 2:
            self.tick_steps = 2
        self.angular_step = (self.tick_to - self.tick_from) / (self.tick_steps - 1)
        self.tick_underline = self.switch.get("tick-underline")
        self.tick_label_space = self.switch.get("tick-label-space", 10)
        self.tick_labels = self.switch.get("tick-labels")
        self.needle_color = self.switch.get("needle-color", "white")
        self.needle_width = self.switch.get("needle-width", 8)
        self.needle_underline = self.switch.get("needle-underline", "black")

        if len(self.tick_labels) != self.tick_steps:
            logger.warning(f"not enough label")


    def get_image_for_icon(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        def red(a):
            if a > 360:
                a = a - 360
                return red(a)
            elif a < 0:
                a = a + 360
                return red(a)
            return a

        image = Image.new(mode="RGB", size=(ICON_SIZE, ICON_SIZE))                     # annunciator text and leds , color=(0, 0, 0, 0)
        draw = ImageDraw.Draw(image)

        # Button
        center = [ICON_SIZE/2, ICON_SIZE/2]

        tl = [center[0]-self.button_size/2, center[0]-self.button_size/2]
        br = [center[0]+self.button_size/2, center[0]+self.button_size/2]
        draw.ellipse(tl+br, fill=self.button_fill_color, outline=self.button_stroke_color, width=self.button_stroke_width)

        # Ticks
        tick_start = self.button_size/2 + self.tick_space
        tick_end = tick_start + self.tick_length
        tick_lbl = tick_end + self.tick_label_space

        label_anchors = []
        for i in range(self.tick_steps):
            a = red(self.tick_from + i * self.angular_step)
            x0 = center[0] - tick_start * math.sin(math.radians(a))
            y0 = center[1] + tick_start * math.cos(math.radians(a))
            x1 = center[0] - tick_end * math.sin(math.radians(a))
            y1 = center[1] + tick_end * math.cos(math.radians(a))
            x2 = center[0] - tick_lbl * math.sin(math.radians(a))
            y2 = center[1] + tick_lbl * math.cos(math.radians(a))
            # print(f"===> ({x0},{y0}) ({x1},{y1}) a=({x2},{y2})")
            label_anchors.append([i, x1, y1])
            draw.line([(x0,y0), (x1, y1)], width=self.tick_width, fill=self.tick_color)


        # print("-<-<", label_anchors)

        # Labels
        label_color = "white"
        label_font = "DIN"
        label_size = 40
        fontname = self.get_font(label_font)
        font = ImageFont.truetype(fontname, int(label_size))
        for i in range(self.tick_steps):
            if label_anchors[i][0] > 0 and label_anchors[i][0] < 180:
                anchor="rs"
                align="right"
            elif label_anchors[i][0] > 180 and label_anchors[i][0] < 360:
                anchor="ls"
                align="left"
            else:
                anchor="ms"
                align="center"
            print(self.tick_labels[i], label_anchors[i], label_anchors[i][1:3], anchor, align)
            draw.text(label_anchors[i][1:3],
                      text=self.tick_labels[i],
                      font=font,
                      anchor=anchor,
                      align=align,
                      fill=label_color)

        # Thick run mark
        tl = [center[0]-tick_start, center[0]-tick_start]
        br = [center[0]+tick_start, center[0]+tick_start]
        draw.arc(tl+br, fill="blue", start=self.tick_from+90, end=self.tick_to+90, width=6)

        # Needle
        needle_length = self.button_size/2 - 5
        underline_width = 4
        underline_color = "black"
        value = self.button.get_current_value()
        if value is None:
            value = 0
        x = center[0] + needle_length * math.sin(math.radians(value))
        y = center[1] + needle_length * math.cos(math.radians(value))
        # print(f"***> ({center}) ({x},{y})")
        if underline_width > 0:
            draw.line([tuple(center), (x, y)],
                      width=self.needle_width+2*underline_width,
                      fill=underline_color)
        draw.line([tuple(center), (x, y)], width=self.needle_width, fill=self.needle_color)
        return image



class Switch(Icon):

    def __init__(self, config: dict, button: "Button"):

        Icon.__init__(self, config=config, button=button)

        self.switch_style = config.get("switch-style")
        self.tick_underline = config.get("tick-underline")
        self.tick_labels = config.get("tick-labels")
        self.three_way = self.button.has_option("3way")


    def get_image_for_icon(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        image = Image.new(mode="RGBA", size=(ICON_SIZE, ICON_SIZE))                     # annunciator text and leds , color=(0, 0, 0, 0)
        draw = ImageDraw.Draw(image)
        return image
