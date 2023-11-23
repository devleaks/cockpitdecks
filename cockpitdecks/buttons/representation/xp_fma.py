# ###########################
# Representation that displays the content of sim/aircraft/view/acf_ICAO on an icon.
# These buttons are *highly* XP and Toliss Airbus specific.
#
import logging

from PIL import Image, ImageDraw

from cockpitdecks.resources.color import TRANSPARENT_PNG_COLOR
from cockpitdecks import ICON_SIZE, now
from cockpitdecks.simulator import Dataref
from .xp_str import StringIcon

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

FMA_COLORS = {"b": "deepskyblue", "w": "white", "g": "lime", "m": "magenta", "a": "orange"}
FMA_INTERNAL_DATAREF = Dataref.mk_internal_dataref("FMA")
FMA_DATAREFS = {
    "1b": "AirbusFBW/FMA1b",
    "1g": "AirbusFBW/FMA1g",
    "1w": "AirbusFBW/FMA1w",
    "2b": "AirbusFBW/FMA2b",
    "2m": "AirbusFBW/FMA2m",
    "2w": "AirbusFBW/FMA2w",
    "3a": "AirbusFBW/FMA3a",
    "3b": "AirbusFBW/FMA3b",
    "3w": "AirbusFBW/FMA3w",
}
FMA_LINES = {  # sample set for debugging
    "0b": "1234567890123456789012345678901234567890",
    "1b": "",
    "1g": "SPEED  ALT    HDG",
    "1w": "                   CAT3 AP1+2",
    "2b": "       G/S    LOC",
    "2m": "            333333",  # wrong for testing
    "2w": "                        1FD2",
    "2a": "                    DUAL",  # does not exist, added for testing purpose
    "3a": "",
    "3b": "                      20",
    "3w": "                  DH    A/THR",
}
FMA_COUNT = 5
MAX_LENGTH = 40


class FMAIcon(StringIcon):
    def __init__(self, config: dict, button: "Button"):
        self.fmaconfig = config.get("fma")
        # get mandatory index
        self.all_in_one = self.fmaconfig.get("all-in-one", False)
        fma = int(self.fmaconfig.get("index"))
        if fma is None:
            logger.warning(f"button {button.name}: no FMA index, forcing index=1")
            fma = 1
        if fma < 1:
            logger.warning(f"button {button.name}: FMA index must be in 1..{FMA_COUNT} range")
            fma = 1
        if fma > FMA_COUNT:
            logger.warning(f"button {button.name}: FMA index must be in 1..{FMA_COUNT} range")
            fma = FMA_COUNT
        self.fma_idx = fma - 1
        self.text_length = 6
        if self.text_length * FMA_COUNT > MAX_LENGTH:
            logger.warning(f"button {button.name}: string too long")
            self.text_length = int(MAX_LENGTH / 5)
        self.boxed = ["11", "22", "33", "41", "42"]  # later
        StringIcon.__init__(self, config=config, button=button)
        self.icon_color = "black"

    def is_master_fma(self) -> bool:
        ret = len(self.button.dataref_collections) > 0
        # logger.debug(f"button {self.button.name}: master {ret}")
        return ret

    def get_master_fma(self):
        if self.is_master_fma():
            return self
        candidates = list(filter(lambda m: isinstance(m._representation, FMAIcon) and m._representation.is_master_fma(), self.button.page.buttons.values()))
        if len(candidates) == 1:
            logger.debug(f"button {self.button.name}: master FMA is {candidates[0].name}, fma={candidates[0]._representation.fma_idx}")
            return candidates[0]._representation
        if len(candidates) == 0:
            logger.warning(f"button {self.button.name}: no master FMA found")
        else:
            logger.warning(f"button {self.button.name}: too many master FMA")
        return None

    def get_fma_lines(self, idx: int = -1):
        self.text = FMA_LINES
        if self.is_master_fma():
            if idx == -1:
                idx = self.fma_idx
            s = idx * self.text_length
            e = s + self.text_length
            c = "1w"
            empty = c + " " * self.text_length
            lines = []
            for li in range(1, 4):
                good = empty
                for k, v in self.text.items():
                    raws = {k: v for k, v in self.text.items() if int(k[0]) == li}
                    for k, v in raws.items():
                        if len(v) < MAX_LENGTH:
                            v = v + " " * (MAX_LENGTH - len(v))
                        if len(v) > MAX_LENGTH:
                            v = v[:MAX_LENGTH]
                        m = v[s:e]
                        # print(self.fma_idx + 1, li, k, v[s:e], s, e, good == empty, (c + m) != empty, ">" + v + "<")
                        if len(m) != self.text_length:
                            logger.warning(f"string '{m}' is shorter/longer than {self.text_length}")
                        if (c + m) != empty:  # if good == empty and
                            good = str(li) + k[1] + m
                            lines.append(good)
            return set(lines)
        master_fma = self.get_master_fma()
        if master_fma is not None:
            return master_fma.get_fma_lines(idx=self.fma_idx)
        logger.warning(f"button {self.button.name}: no lines")
        return []

    def get_image_for_icon_alt(self):
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

        lines = self.get_fma_lines()
        logger.debug(f"button {self.button.name}: {lines}")
        font = self.get_font(text_font, text_size)
        w = image.width / 2
        p = "m"
        a = "center"
        idx = -1
        for text in lines:
            idx = int(text[0]) - 1  # idx + 1
            if text[2:] == (" " * (len(text) - 1)):
                continue
            # if text_position[0] == "l":
            #     w = inside
            #     p = "l"
            #     a = "left"
            # elif text_position[0] == "r":
            #     w = image.width - inside
            #     p = "r"
            #     a = "right"
            h = image.height / 2
            if idx == 0:
                h = inside + text_size
            elif idx == 2:
                h = image.height - inside - text_size
            # logger.debug(f"position {(w, h)}")
            color = FMA_COLORS[text[1]]
            draw.text((w, h), text=text[2:], font=font, anchor=p + "m", align=a, fill=color)
            ref = f"{self.fma_idx+1}{idx+1}"
            if ref in self.boxed:
                draw.rectangle([2 * inside, h - text_size / 2] + [ICON_SIZE - 2 * inside, h + text_size / 2 + 4], outline=color, width=3)

        # Paste image on cockpit background and return it.
        bg = self.button.deck.get_icon_background(
            name=self.button_name(), width=ICON_SIZE, height=ICON_SIZE, texture_in=None, color_in="black", use_texture=False, who="FMA"
        )
        bg.alpha_composite(image)
        self._cached = bg.convert("RGB")
        return self._cached

    def get_image_for_icon(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        if not self.all_in_one:
            return self.get_image_for_icon_alt()

        if not self.is_updated() and self._cached is not None:
            return self._cached

        if not self.is_master_fma():
            logger.debug(f"button {self.button.name}: only draw FMA master")
            return None
        image = Image.new(mode="RGBA", size=(8 * ICON_SIZE, ICON_SIZE), color=TRANSPARENT_PNG_COLOR)
        draw = ImageDraw.Draw(image)

        inside = round(0.04 * image.height + 0.5)

        text, text_format, text_font, text_color, text_size, text_position = self.get_text_detail(self.fmaconfig, "text")
        logger.debug(f"button {self.button.name}: is FMA master")

        loffset = 0
        icon_width = int(8 * ICON_SIZE / 5)
        for i in range(FMA_COUNT):
            lines = self.get_fma_lines(idx=i)
            logger.debug(f"button {self.button.name}: FMA {i}: {lines}")
            font = self.get_font(text_font, text_size)
            w = int(4 * ICON_SIZE / 5)
            p = "m"
            a = "center"
            idx = -1
            for text in lines:
                idx = int(text[0]) - 1  # idx + 1
                if text[2:] == (" " * (len(text) - 1)):
                    continue
                # if text_position[0] == "l":
                #     w = inside
                #     p = "l"
                #     a = "left"
                # elif text_position[0] == "r":
                #     w = image.width - inside
                #     p = "r"
                #     a = "right"
                h = image.height / 2
                if idx == 0:
                    h = inside + text_size / 2
                elif idx == 2:
                    h = image.height - inside - text_size / 2
                color = FMA_COLORS[text[1]]
                # logger.debug(f"added {text[2:]} @ {loffset + w}, {h}, {color}")
                draw.text((loffset + w, h), text=text[2:], font=font, anchor=p + "m", align=a, fill=color)
                ref = f"{self.fma_idx+1}{idx+1}"
                if ref in self.boxed:
                    draw.rectangle(
                        [loffset + 2 * inside, h - text_size / 2] + [loffset + icon_width - 2 * inside, h + text_size / 2 + 4], outline=color, width=3
                    )
            loffset = loffset + icon_width

        # Paste image on cockpit background and return it.
        bg = self.button.deck.get_icon_background(
            name=self.button_name(), width=8 * ICON_SIZE, height=ICON_SIZE, texture_in=None, color_in="black", use_texture=False, who="FMA"
        )
        bg.alpha_composite(image)
        self._cached = bg.convert("RGB")

        # with open("fma_lines.png", "wb") as im:
        #     image.save(im, format="PNG")
        #     logger.debug(f"button {self.button.name}: saved")

        return self._cached
