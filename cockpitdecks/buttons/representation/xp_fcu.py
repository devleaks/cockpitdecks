# ###########################
# Representation that displays the content of sim/aircraft/view/acf_ICAO on an icon.
# These buttons are *highly* X-Plane and Toliss Airbus specific.
#
import logging

from PIL import Image, ImageDraw

from cockpitdecks import ICON_SIZE
from cockpitdecks.resources.color import TRANSPARENT_PNG_COLOR
from .draw import DrawBase

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

FCU_DATAREFS = {
    "1b": "AirbusFBW/FMA1b[:24]",
    "1g": "AirbusFBW/FMA1g[:24]",
    "1w": "AirbusFBW/FMA1w[:36]",
    "2b": "AirbusFBW/FMA2b[:24]",
    "2m": "AirbusFBW/FMA2m[:24]",
    "2w": "AirbusFBW/FMA2w[:36]",
    "3a": "AirbusFBW/FMA3a[:24]",
    "3b": "AirbusFBW/FMA3b[:24]",
    "3w": "AirbusFBW/FMA3w[:24]",
}


class FCUIcon(DrawBase):
    """Highly customized class to display FCU on Streamdeck Plus touchscreen (whole screen)."""

    def __init__(self, config: dict, button: "Button"):
        DrawBase.__init__(self, config=config, button=button)
        self.fcuconfig = config.get("fcu")
        self._cached = None
        self.icon_color = "black"

    def get_fcu_datarefs(self):
        return FCU_DATAREFS.values()

    def is_updated(self):
        return True

    def get_image_for_icon(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        (This is currently more or less hardcoded for Elgato Streamdeck Plus touchscreen.)
        """
        if not self.is_updated() and self._cached is not None:
            return self._cached

        print(">" * 40)

        image = Image.new(mode="RGBA", size=(8 * ICON_SIZE, ICON_SIZE), color=TRANSPARENT_PNG_COLOR)
        draw = ImageDraw.Draw(image)

        inside = round(0.04 * image.height + 0.5)

        # pylint: disable=W0612
        text, text_format, text_font, text_color, text_size, text_position = self.get_text_detail(self.fcuconfig, "text")

        # static texts (may be unlit)
        font = self.get_font(text_font, text_size)
        h = text_size + inside
        draw.text((inside, h), text="SPD", font=font, anchor="ls", align="left", fill=text_color)
        draw.text((150, h), text="MACH", font=font, anchor="ls", align="left", fill=text_color)

        draw.text((420, h), text="HDG", font=font, anchor="ls", align="left", fill=text_color)
        draw.text((570, h), text="TRK", font=font, anchor="ls", align="left", fill=text_color)
        draw.text((720, h), text="LAT", font=font, anchor="ls", align="left", fill=text_color)

        draw.text((980, 120), text="HDG", font=font, anchor="rs", align="right", fill=text_color)
        draw.text((980, 220), text="TRK", font=font, anchor="rs", align="right", fill=text_color)

        draw.text((1100, 120), text="V/S", font=font, anchor="ls", align="left", fill=text_color)
        draw.text((1100, 220), text="FPA", font=font, anchor="ls", align="left", fill=text_color)

        draw.text((1320, h), text="ALT", font=font, anchor="ls", align="left", fill=text_color)
        draw.text((1600, h), text="LVL/CH", font=font, anchor="ms", align="center", fill=text_color)
        draw.text((1880, h), text="V/S", font=font, anchor="rs", align="right", fill=text_color)
        draw.text((8 * ICON_SIZE - inside, h), text="FPA", font=font, anchor="rs", align="right", fill=text_color)

        # line
        h = inside + text_size / 2 + 4
        draw.line([(1410, h), (1510, h)], fill=text_color, width=3, joint="curve")
        draw.line([(1410, h), (1410, h + text_size / 3)], fill=text_color, width=3, joint="curve")
        draw.line([(1690, h), (1790, h)], fill=text_color, width=3, joint="curve")
        draw.line([(1790, h), (1790, h + text_size / 3)], fill=text_color, width=3, joint="curve")

        # dots (may be lit or not)
        dot_size = 20
        h = 170
        w = 250
        dot = ((w - dot_size, h - dot_size), (w + dot_size, h + dot_size))
        draw.ellipse(dot, fill=text_color)
        w = 730
        dot = ((w - dot_size, h - dot_size), (w + dot_size, h + dot_size))
        draw.ellipse(dot, fill=text_color)
        w = 1610
        dot = ((w - dot_size, h - dot_size), (w + dot_size, h + dot_size))
        draw.ellipse(dot, fill=text_color)

        # values
        speed, heading, alt, vs = "250", "314", "26789", "-1201"
        font = self.get_font("Seven Segment", 120)
        h = 210
        one = " 1"
        segment = True
        if not segment:
            font = self.get_font("B612-Regular", 90)
            h = 200
            one = "1"
        draw.text((20, h), text=speed.replace("1", one), font=font, anchor="ls", align="left", fill=text_color)
        draw.text((500, h), text=heading.replace("1", one), font=font, anchor="ls", align="left", fill=text_color)
        draw.text((1260, h), text=alt.replace("1", one), font=font, anchor="ls", align="left", fill=text_color)  # should always be len=5
        draw.text((1720, h), text=vs.replace("1", one), font=font, anchor="ls", align="left", fill=text_color)  # should always be len=5 or 6
        # if ref in self.boxed:
        #     if "warn" in self.boxed:
        #         color = "orange"
        #     draw.rectangle((loffset + 2 * inside, h - text_size / 2, loffset + icon_width - 2 * inside, h + text_size / 2 + 4), outline=color, width=3)

        # Paste image on cockpit background and return it.
        bg = self.button.deck.get_icon_background(
            name=self.button_name(), width=8 * ICON_SIZE, height=ICON_SIZE, texture_in=None, color_in="black", use_texture=False, who="FCU"
        )
        bg.alpha_composite(image)
        self._cached = bg.convert("RGB")
        return self._cached
