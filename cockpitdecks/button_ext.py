# ###########################
# Buttons that are drawn on render()
#
# Buttons were isolated here bevcause they use quite larger packages (avwx-engine),
# call and rely on external services.
#
import logging
import random
import re
from functools import reduce
from datetime import datetime

from avwx import Metar, station

from PIL import Image, ImageDraw

from .constant import WEATHER_ICON_FONT, ICON_FONT, ICON_SIZE
from .color import convert_color, light_off
from .resources.icons import icons as FA_ICONS        # Font Awesome Icons
from .resources.weathericons import WEATHER_ICONS     # Weather Icons
from .button_draw import DrawBase, DrawAnimation
from .button_annunciator import TRANSPARENT_PNG_COLOR


logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)
# logger.setLevel(logging.DEBUG)


class WI:
    """
    Simplified weather icon
    """
    I_S = [
        "_sunny",
        "_cloudy",
        "_cloudy_gusts",
        "_cloudy_windy",
        "_fog",
        "_hail",
        "_haze",
        "_lightning",
        "_rain",
        "_rain_mix",
        "_rain_wind",
        "_showers",
        "_sleet",
        "_sleet_storm",
        "_snow",
        "_snow_thunderstorm",
        "_snow_wind",
        "_sprinkle",
        "_storm_showers",
        "_sunny_overcast",
        "_thunderstorm",
        "_windy",
        "_cloudy_high",
        "_light_wind"
    ]

    DB = [
        {
            "iconName":   "wi_cloud",
            "day":        2,
            "descriptor": [],
            "precip":     "",
            "visibility": [""],
            "cloud":      ["BKN"],
            "wind":       [0, 21]
        },
        {
            "iconName":   "wi_cloudy",
            "day":        2,
            "descriptor": [],
            "precip":     "",
            "visibility": [""],
            "cloud":      ["OVC"],
            "wind":       [0, 21]
        },
        {
            "iconName":   "wi_cloudy_gusts",
            "day":        2,
            "descriptor": [],
            "precip":     "",
            "visibility": [""],
            "cloud":      ["SCT", "BKN", "OVC"],
            "wind":       [22, 63]
        },
        {
            "iconName":   "wi_rain",
            "day":        2,
            "descriptor": [],
            "precip":     "RA",
            "visibility": [""],
            "cloud":      [""],
            "wind":       [0, 21]
        },
        {
            "iconName":   "wi_rain_wind",
            "day":        2,
            "descriptor": [],
            "precip":     "RA",
            "visibility": [""],
            "cloud":      [""],
            "wind":       [22, 63]
        },
        {
            "iconName":   "wi_showers",
            "day":        2,
            "descriptor": ["SH"],
            "precip":     "",
            "visibility": [""],
            "cloud":      [""],
            "wind":       [0, 63]
        },
        {
            "iconName":   "wi_fog",
            "day":        2,
            "descriptor": [],
            "precip":     "",
            "visibility": ["BR", "FG"],
            "cloud":      [""],
            "wind":       [0, 63]
        },
        {
            "iconName":   "wi_storm_showers",
            "day":        2,
            "descriptor": ["TS", "SH"],
            "precip":     "",
            "visibility": [""],
            "cloud":      [""],
            "wind":       [0, 63]
        },
        {
            "iconName":   "wi_thunderstorm",
            "day":        2,
            "descriptor": ["TS"],
            "precip":     "",
            "visibility": [""],
            "cloud":      [""],
            "wind":       [0, 63]
        },
        {
            "iconName":   "wi_day_sunny",
            "day":        1,
            "descriptor": [],
            "precip":     "",
            "visibility": ["CAVOK", "NCD"],
            "cloud":      [""],
            "wind":       [0, 21]
        },
        {
            "iconName":   "wi_windy",
            "day":        1,
            "descriptor": [],
            "precip":     "",
            "visibility": ["CAVOK", "NCD"],
            "cloud":      [""],
            "wind":       [22, 33]
        },
        {
            "iconName":   "wi_strong_wind",
            "day":        1,
            "descriptor": [],
            "precip":     "",
            "visibility": ["CAVOK", "NCD"],
            "cloud":      [""],
            "wind":       [34, 63]
        },
        {
            "iconName":   "wi_night_clear",
            "day":        0,
            "descriptor": [],
            "precip":     "",
            "visibility": ["CAVOK", "NCD"],
            "cloud":      [""],
            "wind":       [0, 21]
        },
        {
            "iconName":   "wi_day_cloudy",
            "day":        1,
            "descriptor": [],
            "precip":     "",
            "visibility": [""],
            "cloud":      ["FEW", "SCT"],
            "wind":       [0, 21]
        },
        {
            "iconName":   "wi_night_alt_cloudy",
            "day":        2,
            "descriptor": [],
            "precip":     "",
            "visibility": [""],
            "cloud":      ["FEW", "SCT"],
            "wind":       [0, 21]
        },
        {
            "iconName":   "wi_day_cloudy_gusts",
            "day":        0,
            "descriptor": [],
            "precip":     "",
            "visibility": [""],
            "cloud":      ["SCT", "BKN", "OVC"],
            "wind":       [22, 63]
        },
        {
            "iconName":   "wi_night_alt_cloudy_gusts",
            "day":        1,
            "descriptor": [],
            "precip":     "",
            "visibility": [""],
            "cloud":      ["SCT", "BKN", "OVC"],
            "wind":       [22, 63]
        },
        {
            "iconName":   "wi_day_cloudy_windy",
            "day":        1,
            "descriptor": [],
            "precip":     "",
            "visibility": [""],
            "cloud":      ["FEW", "SCT"],
            "wind":       [22, 63]
        },
        {
            "iconName":   "wi_night_alt_cloudy_windy",
            "day":        2,
            "descriptor": [],
            "precip":     "",
            "visibility": [""],
            "cloud":      ["FEW", "SCT"],
            "wind":       [22, 63]
        },
        {
            "iconName":   "wi_snow",
            "day":        2,
            "descriptor": [],
            "precip":     "SN",
            "visibility": [""],
            "cloud":      [""],
            "wind":       [0, 21]
        },
        {
            "iconName":   "wi_snow_wind",
            "day":        2,
            "descriptor": [],
            "precip":     "SN",
            "visibility": [""],
            "cloud":      [""],
            "wind":       [22, 63]
        },
    ]

    def __init__(self, day: bool, cover=float, wind=float, precip=float, special=float):
        self.day = day          # night=False, time at location (local time)
        self.cover = cover      # 0=clear, 1=overcast
        self.wind = wind        # 0=no wind, 1=storm
        self.precip = precip    # 0=none, 1=rain1, 2=rain2, 3=snow, 4=hail
        self.special = special  # 0=none, 1=fog, 2=sandstorm

    def icon(self):
        return f"wi_{'day' if self.day else 'night'}" + random.choice(WI.I_S)

    # @staticmethod
    # def check():
    #     err = 0
    #     for i in WI.DB:
    #         if i["iconName"] not in WEATHER_ICONS.keys():
    #             logger.error(f"check: invalid icon {i['iconName']}")
    #             err = err + 1
    #     if err > 0:
    #         logger.error(f"check: {err} invalid icons")

class WeatherIcon(DrawAnimation):
    """
    Depends on avwx-engine
    """
    def __init__(self, config: dict, button: "Button"):
        self.weather = config.get("weather")
        if self.weather is not None and type(self.weather) == dict:
            config["animation"] = config.get("weather")
        else:
            config["animation"] = {}
            self.weather = {}

        DrawAnimation.__init__(self, config=config, button=button)

        self._last_updated = None
        self._cache = None
        self.station = self.get_station()
        if self.station is None:
            self.station = self.weather.get("station", "EBBR")

        # "Animation" (refresh)
        speed = self.weather.get("refresh", 30)     # minutes, should be ~30 minutes
        self.speed = int(speed) * 60                # minutes

        # Working variables
        self.metar = None
        self.weather_icon = None

        # Init
        self.update()
        self.anim_start()

    def get_datarefs(self):
        return [
            "sim/flightmodel/position/latitude",
            "sim/flightmodel/position/longitude",
            "sim/cockpit2/clock_timer/local_time_hours"
        ]

    def should_run(self) -> bool:
        """
        Check conditions to animate the icon.
        In this case, always runs
        """
        return True

    def animate(self):
        self.update()
        return super().animate()

    def get_station(self):
        MIN_UPDATE = 600  # seconds
        if self._last_updated is not None:
            now = datetime.now()
            diff = now.timestamp() - self._last_updated.timestamp()
            if diff < MIN_UPDATE:
                logger.debug(f"get_station: updated less than {MIN_UPDATE} secs. ago ({diff}), skipping..")
                return None
            logger.debug(f"get_station: updated  {diff} secs. ago")

        lat = self.button.get_dataref_value("sim/flightmodel/position/latitude")
        lon = self.button.get_dataref_value("sim/flightmodel/position/longitude")

        logger.debug(f"get_station: closest station to lat={lat},lon={lon}")
        nearest = station.nearest(lat=lat, lon=lon, max_coord_distance=150000)
        logger.debug(f"get_station: closest={nearest}")
        if type(nearest) == dict and len(nearest) > 1:
            s = nearest["station"]
            logger.debug(f"get_station: closest station is {s.icao}")
            return s.icao
        elif type(nearest) == list and len(nearest) > 0:
            s = list(nearest)[0]["station"]
            logger.debug(f"get_station: closest station is {s.icao}")
            return s.icao
        logger.warning(f"get_station: no close station")
        return None

    def update(self, force: bool = False) -> bool:
        """
        Creates or updates Metar. Call to avwx may fail, so it is wrapped into try/except block

        :param      force:  The force
        :type       force:  bool

        :returns:   { description_of_the_return_value }
        :rtype:     bool
        """
        updated = False
        if force:
            self._last_updated = None
        new = self.get_station()
        if new is not None and new != self.station:
            self.station = new
            logger.info(f"update: station changed to {self.station}")
            self.button._config["label"] = new
            try:
                self.metar = Metar(self.station)
                self._last_updated = datetime.now()
                updated = True
            except:
                self.metar = None
                logger.warning(f"update: Metar not created", exc_info=True)
        elif new is not None and self.metar is not None:
            try:
                self.metar.update()
                self._last_updated = datetime.now()
                updated = True
            except:
                self.metar = None
                logger.warning(f"update: Metar not updated", exc_info=True)
        elif self.station is not None and self.metar is None:
            try:
                self.metar = Metar(self.station)
                self._last_updated = datetime.now()
                updated = True
            except:
                self.metar = None
                logger.warning(f"update: Metar not created", exc_info=True)
        if updated:
            logger.info(f"update: Metar updated for {self.station}")
            self.weather_icon = self.selectWeatherIcon()
        return updated

    def get_image_for_icon(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """

        if not self.update():
            self._cache

        image = Image.new(mode="RGBA", size=(ICON_SIZE, ICON_SIZE), color=TRANSPARENT_PNG_COLOR)                     # annunciator text and leds , color=(0, 0, 0, 0)
        draw = ImageDraw.Draw(image)
        inside = round(0.04 * image.width + 0.5)

        # Weather Icon
        icon_font = self._config.get("icon-font", WEATHER_ICON_FONT)
        icon_size = int(image.width / 2)
        icon_color = "white"
        font = self.get_font(icon_font, icon_size)
        inside = round(0.04 * image.width + 0.5)
        w = image.width / 2
        h = image.height / 2
        draw.text((w, h),  # (image.width / 2, 15)
                  text=self.weather_icon if self.weather_icon is not None else "\uf00d",
                  font=font,
                  anchor="mm",
                  align="center",
                  fill=light_off(icon_color, 0.2))

        # Weather Data
        lines = None
        try:
            if self.metar is not None and self.metar.summary:
                lines = self.metar.summary.split(",")  # ~ 6-7 short lines
        except:
            lines = None
            logger.warning(f"get_image_for_icon: Metar has no summary")
            # logger.warning(f"get_image_for_icon: Metar has no summary", exc_info=True)

        if lines is not None:
            text_font = self._config.get("weather-font", self.label_font)
            text_size = int(image.width / 10)
            font = self.get_font(text_font, text_size)
            w = inside
            p = "l"
            a = "left"
            h = image.height / 3
            il = text_size
            for line in lines:
                draw.text((w, h),  # (image.width / 2, 15)
                          text=line.strip(),
                          font=font,
                          anchor=p+"m",
                          align=a,
                          fill=self.label_color)
                h = h + il
        else:
            logger.warning(f"get_image_for_icon: no metar summary")

        # Paste image on cockpit background and return it.
        bg = self.button.deck.get_icon_background(name=self.button_name(), width=ICON_SIZE, height=ICON_SIZE, texture_in=self.icon_texture, color_in=self.icon_color, use_texture=True, who="Weather")
        bg.alpha_composite(image)
        self._cache = bg.convert("RGB")
        return self._cache

    def is_day(self, sunrise: int = 5, sunset: int = 19) -> bool:
        # Numerous alternative possible
        # This one uses the simulator local time
        hours = self.button.get_dataref_value("sim/cockpit2/clock_timer/local_time_hours", default=12)
        return hours > sunrise and hours < sunset

    def get_sun(self) -> tuple:
        return (5, 19)

    def is_metar_day(self, sunrise: int = 5, sunset: int = 19) -> bool:
        # Deduce location and date/time from METAR. Month need to be guessed (default to current).
        #
        hours = self.button.get_dataref_value("sim/cockpit2/clock_timer/local_time_hours", default=12)
        return hours > sunrise and hours < sunset

    def selectWeatherIcon(self):
        # Needs improvement
        # Stolen from https://github.com/flybywiresim/efb
        icon = "wi_cloud"
        if self.metar is not None and self.metar.raw is not None:
            rawtext = self.metar.raw[13:]  # strip ICAO DDHHMMZ
            logger.debug(f"selectWeatherIcon: METAR {rawtext}")
            date = datetime.now();
            day = 1 if self.is_day() else 0
            precip = re.match("RA|SN|DZ|SG|PE|GR|GS", rawtext)
            if precip is None:
                precip = []
            logger.debug(f"selectWeatherIcon: PRECIP {precip}")
            wind = self.metar.data.wind_speed.value if hasattr(self.metar.data, "wind_speed") else 0
            logger.debug(f"selectWeatherIcon: WIND {wind}")
            findIcon = list(filter(lambda item:  (item["day"] == day or item["day"] == 2)
                                        and reduce(lambda x, y: x + y, [rawtext.find(desc) for desc in item["descriptor"]], 0) == len(item["descriptor"])
                                        and rawtext.find(item["precip"])
                                        and reduce(lambda x, y: x + y, [rawtext.find(cld) for cld in item["cloud"]], 0) > 0
                                        and (wind > item["wind"][0] and wind < item["wind"][1])
                                        and reduce(lambda x, y: x + y, [rawtext.find(vis) for vis in item["visibility"]], 0) > 0,
                              WI.DB))
            logger.debug(f"selectWeatherIcon: STEP 1 {findIcon}")
            l = len(findIcon)
            if l == 1:
                icon = findIcon[0]["iconName"]
            else:
                if l > 1:
                    findIcon2 = []
                    if len(precip) > 0:
                        findIcon2 = list(filter(lambda x: re("RA|SN|DZ|SG|PE|GR|GS").match(x["precip"]), findIcon))
                    else:
                        findIcon2 = list(filter(lambda x: x["day"] == day, findIcon))
                    logger.debug(f"selectWeatherIcon: STEP 2 {findIcon2}")
                    if len(findIcon2) > 0:
                        icon = findIcon2[0]["iconName"]
        else:
            logger.debug(f"selectWeatherIcon: no metar")
        logger.debug(f"selectWeatherIcon: returning {icon}")
        return WEATHER_ICONS.get(icon)

    def selectRandomWeatherIcon(self):
        # day or night
        # cloud cover
        # precipitation: type, quantity
        # wind: speed
        # currently random anyway...
        return random.choice(list(WEATHER_ICONS.values()))

