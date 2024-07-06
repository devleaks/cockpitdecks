# ###########################
# Abstract base class for XP Weather icons.
# These buttons are highly XP specific.
#
import logging
import random

from PIL import Image, ImageDraw

from cockpitdecks import ICON_SIZE, now
from cockpitdecks.resources.iconfonts import (
    WEATHER_ICONS,
    WEATHER_ICON_FONT,
    DEFAULT_WEATHER_ICON,
)
from cockpitdecks.resources.color import light_off, TRANSPARENT_PNG_COLOR
from .draw import DrawBase

logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)
# logger.setLevel(logging.DEBUG)


class XPWeatherBaseIcon(DrawBase):
    """
    Icon with background weather image and text laid over
    """

    REPRESENTATION_NAME = "weather-base"

    PARAMETERS = {
        "speed": {"type": "integer", "prompt": "Refresh weather (seconds)"},
        "Refresh location": {"type": "integer", "prompt": "Refresh location (seconds)"},
        "location": {"type": "string", "prompt": "Location"},
    }

    MIN_UPDATE = 600  # seconds between two station updates

    def __init__(self,  button: "Button"):
        self._inited = False
        self._moved = False  # True if we get Metar for location at (lat, lon), False if Metar for default station
        self._upd_calls = 0
        self._upd_count = 0

        self.weather = None
        self.weather_icon = None

        DrawBase.__init__(self, button=button)

        self._weather_last_updated = None
        self._icon_last_updated = None
        self._cache = None

    def init(self):
        if self._inited:
            return
        self._inited = True
        logger.debug(f"inited")

    def update_weather(self) -> bool:
        self.weather_icon = self.select_weather_icon()
        self._weather_last_updated = now()
        return True

    def is_updated(self, force: bool = False) -> bool:
        updated = False
        if self._weather_last_updated is None:
            updated = self.update_weather()
        else:
            diff = now().timestamp() - self._weather_last_updated.timestamp()
            if diff > XPWeatherBaseIcon.MIN_UPDATE:
                updated = self.update_weather()
        return updated

    def get_image_for_icon(self):
        logger.debug(f"updating ({self._upd_count}/{self._upd_calls})..")
        if not self.is_updated() and self._cache is not None:
            logger.debug(f"..not updated, using cache")
            return self._cache

        self._upd_count = self._upd_count + 1
        self._icon_last_updated = now()

        image = Image.new(mode="RGBA", size=(ICON_SIZE, ICON_SIZE), color=TRANSPARENT_PNG_COLOR)  # annunciator text and leds , color=(0, 0, 0, 0)
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
        logger.debug(f"icon: {self.weather_icon}")
        icon_text = WEATHER_ICONS.get(self.weather_icon)
        if icon_text is None:
            logger.warning(f"icon: {self.weather_icon} not found, using default")
            icon_text = WEATHER_ICONS.get(DEFAULT_WEATHER_ICON)
            if icon_text is None:
                logger.warning(f"default icon not found, using default")
                icon_text = "\uf00d"
        draw.text(
            (w, h),
            text=icon_text,
            font=font,
            anchor="mm",
            align="center",
            fill=light_off(icon_color, 0.6),
        )  # (image.width / 2, 15)

        # Weather Data
        lines = self.get_lines()

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
                draw.text(
                    (w, h),
                    text=line.strip(),
                    font=font,
                    anchor=p + "m",
                    align=a,
                    fill=self.label_color,
                )  # (image.width / 2, 15)
                h = h + il
        else:
            logger.warning(f"no summary ({icao})")

        # Paste image on cockpit background and return it.
        bg = self.button.deck.get_icon_background(
            name=self.button_name(),
            width=ICON_SIZE,
            height=ICON_SIZE,
            texture_in=self.icon_texture,
            color_in=self.icon_color,
            use_texture=True,
            who="Weather",
        )
        bg.alpha_composite(image)
        self._cache = bg
        return self._cache

    def get_lines(self) -> list:
        lines = list()
        lines.append(f"Abstract")
        return lines

    def select_weather_icon(self):
        return self.select_random_weather_icon()

    def select_random_weather_icon(self):
        return random.choice(list(WEATHER_ICONS.keys()))

    def describe(self) -> str:
        return "The representation is specific to X-Plane, it is the base for weather information display."
