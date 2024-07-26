# ###########################
# Buttons that are drawn on render()
#
import logging
import threading

from cockpitdecks import ICON_SIZE, now

from cockpitdecks.resources.color import convert_color
from .draw_animation import DrawAnimation
from cockpitdecks.value import Value

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


#
# ###############################
# DYNAMIC CHARTS
#
#
class ChartData:

    def __init__(self, chart, config: dict) -> None:
        self._config = config
        self.chart = chart

        self.name = config.get("name")

        self.datarefs = None

        self.type = config.get("type", "line")
        self.value_min = config.get("value-min", 0)
        self.value_max = config.get("value-max", 100)
        self.keep = config.get("keep", 10)
        self.update = config.get("update")
        self.scale = config.get("scale", 1)
        self.color = config.get("color", "grey")
        self.color = convert_color(self.color)

        self.value = Value(self.name, config=config, button=chart.button)
        self._stop = None

        self.data = []
        self.last_data = now().timestamp()

        self.init()

    def init(self):
        if self.update is not None and self.update > 0:
            self._stop = threading.Event()
            self.thread = threading.Thread(target=self.start, name=f"ChartData:{self.name}")
            self.thread.start()

    def start(self):
        logger.info(f"chart {self.name} started")
        while not self._stop.wait(self.update):
            r = self.get_value()
            self.add(r)
        logger.info(f"chart {self.name} stopped")

    def stop(self):
        if self._stop is not None:
            self._stop.set()

    def get_datarefs(self) -> set:
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
        self.last_data = timestamp if timestamp is not None else now().timestamp()
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
            datarefs = set()
            for c in self.charts.values():
                datarefs = datarefs | c.get_datarefs()
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

        if self.speed is None:
            for c in self.charts.values():
                c.add(c.get_value())

        time_pix = image.width / self.time_width
        time_left = now().timestamp()

        # Preprocess available data, there might not be a lot at the beginning...
        # For each data, get min, max, scaled min, scaled max, number to keep
        stats = {d.name: d.get_stats() for d in self.charts.values()}
        rule_color = "white"

        # data, data_format, data_font, data_color, data_size, data_position = self.get_text_detail(self.chart, "data")

        data_color = "white"
        data_font = "D-DIN"
        data_size = 32
        font = self.get_font(data_font, data_size)
        # test: draw something
        # chart.text(
        #     (int(image.width / 2), int(image.height / 2)),
        #     text=self.REPRESENTATION_NAME,
        #     font=font,
        #     anchor="mm",
        #     align="center",
        #     fill=data_color,
        # )

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
            vert_pix = image.height / (c.value_max - c.value_min)
            # print(plot)
            if c.type == "line":
                points = []
                for pt in plot:
                    pt_value, pt_time = pt
                    if pt_value < c.value_min:
                        pt_value = c.value_min
                    if pt_value > c.value_max:
                        pt_value = c.value_max
                    x = (time_left - pt_time) * time_pix
                    y = vert_pix * (pt_value - c.value_min)
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
