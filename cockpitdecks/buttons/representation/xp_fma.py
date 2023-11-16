# ###########################
# Representation that displays the content of sim/aircraft/view/acf_ICAO on an icon.
# These buttons are highly XP specific.
#
import logging
from re import template

from cockpitdecks import ICON_SIZE, now
from .draw import DrawBase

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

FMA_COLORS = {"b": "deepskyblue", "w": "white", "g": "lime", "m": "magenta", "a": "orange"}


class FMAIcon(DrawBase):
    def __init__(self, config: dict, button: "Button"):
        self.raw = {}
        DrawBase.__init__(self, config=config, button=button)
        self.fmaconfig = config.get("fma")
        fma = int(self.fmaconfig.get("index", 1))
        if fma < 1:
            fma = 1
        if fma > 5:
            fma = 5
        self.fma = fma - 1
        self.text_length = 6
        self.boxed = []  # ["11", "22", "33", "41", "42"]
        self._cached = None

        # AirbusFBW/FMA1b
        # AirbusFBW/FMA1g
        # AirbusFBW/FMA1w
        # AirbusFBW/FMA2b
        # AirbusFBW/FMA2m
        # AirbusFBW/FMA2w
        # AirbusFBW/FMA3a
        # AirbusFBW/FMA3b
        # AirbusFBW/FMA3w

    def init(self):
        xxxxxxx = "111111222222333333444444555555"
        self.raw = {
            "1b": " ",
            "1g": "SPEED  ALT    HDG",
            "1w": "                   CAT3 AP1+2",
            "2b": "       G/S    LOC",
            "2m": "            333333",
            "2w": "                    DUAL1FD2",
            "3a": " ",
            "3b": " ",
            "3w": "                   DH 20A/THR",
        }
        xxxxxxx = "111111222222333333444444555555"
        # self.boxed = ["11", "22", "33", "41", "42"]
        self.icon_color = "black"
        logger.debug(f"inited")

    def parse(self):
        s = self.fma * self.text_length
        e = s + self.text_length
        c = "w"
        empty = c + " " * self.text_length
        lines = []
        for li in range(1, 4):
            good = empty
            for k, v in self.raw.items():
                raws = {k: v for k, v in self.raw.items() if int(k[0]) == li}
                for k, v in raws.items():
                    if len(v) < 40:
                        v = v + " " * (40 - len(v))
                    m = v[s:e]
                    # print(self.fma + 1, li, k, v[s:e], s, e, good == empty, (c + m) != empty, ">" + v + "<")
                    if len(m) != self.text_length:
                        logger.warning(f"string '{m}' is shorter/longer than {self.text_length}")
                    if good == empty and (c + m) != empty:
                        good = k[1] + m
            lines.append(good)
        return lines

    def is_updated(self):
        return False

    def get_image_for_icon(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        if not self.is_updated() and self._cached is not None:
            return self._cached

        image, draw = self.double_icon(width=ICON_SIZE, height=ICON_SIZE)  # annunciator text and leds , color=(0, 0, 0, 0)
        inside = round(0.04 * image.width + 0.5)

        text, text_format, text_font, text_color, text_size, text_position = self.get_text_detail(self.fmaconfig, "text")

        lines = self.parse()
        font = self.get_font(text_font, text_size)
        w = image.width / 2
        p = "m"
        a = "center"
        idx = -1
        for text in lines:
            idx = idx + 1
            if text[1:] == (" " * (len(text) - 1)):
                continue
            if text_position[0] == "l":
                w = inside
                p = "l"
                a = "left"
            elif text_position[0] == "r":
                w = image.width - inside
                p = "r"
                a = "right"
            h = image.height / 2
            if idx == 0:
                h = inside + text_size
            elif idx == 2:
                h = image.height - inside - text_size
            # logger.debug(f"position {(w, h)}")
            draw.text((w, h), text=text[1:], font=font, anchor=p + "m", align=a, fill=FMA_COLORS[text[0]])  # (image.width / 2, 15)
            ref = f"{self.fma+1}{idx+1}"
            if ref in self.boxed:
                draw.rectangle([2 * inside, h - text_size / 2] + [ICON_SIZE - 2 * inside, h + text_size / 2], outline=FMA_COLORS[text[0]], width=2)

        # Paste image on cockpit background and return it.
        bg = self.button.deck.get_icon_background(
            name=self.button_name(), width=ICON_SIZE, height=ICON_SIZE, texture_in=None, color_in="black", use_texture=False, who="FMA"
        )
        bg.alpha_composite(image)
        self._cached = bg.convert("RGB")
        return self._cached
