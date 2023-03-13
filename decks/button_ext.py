# ###########################
# Buttons that are drawn on render()
#
# Buttons were isolated here bevcause they use quite larger packages (avwx-engine),
# call and rely on external services.
#
import logging
import random
from avwx import Metar, station

from PIL import Image, ImageDraw, ImageFont

from .constant import WEATHER_ICON_FONT, ICON_FONT
from .color import convert_color, light_off
from .resources.icons import icons as FA_ICONS        # Font Awesome Icons
from .resources.weathericons import WEATHER_ICONS     # Weather Icons
from .button_draw import DrawBase, DrawAnimation
from .button_annunciator import ICON_SIZE, TRANSPARENT_PNG_COLOR


logger = logging.getLogger("ButtonExternal")
# logger.setLevel(SPAM)
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

        self.station = self.get_station()
        if self.station is None:
            self.station = self.weather.get("station", "EBBR")

        # "Animation" (refresh)
        speed = self.weather.get("refresh", 30)     # minutes, should be ~30 minutes
        self.speed = int(speed) * 60                # minutes

        # Working variables
        self.metar = Metar(self.station)
        self.weather_icon = self.to_icon()

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


    def update(self) -> bool:
        updated = False
        new = self.get_station()
        if new is not None and new != self.station:
            self.station = new
            logger.info(f"update: station changed to {self.station}")
            self.metar = Metar(self.station)
            updated = True
        elif self.metar is not None:
            self.metar.update()
            updated = True
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
            return None

        image = Image.new(mode="RGBA", size=(ICON_SIZE, ICON_SIZE), color=TRANSPARENT_PNG_COLOR)                     # annunciator text and leds , color=(0, 0, 0, 0)
        draw = ImageDraw.Draw(image)
        inside = round(0.04 * image.width + 0.5)

        # Weather Icon
        icon_font = self._config.get("icon-font", WEATHER_ICON_FONT)
        icon_size = int(image.width / 2)
        icon_color = "white"
        fontname = self.get_font(icon_font)
        if fontname is None:
            logger.warning(f"get_image_for_icon: icon font not found, cannot overlay icon")
        else:
            font = ImageFont.truetype(fontname, icon_size)
            inside = round(0.04 * image.width + 0.5)
            w = image.width / 2
            h = image.height / 2
            draw.text((w, h),  # (image.width / 2, 15)
                      text=self.weather_icon,
                      font=font,
                      anchor="mm",
                      align="center",
                      fill=light_off(icon_color, 0.2))

        # Weather Data
        text_font = self._config.get("weather-font", self.label_font)
        fontname = self.get_font(text_font)
        if fontname is None:
            logger.warning(f"get_image_for_icon: text font not found, cannot overlay text")
        else:
            detailsize = int(image.width / 10)
            font = ImageFont.truetype(fontname, detailsize)
            w = inside
            p = "l"
            a = "left"
            h = image.height / 3
            il = detailsize
            if self.metar and self.metar.summary:
                lines = self.metar.summary.split(",")  # ~ 6-7 short lines
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
        bg = Image.new(mode="RGBA", size=(ICON_SIZE, ICON_SIZE), color=self.button.deck.cockpit_color)                     # annunciator text and leds , color=(0, 0, 0, 0)
        bg.alpha_composite(image)
        return bg.convert("RGB")

    def to_icon(self):
        # day or night
        # cloud cover
        # precipitation: type, quantity
        # wind: speed
        # currently random anyway...
        return random.choice(list(WEATHER_ICONS.values()))

