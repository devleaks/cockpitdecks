# ###########################
# Abstract Base Representation for weather icons.
# The ABC offerts basic update structures, just need
#  - A Weather data feed
#  - get_image_for_icon() to provide an iconic representation of the weather provided as above.
#
from __future__ import annotations
import logging
from threading import RLock
from datetime import datetime

from avwx import Station

from PIL import Image, ImageDraw

from cockpitdecks import ICON_SIZE
from cockpitdecks.resources.iconfonts import (
    WEATHER_ICONS,
    WEATHER_ICON_FONT,
    DEFAULT_WEATHER_ICON,
)
from cockpitdecks.resources.color import light_off, TRANSPARENT_PNG_COLOR
from cockpitdecks.resources.weather import WeatherData, WeatherDataListener
from cockpitdecks.resources.weathericon import WeatherIcon
from cockpitdecks.buttons.representation.draw_animation import DrawAnimation

logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)
# logger.setLevel(logging.DEBUG)


class WeatherBaseIcon(DrawAnimation, WeatherDataListener):
    """Base class for all weather iconic representations.
    Subclasses produce different iconic representations: Simple text, pages of text, station plot...
    This base class proposes a simple textual display of lines returned by the get_lines() function.
    Internally, the weather-type class is responsible for fetching weather data
    """

    REPRESENTATION_NAME = "weather-base-icon"

    DEFAULT_STATION = "EBBR"  # LFBO for Airbus?

    PARAMETERS = {
        "speed": {"type": "integer", "prompt": "Refresh weather (seconds)"},
        "Refresh location": {"type": "integer", "prompt": "Refresh location (seconds)"},
    }

    def __init__(self, button: "Button"):
        self.weather = button._config.get(self.REPRESENTATION_NAME)  # Weather specific config
        if self.weather is not None and isinstance(self.weather, dict):  # Add animation parameters for automatic update
            button._config["animation"] = button._config.get(self.REPRESENTATION_NAME)
        else:
            button._config["animation"] = {}
            self.weather = {}

        # Weather image management
        self._cache = None
        self._busy_updating = False  # need this for race condition during update (anim loop)

        # Working variables
        self.weather_data: WeatherData
        self.weather_icon: str | None = None
        self.weather_icon_factory = WeatherIcon()  # decorating weather icon image

        DrawAnimation.__init__(self, button=button)
        # Following parameters are overwritten by config

        icao = self.weather.get("station", self.DEFAULT_STATION)
        self.set_label(icao)

        # "Animation" (refresh) rate
        speed = self.weather.get("refresh", 30)  # minutes, should be ~30 minutes
        self.speed = int(speed) * 60  # minutes

        # This is for the weather icon in the background
        self.icon_color = self.weather.get("icon-color", self.get_attribute("text-color"))

    def __enter__(self):
        self._busy_updating = True
        logger.debug("updating..")

    def __exit__(self, type, value, traceback):
        self._busy_updating = False
        logger.debug("..updated")

    def init(self):
        if not self._inited:
            super().init()
            self._inited = True

    # #############################################
    # Weather data interface
    #
    def weather_changed(self):
        self.button.render()

    # #############################################
    # Cockpitdecks Representation interface
    #
    def should_run(self) -> bool:
        """
        Check conditions to animate the icon.
        In this case, always runs
        """
        return self._inited and self.button.on_current_page()

    def start(self):
        super().start()
        logger.info("starting weather surveillance")
        self.weather_data.start()

    def stop(self):
        super().stop()
        logger.info("stopping weather surveillance")
        self.weather_data.stop()

    def updated(self) -> bool:
        return False

    def set_label(self, label: str = "Weather"):
        self.button._config["label"] = label if label is not None else "Weather"

    def get_lines(self) -> list | None:
        return None

    def get_image_for_icon(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        with self:
            if self.updated() or self._cache is None:
                self.make_weather_image()

        return self._cache

    def make_weather_image(self):
        # Generic display text in small font on icon
        image = Image.new(mode="RGBA", size=(ICON_SIZE, ICON_SIZE), color=TRANSPARENT_PNG_COLOR)  # annunciator text and leds , color=(0, 0, 0, 0)
        draw = ImageDraw.Draw(image)
        inside = round(0.04 * image.width + 0.5)

        # Weather Icon in the background
        icon_font = self._config.get("icon-font", WEATHER_ICON_FONT)
        icon_size = int(image.width / 2)
        icon_color = self.icon_color
        font = self.get_font(icon_font, icon_size)
        inside = round(0.04 * image.width + 0.5)
        w = image.width / 2
        h = image.height / 2
        logger.debug(f"weather icon: {self.weather_icon}")
        icon_text = WEATHER_ICONS.get(self.weather_icon)
        final_icon = self.weather_icon
        if icon_text is None:
            logger.warning(f"weather icon '{self.weather_icon}' not found, using default ({DEFAULT_WEATHER_ICON})")
            final_icon = DEFAULT_WEATHER_ICON
            icon_text = WEATHER_ICONS.get(DEFAULT_WEATHER_ICON)
            if icon_text is None:
                logger.warning(f"default weather icon {DEFAULT_WEATHER_ICON} not found, using hardcoded default (wi_day_sunny)")
                final_icon = "wi_day_sunny"
                icon_text = "\uf00d"
        logger.info(f"weather icon: {final_icon} ({self.speed})")
        draw.text(
            (w, h),
            text=icon_text,
            font=font,
            anchor="mm",
            align="center",
            fill=light_off(icon_color, 0.8),
        )

        # Weather Data
        lines = self.get_lines()

        if lines is not None:
            text, text_format, text_font, text_color, text_size, text_position = self.get_text_detail(self._representation_config, "weather")
            if text_font is None:
                text_font = self.label_font
            if text_size is None:
                text_size = int(image.width / 10)
            if text_color is None:
                text_color = self.label_color
            font = self.get_font(text_font, text_size)
            w = inside
            p = "l"
            a = "left"
            h = image.height / 3
            il = text_size
            for line in lines:
                draw.text(
                    (w, h),
                    text=line.strip(),
                    font=font,
                    anchor=p + "m",
                    align=a,
                    fill=text_color,
                )
                h = h + il
        else:
            logger.warning("no weather information")

        # Paste image on cockpit background and return it.
        bg = self.button.deck.get_icon_background(
            name=self.button_name(),
            width=ICON_SIZE,
            height=ICON_SIZE,
            texture_in=self.cockpit_texture,
            color_in=self.cockpit_color,
            use_texture=True,
            who="Weather",
        )
        bg.alpha_composite(image)
        self._cache = bg
