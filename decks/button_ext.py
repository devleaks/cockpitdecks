# ###########################
# Buttons that are drawn on render()
#
# Buttons were isolated here bevcause they use quite larger packages (avwx-engine),
# call and rely on external services.
#
import random
from avwx import Metar

from PIL import Image, ImageDraw, ImageFont

from .constant import WEATHER_ICON_FONT, ICON_FONT
from .color import convert_color, light_off
from .resources.icons import icons as FA_ICONS        # Font Awesome Icons
from .resources.weathericons import WEATHER_ICONS     # Weather Icons
from .button_draw import DrawBase
from .button_annunciator import ICON_SIZE, TRANSPARENT_PNG_COLOR


class WeatherIcon(DrawBase):

    def __init__(self, config: dict, button: "Button"):
        DrawBase.__init__(self, config=config, button=button)

        self.weather = config.get("weather")
        self.station = "EBBR"
        if self.weather is not None:
            self.station = self.weather.get("station", "EBBR")
        self.metar = Metar(self.station)
        self.weather_icon = self.to_icon()

    def update(self):
        if self.metar is not None:
            self.metar.update()
        else:
            self.metar = Metar(self.station)
        self.weather_icon = self.to_icon()

    def get_image_for_icon(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
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
            lines = self.metar.summary.split(",")  # ~ 6-7 short lines
            for line in lines:
                draw.text((w, h),  # (image.width / 2, 15)
                          text=line.strip(),
                          font=font,
                          anchor=p+"m",
                          align=a,
                          fill=self.label_color)
                h = h + il

        # Paste image on cockpit background and return it.
        bg = Image.new(mode="RGBA", size=(ICON_SIZE, ICON_SIZE), color=self.cockpit_color)                     # annunciator text and leds , color=(0, 0, 0, 0)
        bg.alpha_composite(image)
        return bg.convert("RGB")

    def to_icon(self):
        # day or night
        # cloud cover
        # precipitation: type, quantity
        # wind: speed
        # currently random anyway...
        return random.choice(list(WEATHER_ICONS.values()))

