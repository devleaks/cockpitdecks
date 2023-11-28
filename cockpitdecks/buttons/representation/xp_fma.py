# ###########################
# Representation that displays the content of sim/aircraft/view/acf_ICAO on an icon.
# These buttons are *highly* X-Plane and Toliss Airbus specific.
#
import logging

from PIL import Image, ImageDraw

from cockpitdecks import ICON_SIZE
from cockpitdecks.resources.color import TRANSPARENT_PNG_COLOR
from .xp_str import StringIcon

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

FMA_DATAREFS = {
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
FMA_BOXES = [
    "AirbusFBW/FMAAPFDboxing",
    "AirbusFBW/FMAAPLeftArmedBox",
    "AirbusFBW/FMAAPLeftModeBox",
    "AirbusFBW/FMAAPRightArmedBox",
    "AirbusFBW/FMAAPRightModeBox",
    "AirbusFBW/FMAATHRModeBox",
    "AirbusFBW/FMAATHRboxing",
    "AirbusFBW/FMATHRWarning",
]
# Reproduction on Streamdeck touchscreen colors is difficult.
FMA_COLORS = {"b": "#0080FF", "w": "white", "g": "#00FF00", "m": "#FF00FF", "a": "#A04000"}
FMA_COUNT = 5
FMA_LINE_LENGTH = 36
FMA_COLUMNS = [[0, 7], [7, 14], [14, 21], [21, 28], [28, 36]]
# FMA_INTERNAL_DATAREF = Dataref.mk_internal_dataref("FMA")

# sample set for debugging
FMA_LINES = {
    "0b": "1234567890123456789012345678901234567890",
    "1b": "",
    "1g": "         SRS    RWY",
    "1w": "  MAN",
    "2b": "     53SEL:210  NAV",
    "1m": "                              AP1",  # wrong, does not exist, added for testing purpose
    "2w": " FLX                          1FD2",
    "2a": "",  # does not exist, added for testing purpose
    "3a": "        MASTER AMBER",
    "3b": "                              A/THR",
    "3w": "",
}
FMA_BOXES = ["11", "22", "33", "41", "42"]


class FMAIcon(StringIcon):
    """Highly customized class to display FMA on button keys
    or on Streamdeck Plus touchscreen (whole screen).
    """

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
        StringIcon.__init__(self, config=config, button=button)
        self.icon_color = "black"

        self.text = FMA_LINES  # {k: " " * FMA_LINE_LENGTH for k in FMA_DATAREFS.keys()}  # use FMA_LINES for testing
        self.boxed = []

    def is_master_fma(self) -> bool:
        """Determine if thsi FMA icon is the master or not,
        i;e. if it holds the datarefs.
        """
        ret = len(self.button.dataref_collections) > 0
        # logger.debug(f"button {self.button.name}: master {ret}")
        return ret

    def get_fma_dataref_collections(self):
        collections = []
        # add box datarefs
        collections.append({"name": "fma_boxes", "datarefs": FMA_BOXES, "expire": 10, "set-dataref": "data:_fmap"})
        # add lines
        for line, dref in FMA_DATAREFS.items():
            collections.append({"name": "line", "datarefs": self.button.parse_dataref_array(dref), "expire": 10, "set-dataref": "data:_fmap"})
        return collections

    def get_master_fma(self):
        """Among all FMA icon buttons on the same page, tries to find the master one,
        i;e. the one that holds the datarefs.
        """
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

    def check_boxed(self):
        """Check "boxed" datarefs to determine which texts are boxed/framed.
        They are listed as FMA#-LINE# pairs of digit. Special keyword "warn" if warning enabled.
        """
        logger.debug(",".join([f"{d}={self.button.get_dataref_value(d)}" for d in FMA_BOXES]))
        boxed = FMA_BOXES
        if self.button.get_dataref_value("AirbusFBW/FMAAPLeftArmedBox") == 1:
            boxed.append("22")
        if self.button.get_dataref_value("AirbusFBW/FMAAPLeftModeBox") == 1:
            boxed.append("21")
        if self.button.get_dataref_value("AirbusFBW/FMAAPRightArmedBox") == 1:
            boxed.append("32")
        if self.button.get_dataref_value("AirbusFBW/FMAAPRightModeBox") == 1:
            boxed.append("31")
        if self.button.get_dataref_value("AirbusFBW/FMAATHRModeBox") == 1:
            boxed.append("11")
        if self.button.get_dataref_value("AirbusFBW/FMAATHRboxing") == 1:
            boxed.append("12")
        if self.button.get_dataref_value("AirbusFBW/FMAATHRboxing") == 2:
            boxed.append("11")
            boxed.append("12")
        if self.button.get_dataref_value("AirbusFBW/FMATHRWarning") == 1:
            boxed.append("warn")
        # big mess:
        boxcode = self.button.get_dataref_value("AirbusFBW/FMAAPFDboxing")
        if boxcode is not None:  # can be 0-7, is it a set of binary flags?
            if boxcode == 1:  # boxcode & 1
                boxed.append("51")
            if boxcode == 2:  # boxcode & 2
                boxed.append("52")
            if boxcode == 3:
                boxed.append("51")
                boxed.append("52")
            # etc.
        logger.debug(f"{boxed}")
        self.boxed = set(boxed)

    def get_fma_lines(self, idx: int = -1):
        if self.is_master_fma():
            if idx == -1:
                idx = self.fma_idx
            s = FMA_COLUMNS[idx][0]  # idx * self.text_length
            e = FMA_COLUMNS[idx][1]  # s + self.text_length
            c = "1w"
            empty = c + " " * (e - s)
            self.check_boxed()
            lines = []
            for li in range(1, 4):
                good = empty
                for k, v in self.text.items():
                    raws = {k: v for k, v in self.text.items() if int(k[0]) == li}
                    for k, v in raws.items():
                        if len(v) < FMA_LINE_LENGTH:
                            v = v + " " * (FMA_LINE_LENGTH - len(v))
                        if len(v) > FMA_LINE_LENGTH:
                            v = v[:FMA_LINE_LENGTH]
                        m = v[s:e]
                        if len(m) != (e - s):
                            logger.warning(f"string '{m}' len {len(m)} has wrong size (should be {(e - s)})")
                        if (c + m) != empty:  # if good == empty and
                            good = str(li) + k[1] + m
                            lines.append(good)
            return set(lines)
        master_fma = self.get_master_fma()
        if master_fma is not None:
            return master_fma.get_fma_lines(idx=self.fma_idx)
        logger.warning(f"button {self.button.name}: fma has no master, no lines")
        return []

    def get_image_for_icon_alt(self):
        """
        Displays one FMA on one key icon, 5 keys are required for 5 FMA... (or one touchscreen, see below.)
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
                draw.rectangle((2 * inside, h - text_size / 2, ICON_SIZE - 2 * inside, h + text_size / 2 + 4), outline=color, width=3)

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
        (This is currently more or less hardcoded for Elgato Streamdeck Plus touchscreen.)
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

        # pylint: disable=W0612
        text, text_format, text_font, text_color, text_size, text_position = self.get_text_detail(self.fmaconfig, "text")
        logger.debug(f"button {self.button.name}: is FMA master")

        icon_width = int(8 * ICON_SIZE / 5)
        loffset = 0
        has_line = False
        for i in range(FMA_COUNT - 1):
            loffset = loffset + icon_width
            if i == 1:
                continue
            draw.line(((loffset, 0), (loffset, ICON_SIZE)), fill="white", width=1)
        loffset = 0
        for i in range(FMA_COUNT):
            lines = self.get_fma_lines(idx=i)
            logger.debug(f"button {self.button.name}: FMA {i+1}: {lines}")
            font = self.get_font(text_font, text_size)
            w = int(4 * ICON_SIZE / 5)
            p = "m"
            a = "center"
            idx = -1
            for text in lines:
                idx = int(text[0]) - 1  # idx + 1
                if text[2:] == (" " * (len(text) - 2)):
                    continue
                h = image.height / 2
                if idx == 0:
                    h = inside + text_size / 2
                elif idx == 2:
                    h = image.height - inside - text_size / 2
                    #
                    # special treatment of warning amber messages, centered across FMA 2-3, 3rd line, amber
                    # (yes, I know, they blink 5 times then stay fixed. may be one day.)
                    #
                    if text[:2] == "3a":
                        wmsg = self.text["3a"].strip()
                        logger.debug(f"warning message '{wmsg}'")
                        draw.line(((2 * icon_width, 0), (2 * icon_width, int(2 * ICON_SIZE / 3))), fill="white", width=1)
                        draw.text((2 * icon_width, h), text=wmsg, font=font, anchor=p + "m", align=a, fill=FMA_COLORS["a"])
                        has_line = True
                        continue
                    #
                    #
                color = FMA_COLORS[text[1]]
                # logger.debug(f"added {text[2:]} @ {loffset + w}, {h}, {color}")
                draw.text((loffset + w, h), text=text[2:], font=font, anchor=p + "m", align=a, fill=color)
                ref = f"{i+1}{idx+1}"
                # logger.debug(ref, text)
                if ref in self.boxed:
                    if "warn" in self.boxed:
                        color = "orange"
                    draw.rectangle((loffset + 2 * inside, h - text_size / 2, loffset + icon_width - 2 * inside, h + text_size / 2 + 4), outline=color, width=3)
            loffset = loffset + icon_width

        if not has_line:
            draw.line(((2 * icon_width, 0), (2 * icon_width, ICON_SIZE)), fill="white", width=1)

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
