# ###########################
# Buttons that are drawn on render()
#
import logging
import traceback
import threading
from random import randint
from datetime import datetime
from enum import Enum

from PIL import Image, ImageDraw

from cockpitdecks import ICON_SIZE
from cockpitdecks.resources.iconfonts import ICON_FONTS

from cockpitdecks.resources.color import TRANSPARENT_PNG_COLOR, convert_color, light_off
from .draw import DrawBase  # explicit Icon from file to avoid circular import
from .draw_animation import DrawAnimation
from cockpitdecks.value import Value

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


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

    def __init__(self, button: "Button"):
        DrawBase.__init__(self, button=button)
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

        self.type = config.get("type", "line")
        self.value_min = config.get("minimum", 0)
        self.value_max = config.get("maximum", 100)
        self.keep = config.get("keep", 10)
        self.update = config.get("update")
        self.scale = config.get("scale", 1)
        self.color = config.get("color", "grey")
        self.color = convert_color(self.color)

        self.value = Value(self.name, config=config, button=chart.button)

        self.data = []
        self.last_data = datetime.now().timestamp()

        self.init()

    def init(self):
        if self.update is not None and self.update > 0:
            self.stop = threading.Event()
            self.thread = threading.Thread(target=self.start)
            self.thread.start()

    def start(self):
        while not self.stop.wait(self.update):
            self.add(self.get_value())

    def get_datarefs(self):
        if self.datarefs is None:
            if self.chart is not None:
                self.datarefs = self.chart.button.scan_datarefs(base=self._config)
        logger.debug(f"chart {self.name} return datarefs {self.datarefs}")
        return self.datarefs

    def get_value(self):
        return self.value.get_value()
        # return randint(self.value_min, self.value_max)

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
        return 0 if self.update is None else self.update * self.keep

    def add(self, value, timestamp=None):
        self.last_data = timestamp if timestamp is not None else datetime.now().timestamp()
        self.data.append((value, self.last_data))
        while len(self.data) > self.keep:
            del self.data[0]


class ChartIcon(DrawAnimation):

    REPRESENTATION_NAME = "chart"

    PARAMETERS = {
        "data": {"type": "string", "prompt": "Data"},
    }

    MIN_UPDATE_TIME = 0.5  # sec
    DEFAULT_TIME_WIDTH = 60  # sec

    def __init__(self, button: "Button"):
        self.chart = button._config[self.REPRESENTATION_NAME]
        self.chart_configs = self.chart.get("charts")  # raw
        self.charts = {}  # same, but constructed
        self.time_width = self.chart.get("time-width")
        self.rule_height = self.chart.get("rule-height", 0)

        DrawAnimation.__init__(self, button=button)
        self.init()

    def init(self):
        # Prepare each chart.
        data_prefix = "line#"
        i = 0
        for d in self.chart_configs:
            if d.get("name") is None:  # give a name if none
                d["name"] = data_prefix + str(i)
                i = i + 1
        self.charts = {d["name"]: ChartData(chart=self, config=d) for d in self.chart_configs}

        # Compute speed of update (the fastest)
        speed = None
        for c in self.charts.values():
            if c.update is not None:
                if speed is not None:
                    speed = min(speed, c.update)
                    speed = max(speed, self.MIN_UPDATE_TIME)
                else:
                    speed = max(c.update, self.MIN_UPDATE_TIME)
        self.speed = speed
        if speed is not None:
            logger.debug(f"update speed: {speed} secs.")
        else:
            logger.debug(f"no animation, update when value changed")

        # Compute time width of icon (width = ICON_SIZE - 2 * inside)
        if self.time_width is None:
            time_width = max([c.duration for c in self.charts.values()])
            logger.debug(f"time width: {time_width} secs.")
            if time_width == 0:
                time_width = self.DEFAULT_TIME_WIDTH
                logger.debug(f"time width set to {time_width} secs.")
            self.time_width = time_width

    def get_datarefs(self):
        # Collects datarefs in each chart
        if self.datarefs is None:
            datarefs = []
            for c in self.charts.values():
                datarefs = datarefs + c.get_datarefs()
            self.datarefs = datarefs
        return self.datarefs

    def should_run(self):
        """
        I.e. only works with onoff activations.
        """
        return True
        return self.speed is not None

    def get_image_for_icon(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        inside = round(0.04 * ICON_SIZE + 0.5)
        image, chart = self.double_icon(width=int(ICON_SIZE - 2 * inside), height=int(ICON_SIZE * 7 / 8 - 2 * inside))

        top_of_chart = int(ICON_SIZE / 8 + inside)

        time_pix = image.width / self.time_width
        time_left = datetime.now().timestamp()

        # Preprocess available data, there might not be a lot at the beginning...
        # For each data, get min, max, scaled min, scaled max, number to keep
        stats = {d.name: d.get_stats() for d in self.charts.values()}
        rule_color = "white"

        # data, data_format, data_font, data_color, data_size, data_position = self.get_text_detail(self.chart, "data")

        data_color = "white"
        data_font = "D-DIN"
        data_size = 32
        font = self.get_font(data_font, data_size)
        chart.text(
            (int(image.width / 2), int(image.height / 2)),
            text=self.REPRESENTATION_NAME,
            font=font,
            anchor="mm",
            align="center",
            fill=data_color,
        )

        # Horizontal axis
        rule_width = 2
        height = image.height * self.rule_height / 100
        chart.line(
            [(0, image.height - height - int(rule_width / 2)), (image.width, image.height - height - int(rule_width / 2))],
            width=rule_width,
            fill=rule_color,
        )
        # Horiz ticks later

        # No vertical axis
        # Vert ticks later: 0-100?

        # Add data
        for c in self.charts.values():
            plot = sorted(c.data, key=lambda v: v[1])  # sort by timestamp
            if c.type == "line":
                points = []
                for pt in plot:
                    pt_value, pt_time = pt
                    x = (time_left - pt_time) * time_pix
                    y = image.height * pt_value / c.value_max
                    points.append((int(x), int(y)))
                chart.line(
                    points,
                    width=2,
                    fill=c.color,
                )
            elif c.type == "bar":
                barwidth = int(c.update * time_pix * 0.8)
                for pt in plot:
                    pt_value, pt_time = pt
                    x = (time_left - pt_time) * time_pix
                    y = image.height * pt_value / c.value_max
                    bbox = [(x, image.height - y), (x + barwidth, image.height)]  # ((int(x), int(y)))
                    chart.rectangle(
                        bbox,
                        fill=c.color,
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
        bg.alpha_composite(image, [inside, top_of_chart])

        return bg
