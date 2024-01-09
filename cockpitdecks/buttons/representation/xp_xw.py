# ###########################
# Button that displays the real weather in X-Plane.
#
# It gets updated when real wheather changes.
# These buttons are highly XP specific.
#
import os
import logging
import random
from datetime import datetime

from PIL import Image, ImageDraw

from cockpitdecks import ICON_SIZE, now
from cockpitdecks.resources.iconfonts import WEATHER_ICONS, WEATHER_ICON_FONT, DEFAULT_WEATHER_ICON
from cockpitdecks.resources.color import convert_color, light_off, TRANSPARENT_PNG_COLOR
from cockpitdecks.simulator import Dataref
from .xp_wb import XPWeatherBaseIcon
from .xp_wm import XPWeather


logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)
# logger.setLevel(logging.DEBUG)


class XPWeatherIcon(XPWeatherBaseIcon):
    """
    Depends on simulator weather
    """

    MIN_UPDATE = 600  # seconds between two station updates

    def __init__(self, config: dict, button: "Button"):
        self.weather = config.get("xp-weather", {})
        self.mode = self.weather.get("mode", "region")

        self.xpweather = None
        self._wu_count = 0
        self._weather_last_updated = None
        self._icon_last_updated = None
        self._cache_metar = None
        self._cache = None

        XPWeatherBaseIcon.__init__(self, config=config, button=button)

        # Working variables
        self.collector = self.button.sim.collector  # shortcut
        self.all_collections = ["weather"] + [f"cloud#{i}" for i in range(3)] + [f"wind#{i}" for i in range(13)]

    def init(self):
        if self._inited:
            return
        self.weather_icon = self.select_weather_icon()
        self._inited = True
        logger.debug(f"inited")

    def notify_weather_updated(self):
        if self.xpweather is not None and self.button._activation.writable_dataref is not None:
            self._wu_count = self._wu_count + 1
            self.button._activation._write_dataref(self.button._activation.writable_dataref, float(self._wu_count))
            logger.info(f"updated XP weather at {self._weather_last_updated.strftime('%H:%M:%S')} ({self._wu_count})")

    def collect_all_datarefs(self):
        drefs = {}
        for cname in self.all_collections:
            drefs = drefs | self.collector.collections[cname].datarefs
        return drefs

    def collect_last_updated(self):
        last_updated = None
        for name, collection in [(name, self.collector.collections.get(name)) for name in self.all_collections]:
            if collection is None:
                logger.debug(f"collection {name} missing")
                return None

            if collection.last_completed is None:
                logger.debug(f"collection {name} not completed")
                return None

            if last_updated is not None:
                if last_updated < collection.last_completed:
                    last_updated = collection.last_completed
            else:
                last_updated = collection.last_completed
            # logger.debug(f"collection {collection.name} completed at {collection.last_completed}")

        logger.debug(f"all collections completed at {last_updated}")
        return last_updated

    def update_weather(self):
        last_updated = self.collect_last_updated()
        if last_updated is not None:
            self.xpweather = XPWeather(self.collect_all_datarefs())
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
        logger.debug(f"Dataref collector has not completed")
        return False

    def is_updated(self) -> bool:
        self._upd_calls = self._upd_calls + 1
        if self.update_weather():
            if self._icon_last_updated is not None:
                return self._weather_last_updated > self._icon_last_updated
            return True
        return False

    def get_lines(self) -> list:
        lines = list()

        if self.xpweather is None:
            lines.append(f"Mode: {self.mode}")
            lines.append(f"No weather")
            return lines

        lu = self.collect_last_updated()
        if lu is not None:
            dt = lu.strftime("%d %H:%M")
        else:
            dt = "NO TIME"
        lines.append(f"{dt} /M:{self.mode[0:4]}")

        press = round(self.xpweather.weather.qnh / 100)
        lines.append(f"Press: {press}")

        temp = round(self.xpweather.weather.temp, 1)
        lines.append(f"Temp: {temp}")

        idx = 0
        dewp = round(self.xpweather.wind_layers[idx].dew_point, 1)
        lines.append(f"DewP:{dewp} (L{idx})")

        vis = round(self.xpweather.weather.visibility, 1)
        lines.append(f"Vis: {vis} sm")

        wind_dir = round(self.xpweather.wind_layers[idx].direction)
        wind_speed = round(self.xpweather.weather.wind_speed, 1)
        lines.append(f"Winds: {wind_speed} m/s {wind_dir}° (L{idx})")

        return lines
