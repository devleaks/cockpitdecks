# ###########################
# Button that displays the real weather in X-Plane.
#
# It gets updated when real wheather changes.
# These buttons are highly XP specific.
#
import logging

from cockpitdecks import now
from .xp_wb import XPWeatherBaseIcon
from .xp_wd import WEATHER_LOCATION

logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)
# logger.setLevel(logging.DEBUG)

# What gets displayed
DISPLAY_DATAREFS_AIRCRAFT = {
    "press": "sim/weather/aircraft/qnh_pas",
    "temp": "sim/weather/aircraft/temperature_ambient_deg_c",
    "dewp": "sim/weather/aircraft/dewpoint_deg_c",
    "vis": "sim/weather/aircraft/visibility_reported_sm",
    "wind_dir": "sim/weather/aircraft/wind_direction_degt",
    "wind_speed": "sim/weather/aircraft/wind_speed_msc",
}

DISPLAY_DATAREFS_REGION = {
    "press": "sim/weather/region/sealevel_pressure_pas",
    "temp": "sim/weather/region/sealevel_temperature_c",
    "dewp": "sim/weather/region/dewpoint_deg_c",
    "vis": "sim/weather/region/visibility_reported_sm",
    "wind_dir": "sim/weather/region/wind_direction_degt",
    "wind_speed": "sim/weather/region/wind_speed_msc",
}


class XPWeatherSummaryIcon(XPWeatherBaseIcon):
    """
    Depends on simulator weather
    """

    REPRESENTATION_NAME = "xp-weather-summary"

    MIN_UPDATE = 600  # seconds between two station updates

    def __init__(self, button: "Button"):
        self.weather = button._config.get(self.REPRESENTATION_NAME, {})
        self.mode = self.weather.get("mode", "region")

        XPWeatherBaseIcon.__init__(self, button=button)

        # Working variables
        self.display_datarefs = DISPLAY_DATAREFS_AIRCRAFT if self.mode == WEATHER_LOCATION.AIRCRAFT.value else DISPLAY_DATAREFS_REGION
        self.weather_datarefs = set(self.display_datarefs.values())

    def describe(self) -> str:
        return "The representation is specific to X-Plane and show X-Plane internal weather fetched from datarefs."

    def init(self):
        if self._inited:
            return
        self.weather_icon = self.select_weather_icon()
        self._inited = True
        logger.debug(f"inited")

    def get_datarefs(self) -> set:
        return self.weather_datarefs

    def is_updated(self, force: bool = False) -> bool:
        # Updates weather icon and information every XPWeatherSummaryIcon.MIN_UPDATE seconds
        updated = False
        self.inc("update")
        if self._weather_last_updated is None:
            self.weather_icon = self.select_weather_icon()
            updated = True
            self._weather_last_updated = now()
            logger.info(f"updated Real weather")
        else:
            diff = now().timestamp() - self._weather_last_updated.timestamp()
            if diff > XPWeatherSummaryIcon.MIN_UPDATE:
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
