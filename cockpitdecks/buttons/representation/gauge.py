# ###########################
# Buttons that are drawn on render()
#
import logging
import math
from enum import Enum
import random

from PIL import Image, ImageDraw

from cockpitdecks import ICON_SIZE
from cockpitdecks.resources.iconfonts import ICON_FONTS

from cockpitdecks.resources.color import TRANSPARENT_PNG_COLOR, convert_color, light_off
from .draw import DrawBase  # explicit Icon from file to avoid circular import

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


#
# ###############################
# DRAWN REPRESENTATION (using Pillow, continued)
#
#
def grey(i: int):
    return (i, i, i)


NEEDLE_COLOR = grey(255)
NEEDLE_UNDERLINE_COLOR = grey(0)
MARKER_COLOR = "lime"
RULE_COLOR = grey(255)

TICK_COLOR = grey(255)
LABEL_COLOR = grey(255)


#
# ###############################
# DRAWN REPRESENTATION (using Pillow, continued)
#
#
class TapeIcon(DrawBase):

    REPRESENTATION_NAME = "tape"

    PARAMETERS = {
        "top-line-color": {"type": "string", "prompt": "Top line color"},
    }

    def __init__(self, button: "Button"):
        DrawBase.__init__(self, button=button)
        self.tape = self._config[self.REPRESENTATION_NAME]
        self.vertical = self.option_value("vertical", False)
        self.value_min = self.tape.get("minimum", 0)
        self.value_max = self.tape.get("maximum", 100)
        self.value_step = self.tape.get("step", 1)
        self.scale = self.tape.get("scale", 1)

        # Working variables
        self.offset = 0
        self.step = 0

        self.tick_lengths = self.tape.get("tick-lengths", [(10, 1), (20, 2), (30, 4)])
        self.rule_color = self.tape.get("rule-color", RULE_COLOR)
        self.rule_position = self.tape.get("rule-position", "center")  # center is valid for both horiz and vert
        self.label_frequency = self.tape.get("label-frequency", 5)
        self._tape = None

    def get_image_for_icon(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """

        def ticks(i):
            tick_len = self.tick_lengths[0][0]
            tick_width = self.tick_lengths[0][1]
            if i % 10 == 0:
                tick_len = self.tick_lengths[2][0]
                tick_width = self.tick_lengths[2][1]
            elif i % self.label_frequency == 0:
                tick_len = self.tick_lengths[1][0]
                tick_width = self.tick_lengths[1][1]
            return (tick_len, tick_width)

        inside = round(0.04 * ICON_SIZE + 0.5)

        if self._tape is None:  # Make tape
            value_range = self.value_max - self.value_min
            value_step = value_range / self.value_step

            tape_width = math.ceil(value_range / 10)
            tape_size = tape_width + 2  # 1 icon size before and after
            numiconval = int(1.5 * (value_range / tape_size))
            self.step = (tape_width * ICON_SIZE) / value_range  # self.value_step unit in value = self.step pixels

            tick, tick_format, tick_font, tick_color, tick_size, tick_position = self.get_text_detail(self.tape, "tick")
            font = self.get_font(tick_font, tick_size)

            center_position = ICON_SIZE / 2
            center_direction = -1

            tick_start = 0
            tick_offset = self.value_min
            tick_end = value_range
            tick_real_start = 0
            tick_real_zero = numiconval
            tick_real_end = value_range + numiconval
            tick_real_stop = value_range + 2 * numiconval
            self.offset = numiconval * self.step

            if self.vertical:
                image, draw = self.double_icon(width=ICON_SIZE, height=tape_size * ICON_SIZE)  # annunciator text and leds , color=(0, 0, 0, 0)

                anchor = "lm"
                if self.rule_position == "left":
                    center_position = inside
                elif self.rule_position == "right":
                    center_position = image.width - inside
                    center_direction = 1
                    anchor = "rm"
                label_offset = int(center_direction * ICON_SIZE / 8)

                # Rule along entire tape
                draw.line(
                    [(center_position, 0), (center_position, image.height)],
                    width=2,
                    fill=self.rule_color,
                )

                # print(">>>>>>", numiconval, tick_real_start, tick_real_zero, tick_real_end, tick_real_stop)

                # before start value
                for i in range(tick_real_start, tick_real_zero):
                    y = int(i * self.step)
                    idx = self.value_max - numiconval + i
                    tick_len, tick_width = ticks(idx)
                    draw.line(
                        [(center_position, y), (center_position - center_direction * tick_len, y)],
                        width=tick_width,
                        fill=self.rule_color,
                    )
                    # print(self.button_name(), "B", y, i, idx)

                    if idx % self.label_frequency == 0:
                        draw.text(
                            (center_position - label_offset, y),
                            text=str(idx),
                            font=font,
                            anchor=anchor,
                            align="center",
                            fill=tick_color,
                        )
                # between start and end values
                offset = numiconval * self.step
                # print("offset 1", offset)
                for i in range(tick_real_zero, tick_real_end):
                    y = int(i * self.step)
                    idx = self.value_min + (i - tick_real_zero)
                    tick_len, tick_width = ticks(idx)
                    draw.line(
                        [(center_position, y), (center_position - center_direction * tick_len, y)],
                        width=tick_width,
                        fill=self.rule_color,
                    )
                    # print(self.button_name(), "R", y, i, idx)

                    if idx % self.label_frequency == 0:
                        draw.text(
                            (center_position - label_offset, y),
                            text=str(idx),
                            font=font,
                            anchor=anchor,
                            align="center",
                            fill=tick_color,
                        )

                # after end value
                offset = (numiconval + value_range) * self.step
                # print("offset 2", offset)
                for i in range(tick_real_end, tick_real_stop):
                    y = int(i * self.step)
                    idx = self.value_min + i - tick_real_end
                    tick_len, tick_width = ticks(idx)
                    draw.line(
                        [(center_position, y), (center_position - center_direction * tick_len, y)],
                        width=tick_width,
                        fill=self.rule_color,
                    )
                    # print(self.button_name(), "A", y, i, idx)

                    if idx % self.label_frequency == 0:
                        draw.text(
                            (center_position - label_offset, y),
                            text=str(idx),
                            font=font,
                            anchor=anchor,
                            align="center",
                            fill=tick_color,
                        )
            else:
                image, draw = self.double_icon(width=tape_size * ICON_SIZE, height=ICON_SIZE)  # annunciator text and leds , color=(0, 0, 0, 0)

                anchor = "mb"
                if self.rule_position == "bottom":
                    center_position = image.height - inside
                elif self.rule_position == "top":
                    center_position = inside
                    center_direction = 1
                    anchor = "mt"
                label_offset = int(center_direction * ICON_SIZE / 8)

                # Rule along entire tape
                draw.line(
                    [(0, center_position), (image.width, center_position)],
                    width=2,
                    fill=self.rule_color,
                )

                # before start value
                for i in range(tick_real_start, tick_real_zero):
                    x = i * self.step
                    idx = self.value_max - numiconval + i
                    tick_len, tick_width = ticks(idx)
                    draw.line(
                        [(x, center_position), (x, center_position + center_direction * tick_len)],
                        width=tick_width,
                        fill=self.rule_color,
                    )

                    if idx % self.label_frequency == 0:
                        draw.text(
                            (x, center_position + label_offset),
                            text=str(idx),
                            font=font,
                            anchor=anchor,
                            align="center",
                            fill=tick_color,
                        )
                # between start and end values
                offset = numiconval * self.step
                # print("offset 1", offset)
                for i in range(tick_real_zero, tick_real_end):
                    x = i * self.step
                    idx = self.value_min + (i - tick_real_zero)
                    tick_len, tick_width = ticks(idx)
                    draw.line(
                        [(x, center_position), (x, center_position + center_direction * tick_len)],
                        width=tick_width,
                        fill=self.rule_color,
                    )

                    if idx % self.label_frequency == 0:
                        draw.text(
                            (x, center_position + label_offset),
                            text=str(idx),
                            font=font,
                            anchor=anchor,
                            align="center",
                            fill=tick_color,
                        )

                # after end value

                offset = (numiconval + value_range) * self.step
                # print("offset 2", offset)
                for i in range(tick_real_end, tick_real_stop):
                    x = i * self.step
                    idx = self.value_min + i - tick_real_end
                    tick_len, tick_width = ticks(idx)
                    draw.line(
                        [(x, center_position), (x, center_position + center_direction * tick_len)],
                        width=tick_width,
                        fill=self.rule_color,
                    )
                    if i % self.label_frequency == 0:
                        draw.text(
                            (x, center_position + label_offset),
                            text=str(idx),
                            font=font,
                            anchor=anchor,
                            align="center",
                            fill=tick_color,
                        )

            self.icon_color = self._config.get("data-bg-color", self.cockpit_texture)
            self.icon_texture = self._config.get("data-bg-texture", self.cockpit_color)
            self._tape = image

        # Use tape
        # 2a. Move whole drawing around
        r = self.button.value
        if r is None:
            r = self.value_min
        value = r - self.value_min
        a = 1
        b = 0
        c = 0
        d = 0
        e = 1
        f = 0
        if self.vertical:
            f = self.offset - ICON_SIZE / 2 + value * self.step
        else:
            c = self.offset - ICON_SIZE / 2 + value * self.step
        tape = self._tape.transform(self._tape.size, Image.AFFINE, (a, b, c, d, e, f))

        # print("RESULT", r, value, self.offset, a, b, c, d, e, f)

        # Paste image on cockpit background and return it.
        # may be cahe it and take a bg = cached_bg.copy()
        bg = self.button.deck.get_icon_background(
            name=self.button_name(),
            width=ICON_SIZE,
            height=ICON_SIZE,
            texture_in=self.icon_texture,
            color_in=self.icon_color,
            use_texture=True,
            who="Data",
        )
        bg.alpha_composite(tape)
        return bg


class GaugeIcon(DrawBase):

    REPRESENTATION_NAME = "gauge"

    PARAMETERS = {
        "top-line-color": {"type": "string", "prompt": "Top line color"},
    }

    def __init__(self, button: "Button"):
        DrawBase.__init__(self, button=button)
        self.gauge = self._config[self.REPRESENTATION_NAME]

        self.gauge_offset = self.gauge.get("gauge-offset", 0)
        self.center = (int(ICON_SIZE / 2), int(ICON_SIZE / 2) + self.gauge_offset)

        self.scale = 1
        self.offset = 0
        self.gauge_size = self.get_attribute("gauge-size", default=int(ICON_SIZE / 2))
        self.num_ticks = self.gauge.get("ticks", 8)

        # Ticks
        self.tick_from = self.get_attribute("tick-from", default=-90)
        self.tick_to = self.get_attribute("tick-to", default=90)
        self.angle = self.gauge.get("angle", self.tick_to - self.tick_from)

        self.tick_space = self.get_attribute("tick-space", default=10)
        self.tick_length = self.get_attribute("tick-length", default=16)
        self.tick_width = self.get_attribute("tick-width", default=4)
        self.tick_color = self.get_attribute("tick-color", default=TICK_COLOR)
        self.tick_color = convert_color(self.tick_color)
        self.tick_underline_color = self.get_attribute("tick-underline-color", default=TICK_COLOR)
        self.tick_underline_color = convert_color(self.tick_underline_color)
        self.tick_underline_width = self.get_attribute("tick-underline-width", 4)

        # Labels
        self.tick_labels = self.gauge.get("tick-labels", {})
        self.tick_label_space = self.get_attribute("tick-label-space", default=10)
        self.tick_label_font = self.get_attribute("tick-label-font", default=self.get_attribute("label-font"))
        self.tick_label_size = self.get_attribute("tick-label-size", default=32)
        self.tick_label_color = self.get_attribute("tick-label-color", default=LABEL_COLOR)
        self.tick_label_color = convert_color(self.tick_label_color)

        # Handle needle
        self.needle_width = self.get_attribute("needle-width", default=8)
        self.needle_start = self.get_attribute("needle-start", default=10)  # from center of button
        self.needle_length = self.get_attribute("needle-length", default=50)  # end = start + length
        self.needle_tip = self.gauge.get("needle-tip")  # arro, arri, ball
        self.needle_tip_size = self.get_attribute("needle-tip-size", default=5)
        # self.needle_length = int(self.needle_length * self.button_size / 200)
        self.needle_color = self.get_attribute("needle-color", default=NEEDLE_COLOR)
        self.needle_color = convert_color(self.needle_color)
        # Options
        self.needle_underline_width = self.get_attribute("needle-underline-width", default=4)
        self.needle_underline_color = self.get_attribute("needle-underline-color", default=NEEDLE_UNDERLINE_COLOR)
        self.needle_underline_color = convert_color(self.needle_underline_color)

        self._gauge = None
        self._needle = None

    def get_image_for_icon(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """

        def red(a):
            # reduce a to [0, 360[
            if a >= 360:
                return red(a - 360)
            elif a < 0:
                return red(a + 360)
            return a

        if self._gauge is None:  # do backgroud image
            image, draw = self.double_icon(width=ICON_SIZE, height=ICON_SIZE)  # annunciator text and leds , color=(0, 0, 0, 0)
            inside = round(0.04 * image.width + 0.5)
            gauge_size = ICON_SIZE / 2
            num_ticks = self.num_ticks + 1
            self.angular_step = int(self.angle / self.num_ticks)

            # Values on arc
            tick, tick_format, tick_font, tick_color, tick_size, tick_position = self.get_text_detail(self.gauge, "tick")

            tick_color = "yellow"
            tick_font = "D-DIN"
            tick_size = 60
            font = self.get_font(tick_font, tick_size)

            # Ticks
            tick_start = self.gauge_size / 2 + self.tick_space
            tick_end = tick_start + self.tick_length
            label_anchors = []
            if self.tick_width > 0:
                tick_lbl = tick_end + self.tick_label_space

                for i in range(num_ticks):
                    a = red(180 + self.tick_from + i * self.angular_step)
                    x0 = self.center[0] - tick_start * math.sin(math.radians(a))
                    y0 = self.center[1] + tick_start * math.cos(math.radians(a))
                    x1 = self.center[0] - tick_end * math.sin(math.radians(a))
                    y1 = self.center[1] + tick_end * math.cos(math.radians(a))
                    x2 = self.center[0] - tick_lbl * math.sin(math.radians(a))
                    y2 = self.center[1] + tick_lbl * math.cos(math.radians(a))
                    # print(f"===> ({x0},{y0}) ({x1},{y1}) a=({x2},{y2})")
                    label_anchors.append([a, x2, y2])
                    draw.line([(x0, y0), (x1, y1)], width=self.tick_width, fill=self.tick_color)

            # Tick run mark
            if self.tick_underline_width > 0:
                tl = [self.center[0] - tick_start, self.center[1] - tick_start]
                br = [self.center[0] + tick_start, self.center[1] + tick_start]
                draw.arc(
                    tl + br,
                    fill=self.tick_underline_color,
                    start=self.tick_from - 90,
                    end=self.tick_to - 90,
                    width=self.tick_underline_width,
                )

            # Labels
            font = self.get_font(self.tick_label_font, int(self.tick_label_size))
            for i in range(num_ticks):
                angle = int(label_anchors[i][0])
                tolerence = 30
                if angle > tolerence and angle < 180 - tolerence:
                    anchor = "rs"
                    align = "right"
                elif angle > 180 + tolerence and angle < 360 - tolerence:
                    anchor = "ls"
                    align = "left"
                else:  # 0, 180, 360
                    anchor = "ms"
                    align = "center"
                # print(self.tick_labels[i], label_anchors[i], label_anchors[i][1:3], anchor, align)
                draw.text(
                    label_anchors[i][1:3],
                    text=str(i),
                    font=font,
                    anchor=anchor,
                    align=align,
                    fill=self.tick_label_color,
                )

            self.icon_color = self._config.get("data-bg-color", self.cockpit_texture)
            self.icon_texture = self._config.get("data-bg-texture", self.cockpit_color)
            self._gauge = self.button.deck.get_icon_background(
                name=self.button_name(),
                width=ICON_SIZE,
                height=ICON_SIZE,
                texture_in=self.icon_texture,
                color_in=self.icon_color,
                use_texture=True,
                who="Data",
            )
            self._gauge.alpha_composite(image)

            # Needle
            self._needle, needle_drawing = self.double_icon(width=ICON_SIZE, height=ICON_SIZE)  # annunciator text and leds , color=(0, 0, 0, 0)
            needle_drawing.line(
                [self.center, (self.center[0], self.center[1] - self.needle_length)],
                fill=self.needle_color,
                width=self.needle_width,
            )

        value = self.button.value
        if value is None:
            value = 0
        rotation = self.offset + self.scale * value
        rotated_needle = self._needle.rotate(rotation, resample=Image.Resampling.NEAREST, center=self.center)

        bg = self._gauge.copy()
        bg.alpha_composite(rotated_needle)
        return bg


class CompassIcon(GaugeIcon):
    """A Compass is a circular gauge (360°)"""

    REPRESENTATION_NAME = "compass"

    PARAMETERS = {
        "compass-mode": {"type": "string", "prompt": "Compass Mode"},
    }

    def __init__(self, button: "Button"):
        self.compass = button._config.get(self.REPRESENTATION_NAME)
        self.mode = self.compass.get("mode", "compass")
        # Complement Gauge for compass
        # ... to do
        GaugeIcon.__init__(self, button=button)
