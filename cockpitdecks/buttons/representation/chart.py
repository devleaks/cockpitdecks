# ###########################
# Buttons that are drawn on render()
#
import logging
import threading
import math
from random import randint
import traceback

from PIL import ImageDraw

from cockpitdecks import ICON_SIZE, now

from cockpitdecks.resources.color import convert_color
from cockpitdecks.resources.ts import TimeSerie
from cockpitdecks.simulator import SimulatorData, SimulatorDataListener
from .draw import DrawBase
from .draw_animation import DrawAnimation
from cockpitdecks.value import Value

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

MAX_UPDATE_RATE = 4  # per seconds
MAX_SPARKLINES = 3


#
# ###############################
# DYNAMIC CHARTS
#
#
class ChartData(DrawBase, SimulatorDataListener):

    def __init__(self, chart, config: dict) -> None:
        self.chart_config = config
        self.chart = chart

        self.name = config.get("name")

        self.datarefs = None

        # values
        self.value = Value(self.name, config=config, button=chart.button)

        self.data = []
        self.last_data = now().timestamp()

        # Vertical axis, assumes default values
        self.type = config.get("type", "line")  # point, line, bar or bars or histogram
        self.value_min = config.get("value-min", 0)
        self.value_max = config.get("value-max", 100)

        # Horizontal axis
        # 0 = no update, updated when dataref changed
        self.update = config.get("update", 0)
        self.keep = config.get("keep", 0)
        self.time_width: float | None = config.get("time-width")
        self.rate = config.get("rate", False)

        self._stop = threading.Event()
        self._stop.set()
        self.thread = None

        # presentation
        self.scale = config.get("scale", 1)
        self.color = config.get("color", "grey")
        self.color = convert_color(self.color)
        self._cached = None

        self.init()

    def init(self):
        if self.time_width is None:  # have to compute/guess it
            if self.auto_update and self.keep > 0:
                self.time_width = self.update * self.keep
            else:
                logger.debug(f"chart {self.name} unable to estimate time width")
        else:
            if self.auto_update and self.keep == 0:
                self.keep = math.ceil(self.time_width / self.update)
        if not self.auto_update:
            for d in self.get_simulator_data():
                dref = self.chart.button.sim.get_dataref(d)
                dref.add_listener(self)
            logger.debug(f"chart {self.name}: installed listener on {self.get_simulator_data()}")

    def get_simulator_data(self) -> set:
        if self.datarefs is None:
            if self.chart is not None:
                self.datarefs = self.chart.button.scan_datarefs(base=self.chart_config)
        logger.debug(f"chart {self.name} return datarefs {self.datarefs}")
        return self.datarefs

    @property
    def auto_update(self):
        return self.update >= (1 / MAX_UPDATE_RATE)

    @property
    def duration(self):
        return self.time_width

    def invalidate_representation(self):
        self._cached = None

    # (Optional) Automation of data collection
    def start(self):
        if not self._stop.is_set():
            logger.warning(f"chart {self.name} already started ({self.thread.is_alive() if self.thread is not None else 'no thread'})")
            return
        if self.update is not None and self.update > 0:
            self._stop.clear()
            self.thread = threading.Thread(target=self.loop, name=f"ChartData:{self.name}")
            self.thread.start()

    def loop(self):
        logger.debug(f"chart {self.name} started")
        while not self._stop.wait(self.update):
            r = self.get_value()
            self.add(r)
        logger.debug(f"chart {self.name} stopped")

    def stop(self):
        if not self._stop.is_set():
            self._stop.set()
            logger.debug(f"chart {self.name} will stop at next update")
            e = self.thread.join(timeout=self.update)
            logger.debug(f"chart {self.name}: thread terminated")

    # Value
    def get_value(self):
        return self.value.get_value()
        # return randint(self.value_min, self.value_max)

    def simulator_data_changed(self, data: SimulatorData):
        r = data.value()
        if r is None:
            logger.warning(f"chart {self.name}: value is None, set to zero")
            r = 0
        self.add(r)

    def add(self, value, timestamp=None):
        self.last_data = timestamp if timestamp is not None else now().timestamp()
        self.data.append((value, self.last_data))
        if self.keep > 0:  # we know the number of points to keep
            if len(self.data) > self.keep:
                data = sorted(self.data, key=lambda x: x[1])
                self.data = data[-self.keep :]
        else:  # must use time, only keeps time_width more recent points
            maxtime = now().timestamp() - self.time_width  # in the past
            data = filter(lambda x: x[1] > maxtime, self.data)
            self.data = sorted(data, key=lambda x: x[1])
            if len(self.data) == 0:
                logger.warning(f"chart {self.name}: no data")
        self.invalidate_representation()
        self.render()

    def get_rate(self):
        rate = []
        if len(self.data) > 1:
            p = None
            for d in self.data:
                if p is not None:
                    rate.append(((d[0] - p[0]) / (d[1] - p[1]), d[1]))
                p = d
        else:
            if len(self.data) == 1:
                rate = self.data
        return rate

    def get_data(self):
        return self.get_rate() if self.rate else self.data

    def get_image_for_icon(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        if self._cached is not None:
            return self._cached  # data unchanged, plot unchanged

        inside = round(0.04 * ICON_SIZE + 0.5)
        image, chart = self.double_icon(width=int(ICON_SIZE - 2 * inside), height=int(ICON_SIZE * 7 / 8 - 2 * inside))

        time_pix = image.width / self.time_width
        time_left = now().timestamp()

        # data, data_format, data_font, data_color, data_size, data_position = self.get_text_detail(self.chart, "data")
        # data_color = "white"
        # data_font = "D-DIN"
        # data_size = 32
        # font = self.get_font(data_font, data_size)

        # image (0, height) is graph (0,0)
        # image (width,0) is graph(maxtime, maxvalue)
        # data is sorted in truncate
        # plot = sorted(self.data, key=lambda v: v[1])  # sort by timestamp
        plot = self.get_data()
        vert_pix = image.height / (self.value_max - self.value_min)  # available for plot
        vert_zero = image.height
        if self.type == "point":
            radius = 2
            for pt in plot:
                pt_value, pt_time = pt
                if pt_value < self.value_min:
                    pt_value = self.value_min
                if pt_value > self.value_max:
                    pt_value = self.value_max
                x = (time_left - pt_time) * time_pix
                y = vert_zero - (vert_pix * (pt_value - self.value_min))
                box = ((int(x) - radius, int(y) - radius), (int(x) + radius, int(y) + radius))
                chart.ellipse(
                    box,
                    width=2,
                    fill=self.color,
                )
        elif self.type in ["line", "curve"]:
            points = []
            for pt in plot:
                pt_value, pt_time = pt
                if pt_value < self.value_min:
                    pt_value = self.value_min
                if pt_value > self.value_max:
                    pt_value = self.value_max
                x = (time_left - pt_time) * time_pix
                y = vert_zero - (vert_pix * (pt_value - self.value_min))
                points.append((int(x), int(y)))
            chart.line(
                points,
                width=3,
                fill=self.color,
            )
        elif self.type in ["bar", "bars", "histogram"]:
            barwidth = int(self.update * time_pix * 0.8)
            for pt in plot:
                pt_value, pt_time = pt
                x = (time_left - pt_time) * time_pix
                y = vert_zero - (vert_pix * (pt_value - self.value_min))
                bbox = [(x, y), (x + barwidth, image.height)]  # ((int(x), int(y)))
                chart.rectangle(
                    bbox,
                    fill=self.color,
                )

        self._cached = image
        return self._cached

    def render(self):
        self.chart.button.render()


class ChartIcon(DrawAnimation):
    """Chart or Sparkline Icon

    Draws up to three

    Attributes:
        REPRESENTATION_NAME: [description]
        PARAMETERS: [description]
        }: [description]
        MIN_UPDATE_TIME: [description]
        DEFAULT_TIME_WIDTH: [description]
    """

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
        self.charts = {d["name"]: ChartData(chart=self, config=d) for d in self.chart_configs[:MAX_SPARKLINES]}

    def get_simulator_data(self):
        # Collects datarefs in each chart
        if self.datarefs is None:
            datarefs = set()
            for c in self.charts.values():
                datarefs = datarefs | c.get_simulator_data()
            self.datarefs = datarefs
        return self.datarefs

    def should_run(self):
        """
        I.e. only works with onoff activations.
        """
        return True

    def anim_start(self):
        if self.running:
            logger.warning(f"chart {self.name} already running")
            return
        for c in self.charts.values():
            if c.auto_update:
                c.start()
        self.running = True

    def anim_stop(self):
        if not self.running:
            return
        for c in self.charts.values():
            if c.auto_update:
                c.stop()
        self.running = False

    def get_image_for_icon(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        self.icon_color = self._representation_config.get("chart-bg-color", self.cockpit_texture)
        self.icon_texture = self._representation_config.get("chart-bg-texture", self.cockpit_color)

        inside = round(0.04 * ICON_SIZE + 0.5)
        top_of_chart = int(ICON_SIZE / 8 + inside)

        bg = self.button.deck.get_icon_background(
            name=self.button_name(),
            width=ICON_SIZE,
            height=ICON_SIZE,
            texture_in=self.icon_color,
            color_in=self.icon_texture,
            use_texture=True,
            who="Chart",
        )
        bg_draw = ImageDraw.Draw(bg)

        # Horizontal axis
        avail = bg.height - 2 * inside
        rule_color = "white"
        rule_width = 2
        height = inside + avail * self.rule_height / 100 - int(rule_width / 2)
        bg_draw.line(
            [(0, bg.height - height), (bg.width, bg.height - height)],
            width=rule_width,
            fill=rule_color,
        )

        # Horiz ticks later
        # No vertical axis
        # Vert ticks later: 0-100? ~= normalisation

        # Stack partial images
        for c in self.charts.values():
            image = c.get_image_for_icon()
            bg.alpha_composite(image, [inside, top_of_chart])

        return bg
