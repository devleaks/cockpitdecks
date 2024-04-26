# ###########################
# Button that displays the real weather in X-Plane.
#
# It gets updated when real wheather changes.
# These buttons are highly XP specific.
#
import logging

from cockpitdecks import now
from .xp_wb import XPWeatherBaseIcon
from .xp_wd import DISPLAY_DATAREFS_REGION, DISPLAY_DATAREFS_AIRCRAFT

logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)
# logger.setLevel(logging.DEBUG)


class RealWeatherIcon(XPWeatherBaseIcon):
    """
    Depends on simulator weather
    """

    REPRESENTATION_NAME = "weather-real"

    MIN_UPDATE = 600  # seconds between two station updates

    def __init__(self, config: dict, button: "Button"):
        self.weather = config.get("real-weather", {})
        self.mode = self.weather.get("mode", "region")

        XPWeatherBaseIcon.__init__(self, config=config, button=button)

        # Working variables
        self.display_datarefs = DISPLAY_DATAREFS_REGION if self.mode == "region" else DISPLAY_DATAREFS_AIRCRAFT
        self.weather_datarefs = self.display_datarefs.values()

    def init(self):
        if self._inited:
            return
        self.weather_icon = self.select_weather_icon()
        self._inited = True
        logger.debug(f"inited")

    def get_datarefs(self):
        return list(self.weather_datarefs)

    def is_updated(self, force: bool = False) -> bool:
        # Updates weather icon and information every RealWeatherIcon.MIN_UPDATE seconds
        updated = False
        self._upd_calls = self._upd_calls + 1
        if self._weather_last_updated is None:
            self.weather_icon = self.select_weather_icon()
            updated = True
            self._weather_last_updated = now()
            logger.info(f"updated Real weather")
        else:
            diff = now().timestamp() - self._weather_last_updated.timestamp()
            if diff > RealWeatherIcon.MIN_UPDATE:
                self.weather_icon = self.select_weather_icon()
                updated = True
                self._weather_last_updated = now()
                logger.info(f"updated Real weather")
            else:
                logger.debug(f"Real weather does not need updating")
        return updated

    def get_lines(self) -> list:
        lines = list()
        lines.append(f"Mode: {self.mode}")
        press = self.button.get_dataref_value(self.display_datarefs["press"])
        if press is not None:
            press = int(press / 100)
        lines.append(f"Press: {press}")
        temp = self.button.get_dataref_value(self.display_datarefs["temp"])
        lines.append(f"Temp: {temp}")
        dewp = self.button.get_dataref_value(self.display_datarefs["dewp"])
        lines.append(f"DewP:{dewp}")  # "sim/weather/region/sealevel_temperature_c"
        vis = self.button.get_dataref_value(self.display_datarefs["vis"])
        lines.append(f"Vis: {vis} sm")
        wind_dir = self.button.get_dataref_value(self.display_datarefs["wind_dir"])
        wind_speed = self.button.get_dataref_value(self.display_datarefs["wind_speed"])
        lines.append(f"Winds: {wind_speed} m/s {wind_dir}°")
        return lines
