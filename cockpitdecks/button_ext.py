# ###########################
# Buttons that are drawn on render()
#
# Buttons were isolated here bevcause they use quite larger packages (avwx-engine),
# call and rely on external services.
#
import logging
import random
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

    def __init__(self, day: bool, cover=float, wind=float, precip=float, special=float):
        self.day = day          # night=False, time at location (local time)
        self.cover = cover      # 0=clear, 1=overcast
        self.wind = wind        # 0=no wind, 1=storm
        self.precip = precip    # 0=none, 1=rain1, 2=rain2, 3=snow, 4=hail
        self.special = special  # 0=none, 1=fog, 2=sandstorm

    def icon(self):
        return f"wi_{'day' if self.day else 'night'}" + random.choice(WI.I_S)



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
            "sim/flightmodel/position/longitude"
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
            self.weather_icon = self.to_icon()
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
        bg = Image.new(mode="RGBA", size=(ICON_SIZE, ICON_SIZE), color=self.button.page.cockpit_color)
        # icon_bg = self.get_default_icon()
        # bg.paste(icon_bg)
        bg.alpha_composite(image)
        self._cache = bg.convert("RGB")
        return self._cache

    def to_icon(self):
        # day or night
        # cloud cover
        # precipitation: type, quantity
        # wind: speed
        # currently random anyway...
        return random.choice(list(WEATHER_ICONS.values()))

