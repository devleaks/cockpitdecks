# ###########################
# Buttons that are drawn on render()
#
import logging
import math
from random import randint
from datetime import datetime, time
from enum import Enum

from PIL import Image, ImageDraw

from cockpitdecks import ICON_SIZE
from cockpitdecks.resources.iconfonts import ICON_FONTS

from cockpitdecks.resources.color import TRANSPARENT_PNG_COLOR, convert_color, light_off
from .draw import DrawBase  # explicit Icon from file to avoid circular import
from .draw_animation import DrawAnimation

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
MIN_COLLECT_TIME = 0.5  # sec


#
# ###############################
# DRAWN REPRESENTATION (using Pillow, continued)
#
#
class DataIcon(DrawBase):

    REPRESENTATION_NAME = "data"

    PARAMETERS = {
        "top-line-color": {"type": "string", "prompt": "Top line color"},
        "top-line-width": {"type": "string", "prompt": "Top line width"},
        "icon": {"type": "string", "prompt": "Icon name"},
        "icon-size": {"type": "integer", "prompt": "Icon size"},
        "icon-color": {"type": "string", "prompt": "Icon color"},
        "data": {"type": "string", "prompt": "Data"},
        "data-format": {"type": "string", "prompt": "Data format (python style)"},
        "data-font": {"type": "string", "prompt": "Data font"},
        "data-size": {"type": "integer", "prompt": "Data font size"},
        "data-color": {"type": "string", "prompt": "Data color"},
        "data-unit": {"type": "string", "prompt": "Data unit"},
        "formula": {"type": "string", "prompt": "Formula"},
        "bottomline": {"type": "string", "prompt": "Bottom line"},
        "bottomline-size": {"type": "integer", "prompt": "Bottom line font size"},
        "bottomline-color": {"type": "string", "prompt": "Bottom line color"},
        "mark": {"type": "string", "prompt": "Mark"},
        "mark-size": {"type": "integer", "prompt": "Mark size"},
        "mark-font": {"type": "string", "prompt": "Mark font"},
        "mark-color": {"type": "string", "prompt": "Mark color"},
    }

    def __init__(self, config: dict, button: "Button"):
        DrawBase.__init__(self, config=config, button=button)
        self.data = self._config[self.REPRESENTATION_NAME]

    def get_datarefs(self):
        if self.datarefs is None:
            if self.data is not None:
                self.datarefs = self.button.scan_datarefs(base=self.data)
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


class ChartData:

    def __init__(self, chart, config: dict) -> None:
        self._config = config
        self.chart = chart
        self.name = config.get("name")

        self.datarefs = None
        self.data = []
        self.type = config.get("type", "tape")
        self.value_min = config.get("minimum", 0)
        self.value_max = config.get("maximum", 100)
        self.keep = config.get("keep", 64)
        self.update = config.get("update", 1)
        self.scale = config.get("scale", 1)
        self.latest = datetime.now()

    def get_datarefs(self):
        if self.datarefs is None:
            if self.chart is not None:
                self.datarefs = self.chart.button.scan_datarefs(base=self._config)
        return self.datarefs

    def get_stats(self):
        if len(self.data) == 0:
            return (0, 0, 0, 0, 0, self.keep, self.update, self.duration)

        def v(idx):
            return [v[idx] for v in self.data]

        count = len(self.data)
        valmin = min(v(0))
        sclmin = valmin * self.scale
        valmax = max(v(0))
        sclmax = valmax * self.scale
        tsmin = min(v(1))
        tsmax = max(v(1))
        #       0      1       2       3       4       5      6      7          8            9
        return (count, valmin, valmax, sclmin, sclmax, tsmin, tsmax, self.keep, self.update, self.duration)

    @property
    def duration(self):
        return self.update * self.keep

    def add(self, value, timestamp=None):
        self.data.append((value, timestamp if timestamp is not None else datetime.now().timestamp()))
        while len(self.data) > self.keep:
            del self.data[0]


class ChartIcon(DrawAnimation):

    REPRESENTATION_NAME = "chart"

    PARAMETERS = {
        "data": {"type": "string", "prompt": "Data"},
    }

    MIN_COLLECT_TIME = 0.5  # sec

    def __init__(self, config: dict, button: "Button"):
        self._config = config
        self.chart = self._config[self.REPRESENTATION_NAME]
        self.lines = self.chart.get("data")  # raw
        self.data = {}  # same, but constructed

        DrawAnimation.__init__(self, config=config, button=button)

    def init(self):
        data_prefix = "line#"
        i = 0
        for d in self.lines:
            n = d.get("name")
            if n is None:
                d["name"] = data_prefix + str(i)
                i = i + 1
        self.data = {d["name"]: ChartData(chart=self, config=d) for d in self.lines}

        # Set basic timing
        stats = {d.name: d.get_stats() for d in self.data.values()}
        fastest = min(s[6] for s in stats.values())
        self.speed = max(fastest, self.MIN_COLLECT_TIME)  # cannot collect faster than MIN_COLLECT_TIME

    def get_datarefs(self):
        if self.datarefs is None:
            datarefs = []
            for c in self.data.values():
                datarefs = datarefs + c.get_datarefs()
            self.datarefs = datarefs
        return self.datarefs

    def should_run(self):
        """
        I.e. only works with onoff activations.
        """
        return True
        return hasattr(self.button._activation, "is_on") and self.button._activation.is_on()

    def get_image_for_icon(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """

        # DEMO
        for c in self.data.values():
            c.add(randint(c.value_min, c.value_max))

        image, draw = self.double_icon(width=ICON_SIZE, height=ICON_SIZE)  # annunciator text and leds , color=(0, 0, 0, 0)
        inside = round(0.04 * image.width + 0.5)

        # Preprocess available data, there might not be a lot at the beginning...
        # For each data, get min, max, scaled min, scaled max, number to keep
        stats = {d.name: d.get_stats() for d in self.data.values()}
        rule_color = "white"

        # data, data_format, data_font, data_color, data_size, data_position = self.get_text_detail(self.chart, "data")

        data_color = "white"
        data_font = "D-DIN"
        data_size = 32
        font = self.get_font(data_font, data_size)
        draw.text(
            (int(ICON_SIZE / 2), int(ICON_SIZE / 2)),
            text=self.REPRESENTATION_NAME,
            font=font,
            anchor="mm",
            align="center",
            fill=data_color,
        )

        # Set graph
        graphmin = min([s[0] for s in stats.values()])
        graphmax = max([s[0] for s in stats.values()])
        tsmin = min([s[5] for s in stats.values()])
        timewidth = max([s[9] for s in stats.values()])

        # Horizontal axis
        draw.line(
            [(0, image.height - inside), (image.width, image.height - inside)],
            width=2,
            fill=rule_color,
        )

        # Add data
        timeslot = int((ICON_SIZE - 2 * inside) / timewidth)
        for c in self.data.values():
            plot = sorted(c.data, key=lambda v: v[1])  # sort by timestamp
            points = []
            for i in range(len(plot)):
                x = inside + (plot[i][1] - tsmin) * timeslot
                y = (ICON_SIZE / 8) + plot[i][0] * (ICON_SIZE * 4 / 5) / c.value_max
                points.append((x, y))
            draw.line(
                points,
                width=2,
                fill=rule_color,
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
