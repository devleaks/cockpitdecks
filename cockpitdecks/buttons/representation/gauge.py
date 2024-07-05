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
from .draw import DrawBase  # explicit Icon from file to avoid circular import

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


#
# ###############################
# DRAWN REPRESENTATION (using Pillow, continued)
#
#
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

    def __init__(self, config: dict, button: "Button"):
        DrawBase.__init__(self, config=config, button=button)
        self.tape = self._config[self.REPRESENTATION_NAME]
        self.vertical = self.option_value("vertical", False)
        self.type = config.get("type", "tape")
        self.value_min = config.get("minimum", 0)
        self.value_max = config.get("maximum", 360)
        self.scale = 1
        self.offset = 0
        self.step = 1
        self._tape = None

    def get_image_for_icon(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        def ticks(i):
            tick_len = 5
            tick_width = 1
            if i % 10 == 0:
                tick_len = 10
                tick_width = 3
            elif i % 5 == 0:
                tick_len = 10
                tick_width = 3
            return (tick_len, tick_width)

        inside = round(0.04 * ICON_SIZE + 0.5)

        if self._tape is None: # Make tape
            value_range = self.value_max - self.value_min
            tape_width = math.ceil(value_range / 10)
            tape_size = tape_width + 2  # 1 icon size before and after
            numiconval = int(1.5 * (value_range / tape_size))
            self.step = (tape_width * ICON_SIZE) / value_range
            rule_color = "yellow"

            tick, tick_format, tick_font, tick_color, tick_size, tick_position = self.get_text_detail(self.tape, "tick")

            tick_color = "yellow"
            tick_font = "D-DIN"
            tick_size = 60
            font = self.get_font(tick_font, tick_size)

            if self.vertical:
                image, draw = self.double_icon(width=ICON_SIZE, height=tape_size * ICON_SIZE)  # annunciator text and leds , color=(0, 0, 0, 0)
                # Rule along entire tape
                draw.line(
                    [(inside, 0), (inside, image.height)],
                    width=2,
                    fill=rule_color,
                )

                # before start value
                before_start = int(self.value_max - numiconval)
                for i in range(before_start, self.value_max):
                    y = (i - before_start) * self.step
                    tick_len, tick_width = ticks(i)
                    draw.line(
                        [(inside, y), (inside + tick_len, y)],
                        width=tick_width,
                        fill=rule_color,
                    )

                    if i % 5 == 0:
                        draw.text(
                            (inside + tick_len + 20, y),
                            text=str(i),
                            font=font,
                            anchor="lm",
                            align="center",
                            fill=tick_color,
                        )
                # between start and end values
                self.offset = numiconval * self.step
                for i in range(self.value_min, self.value_max):
                    y = self.offset + i * self.step
                    tick_len, tick_width = ticks(i)
                    draw.line(
                        [(inside, y), (inside + tick_len, y)],
                        width=tick_width,
                        fill=rule_color,
                    )

                    if i % 5 == 0:
                        draw.text(
                            (inside + tick_len + 20, y),
                            text=str(i),
                            font=font,
                            anchor="lm",
                            align="center",
                            fill=tick_color,
                        )

                # after end value
                offset = (numiconval + value_range) * self.step
                after_end = self.value_min + numiconval
                for i in range(self.value_min, after_end):
                    y = offset + i * self.step
                    tick_len, tick_width = ticks(i)
                    draw.line(
                        [(inside, y), (inside + tick_len, y)],
                        width=tick_width,
                        fill=rule_color,
                    )

                    if i % 5 == 0:
                        draw.text(
                            (inside + tick_len + 20, y),
                            text=str(i),
                            font=font,
                            anchor="lm",
                            align="center",
                            fill=tick_color,
                        )
            else:
                image, draw = self.double_icon(width=tape_size * ICON_SIZE, height=ICON_SIZE)  # annunciator text and leds , color=(0, 0, 0, 0)
                # Rule along entire tape
                draw.line(
                    [(0, image.height - inside), (image.width, image.height - inside)],
                    width=2,
                    fill=rule_color,
                )

                # before start value
                before_start = int(self.value_max - numiconval)
                for i in range(before_start, self.value_max):
                    x = (i - before_start) * self.step
                    tick_len, tick_width = ticks(i)
                    draw.line(
                        [(x, image.height - inside), (x, image.height - inside - tick_len)],
                        width=tick_width,
                        fill=rule_color,
                    )

                    if i % 5 == 0:
                        draw.text(
                            (x, image.height - inside - 20),
                            text=str(i),
                            font=font,
                            anchor="mb",
                            align="center",
                            fill=tick_color,
                        )
                # between start and end values
                self.offset = numiconval * self.step
                for i in range(self.value_min, self.value_max):
                    x = self.offset + i * self.step
                    tick_len, tick_width = ticks(i)
                    draw.line(
                        [(x, image.height - inside), (x, image.height - inside - tick_len)],
                        width=tick_width,
                        fill=rule_color,
                    )

                    if i % 5 == 0:
                        draw.text(
                            (x, image.height - inside - 20),
                            text=str(i),
                            font=font,
                            anchor="mb",
                            align="center",
                            fill=tick_color,
                        )

                # after end value
                offset = (numiconval + value_range) * self.step
                after_end = self.value_min + numiconval
                for i in range(self.value_min, after_end):
                    x = offset + i * self.step
                    tick_len, tick_width = ticks(i)
                    draw.line(
                        [(x, image.height - inside), (x, image.height - inside - tick_len)],
                        width=tick_width,
                        fill=rule_color,
                    )

                    if i % 5 == 0:
                        draw.text(
                            (x, image.height - inside - 20),
                            text=str(i),
                            font=font,
                            anchor="mb",
                            align="center",
                            fill=tick_color,
                        )

            self.icon_color = self._config.get("data-bg-color", self.cockpit_texture)
            self.icon_texture = self._config.get("data-bg-texture", self.cockpit_color)
            self._tape = image

        # Use tape
        # 2a. Move whole drawing around
        value = self.button.get_current_value()
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

        # Paste image on cockpit background and return it.
        bg = self.button.deck.get_icon_background(
            name=self.button_name(),
            width=ICON_SIZE,
            height=ICON_SIZE,
            texture_in=self.icon_color,
            color_in=self.icon_texture,
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

    def __init__(self, config: dict, button: "Button"):
        DrawBase.__init__(self, config=config, button=button)
        self.gauge = self._config[self.REPRESENTATION_NAME]

    def get_datarefs(self):
        if self.datarefs is None:
            if self.data is not None:
                self.datarefs = self.button.scan_datarefs(base=data)
        return self.datarefs

    def get_image_for_icon(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        image, draw = self.double_icon(width=ICON_SIZE, height=ICON_SIZE)  # annunciator text and leds , color=(0, 0, 0, 0)
        inside = round(0.04 * image.width + 0.5)

        # Data
        data = self._config.get("data")
        if data is None:
            logger.warning(f"button {self.button.name}: no data")
            return image

        # Top bar
        topbar = data.get("top-line-color")
        if topbar is not None:
            topbarcolor = convert_color(topbar)
            linewidth = data.get("top-line-width", 6)
            draw.line(
                [(0, int(linewidth / 2)), (image.width, int(linewidth / 2))],
                fill=topbarcolor,
                width=linewidth,
            )

        # Icon
        icon, icon_format, icon_font, icon_color, icon_size, icon_position = self.get_text_detail(data, "icon")
        icon_str = "*"
        icon_arr = icon.split(":")
        if len(icon_arr) == 0 or icon_arr[0] not in ICON_FONTS.keys():
            logger.warning(f"button {self.button.name}: invalid icon {icon}")
        else:
            icon_name = ":".join(icon_arr[1:])
            icon_str = ICON_FONTS[icon_arr[0]][1].get(icon_name, "*")
        icon_font = data.get("icon-font", ICON_FONTS[icon_arr[0]][0])
        font = self.get_font(icon_font, int(icon_size))
        inside = round(0.04 * image.width + 0.5)
        w = inside - 4
        h = image.height / 2
        draw.text((w, h), text=icon_str, font=font, anchor="lm", align="left", fill=icon_color)  # (image.width / 2, 15)

        # Trend
        data_trend = data.get("data-trend")
        trend, trend_format, trend_font, trend_color, trend_size, trend_position = self.get_text_detail(data, "trend")
        trend_str = ICON_FONTS[icon_arr[0]][1].get("minus")
        if self.button.previous_value is not None:
            if self.button.previous_value > self.button.current_value:
                trend_str = ICON_FONTS[icon_arr[0]][1].get("arrow-down")
            elif self.button.previous_value < self.button.current_value:
                trend_str = ICON_FONTS[icon_arr[0]][1].get("arrow-up")
        font = self.get_font(icon_font, int(icon_size / 2))
        if data_trend:
            draw.text(
                (w + icon_size + 4, h),
                text=trend_str,
                font=font,
                anchor="lm",
                align="center",
                fill=icon_color,
            )

        # Value
        DATA_UNIT_SEP = " "
        data_value, data_format, data_font, data_color, data_size, data_position = self.get_text_detail(data, "data")

        if data_format is not None:
            data_str = data_format.format(float(data_value))
        else:
            data_str = str(data_value)

        # if data_unit is not None:
        #    data_str = data_str + DATA_UNIT_SEP + data_unit

        font = self.get_font(data_font, data_size)
        font_unit = self.get_font(data_font, int(data_size * 0.50))
        inside = round(0.04 * image.width + 0.5)
        w = image.width - inside
        h = image.height / 2 + data_size / 2 - inside
        # if dataprogress is not None:
        #    h = h - DATAPROGRESS_SPACE - DATAPROGRESS / 2
        data_unit = data.get("data-unit")
        if data_unit is not None:
            w = w - draw.textlength(DATA_UNIT_SEP + data_unit, font=font_unit)
        draw.text(
            (w, h),
            text=data_str,
            font=font,
            anchor="rs",
            align="right",
            fill=data_color,
        )  # (image.width / 2, 15)

        # Unit
        if data_unit is not None:
            w = image.width - inside
            draw.text(
                (w, h),
                text=DATA_UNIT_SEP + data_unit,
                font=font_unit,
                anchor="rs",
                align="right",
                fill=data_color,
            )  # (image.width / 2, 15)

        # Progress bar
        DATA_PROGRESS_SPACE = 8
        DATA_PROGRESS = 6

        data_progress = data.get("data-progress")
        progress_color = data.get("progress-color")
        if data_progress is not None:
            w = icon_size + 4 * inside
            h = 3 * image.height / 4 - 2 * DATA_PROGRESS
            pct = float(data_value) / float(data_progress)
            if pct > 1:
                pct = 1
            full_color = light_off(progress_color, 0.30)
            l = w + pct * ((image.width - inside) - w)
            draw.line(
                [(w, h), (image.width - inside, h)],
                fill=full_color,
                width=DATA_PROGRESS,
                joint="curve",
            )  # 100%
            draw.line([(w, h), (l, h)], fill=progress_color, width=DATA_PROGRESS, joint="curve")

        # Bottomline (forced at CENTER BOTTOM line of icon)
        bottom_line, botl_format, botl_font, botl_color, botl_size, botl_position = self.get_text_detail(data, "bottomline")

        if bottom_line is not None:
            font = self.get_font(botl_font, botl_size)
            w = image.width / 2
            h = image.height / 2
            h = image.height - inside - botl_size / 2  # forces BOTTOM position
            draw.multiline_text(
                (w, h),
                text=bottom_line,
                font=font,
                anchor="md",
                align="center",
                fill=botl_color,
            )  # (image.width / 2, 15)

        # Final mark
        mark, mark_format, mark_font, mark_color, mark_size, mark_position = self.get_text_detail(data, "mark")
        if mark is not None:
            font = self.get_font(mark_font, mark_size)
            w = image.width - 2 * inside
            h = image.height - 2 * inside
            draw.text(
                (w, h),
                text=mark,
                font=font,
                anchor="rb",
                align="right",
                fill=mark_color,
            )

        # Get background colour or use default value
        # Variables may need normalising as icon-color for data icons is for icon, in other cases its background of button?
        # Overwrite icon-* with data-bg-*
        self.icon_color = self._config.get("data-bg-color", self.cockpit_texture)
        self.icon_texture = self._config.get("data-bg-texture", self.cockpit_color)

        # Paste image on cockpit background and return it.
        bg = self.button.deck.get_icon_background(
            name=self.button_name(),
            width=ICON_SIZE,
            height=ICON_SIZE,
            texture_in=self.icon_color,
            color_in=self.icon_texture,
            use_texture=True,
            who="Data",
        )
        bg.alpha_composite(image)
        return bg
