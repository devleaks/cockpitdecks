# ###########################
# Button that displays the real weather in X-Plane.
#
# It gets updated when real wheather changes.
# These buttons are highly XP specific.
#
from datetime import datetime
import logging

from cockpitdecks import now
from .xp_wb import XPWeatherBaseIcon
from .xp_wd import XPWeatherData


logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)
# logger.setLevel(logging.DEBUG)


class XPRealWeatherIcon(XPWeatherBaseIcon):
    """
    Depends on simulator weather
    """

    REPRESENTATION_NAME = "xp-real-weather"

    MIN_UPDATE = 600  # seconds between two station updates

    def __init__(self, button: "Button"):
        self.weather = button._config.get(self.REPRESENTATION_NAME, {})
        self.mode = self.weather.get("mode", "region")

        self.xpweather = None

        self._wu_count = 0
        self._upd_calls = 0
        self._weather_last_updated = None
        self._icon_last_updated = None
        self._cache_metar = None
        self._cache = None

        XPWeatherBaseIcon.__init__(self, button=button)

        # Working variables
        self.collector = self.button.sim.collector  # shortcut
        self.all_collections = ["weather"] + [f"cloud#{i}" for i in range(3)] + [f"wind#{i}" for i in range(13)]

    def init(self):
        if self._inited:
            return
        self.weather_icon = self.select_weather_icon()
        self._inited = True
        logger.debug(f"inited")

    def update_weather(self):
        self.xpweather = XPWeatherData()
        if self._cache_metar is not None:
            if self._cache_metar == self.xpweather.make_metar():
                logger.debug(f"XP weather unchanged")
                return False  # weather unchanged
        self._cache_metar = self.xpweather.make_metar()
        self.weather_icon = self.select_weather_icon()
        self._weather_last_updated = now()
        # self.notify_weather_updated()
        logger.info(f"XP weather updated: {self._cache_metar}")
        logger.debug(self.xpweather.get_metar_desc(self._cache_metar))
        return True

    def is_updated(self, force: bool = False) -> bool:
        self._upd_calls = self._upd_calls + 1
        if self.update_weather():
            if self._icon_last_updated is not None:
                return self._weather_last_updated > self._icon_last_updated
            return True
        return False

    def get_lines(self) -> list:
        lines = []

        if self.xpweather is None:
            lines.append(f"Mode: {self.mode}")
            lines.append("No weather")
            return lines

        dt = "NO TIME"
        if self.xpweather.last_updated is not None:
            lu = datetime.fromtimestamp(self.xpweather.last_updated).strftime("%d %H:%M")
        lines.append(f"{dt} /M:{self.mode[0:4]}")

        press = round(self.xpweather.weather.qnh / 100, 0)
        lines.append(f"Press: {press}")

        temp = round(self.xpweather.weather.temp, 1)
        lines.append(f"Temp: {temp}")

        print(">>>>>>", self.xpweather.weather.wind_speed)

        idx = 0
        dewp = round(self.xpweather.wind_layers[idx].dew_point, 1)
        lines.append(f"DewP:{dewp} (L{idx})")

        vis = round(self.xpweather.weather.visibility, 1)
        lines.append(f"Vis: {vis} sm")

        wind_dir = round(self.xpweather.wind_layers[idx].direction)
        wind_speed = round(self.xpweather.wind_layers[idx].speed_kts, 1)
        lines.append(f"Winds: {wind_speed} m/s {wind_dir}° (L{idx})")

        return lines

    def describe(self) -> str:
        return "The representation is specific to X-Plane and show X-Plane internal weather fetched from wind and cloud layers."
