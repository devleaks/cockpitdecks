import socket
import threading
import logging
import time
import json

from typing import Dict, List, Set
from datetime import datetime

from cockpitdecks.buttons.representation.draw import DrawBase
from cockpitdecks import ICON_SIZE

# ##############################
# Toliss Airbus FMA display
FMA_DATAREFS = {
    "1w": "AirbusFBW/FMA1w",
    "1g": "AirbusFBW/FMA1g",
    "1b": "AirbusFBW/FMA1b",
    "2w": "AirbusFBW/FMA2w",
    "2b": "AirbusFBW/FMA2b",
    "2m": "AirbusFBW/FMA2m",
    "3w": "AirbusFBW/FMA3w",
    "3b": "AirbusFBW/FMA3b",
    "3a": "AirbusFBW/FMA3a",
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
FMA_COLORS = {
    "b": "#0080FF",
    "w": "white",
    "g": "#00FF00",
    "m": "#FF00FF",
    "a": "#A04000",
}

FMA_LABELS = {
    "ATHR": "Auto Thrust",
    "VNAV": "Vertical Navigation",
    "LNAV": "Horizontal Navigation",
    "APPR": "Approach",
    "AP": "Auto Pilot",
}
FMA_LABELS_ALT = {
    "ATHR": "Autothrust Mode",
    "VNAV": "Vertical Mode",
    "LNAV": "Horizontal Mode",
    "APPR": "Approach",
    "AP": "Autopilot Mode",
}

FMA_LABEL_MODE = 3  # 0 (None), 1 (keys), or 2 (values), or 3 alternates

FMA_COUNT = len(FMA_LABELS.keys())
FMA_LINES = len(set([c[0] for c in FMA_DATAREFS]))
FMA_COLUMNS = [[0, 7], [7, 15], [15, 21], [21, 28], [28, 37]]
FMA_LINE_LENGTH = FMA_COLUMNS[-1][-1]
FMA_EMPTY_LINE = " " * FMA_LINE_LENGTH
COMBINED = "combined"
WARNING = "warn"

logger = logging.getLogger(__file__)
logger.setLevel(logging.DEBUG)
# logger.setLevel(15)


class FMAIcon(DrawBase):
    """Displays Toliss Airbus Flight Mode Annunciators on Streamdeck Plus touchscreen
    """

    REPRESENTATION_NAME = "fma"

    def __init__(self, config: dict, button: "Button"):
        DrawBase.__init__(self, config=config, button=button)

        self.fmaconfig = config.get("fma", {})  # should not be none, empty at most...
        self.all_in_one = False
        self.fma_label_mode = self.fmaconfig.get("label-mode", FMA_LABEL_MODE)
        self.icon_color = "black"
        self.text = {k: FMA_EMPTY_LINE for k in FMA_DATAREFS}
        self.fma_text: Dict[str, str] = {}
        self.previous_text: Dict[str, str] = {}
        self.boxed: Set[str] = []
        self._cached = None  # cached icon

        # get mandatory index
        self.all_in_one = False
        fma = self.fmaconfig.get("index")
        if fma is None:
            logger.info(f"button {button.name}: no FMA index, assuming all-in-one")
            self.all_in_one = True
            fma = 1
        fma = int(fma)
        if fma < 1:
            logger.info(f"button {button.name}: FMA index must be in 1..{FMA_COUNT} range")
            fma = 1
        if fma > FMA_COUNT:
            logger.info(f"button {button.name}: FMA index must be in 1..{FMA_COUNT} range")
            fma = FMA_COUNT
        self.fma_idx = fma - 1

    @property
    def combined(self) -> bool:
        """FMA vertical and lateral combined into one"""
        return COMBINED in self.boxed

    def describe(self) -> str:
        return "The representation is specific to Toliss Airbus and display the Flight Mode Annunciators (FMA)."

    def is_master_fma(self) -> bool:
        return self.all_in_one or self.fma_idx == 1

    def get_master_fma(self):
        """Among all FMA icon buttons on the same page, tries to find the master one,
        i;e. the one that holds the datarefs.
        """
        if self.is_master_fma():
            return self
        candidates = list(
            filter(
                lambda m: isinstance(m._representation, FMAIcon) and m._representation.is_master_fma(),
                self.button.page.buttons.values(),
            )
        )
        if len(candidates) == 1:
            logger.debug(f"button {self.button.name}: master FMA is {candidates[0].name}, fma={candidates[0]._representation.fma_idx}")
            return candidates[0]._representation
        if len(candidates) == 0:
            logger.warning(f"button {self.button.name}: no master FMA found")
        else:
            logger.warning(f"button {self.button.name}: too many master FMA")
        return None

    def is_updated(self) -> bool:
        oldboxed = self.boxed
        self.check_boxed()
        if self.boxed != oldboxed:
            logger.debug(f"boxed changed {self.boxed}/{oldboxed}")
            return True
        self.previous_text = self.text
        self.text = {k: self.button.get_dataref_value(v, default=FMA_EMPTY_LINE) for k, v in FMA_DATAREFS.items()}
        return self.text != self.previous_text

    def check_boxed(self):
        """Check "boxed" datarefs to determine which texts are boxed/framed.
        They are listed as FMA#-LINE# pairs of digit. Special keyword WARNING if warning enabled.
        """
        boxed = []
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
            boxed.append(WARNING)
        # big mess:
        boxcode = self.button.get_dataref_value("AirbusFBW/FMAAPFDboxing")
        if boxcode is not None:  # can be 0-7, is it a set of binary flags?
            boxcode = int(boxcode)
            if boxcode & 1 == 1:
                boxed.append("51")
            if boxcode & 2 == 2:
                boxed.append("52")
            if boxcode & 4 == 4:
                boxed.append("53")
            if boxcode & 8 == 8:
                boxed.append(COMBINED)
            # etc.
        self.boxed = set(boxed)
        logger.debug(f"boxed: {boxcode}, {self.boxed}")

    def get_fma_lines(self, idx: int = -1):
        if self.is_master_fma():
            if idx == -1:
                idx = self.fma_idx
            s = FMA_COLUMNS[idx][0]  # idx * self.text_length
            e = FMA_COLUMNS[idx][1]  # s + self.text_length
            l = e - s
            c = "1w"
            empty = c + " " * l
            if self.combined and idx == 1:
                s = FMA_COLUMNS[idx][0]
                e = FMA_COLUMNS[idx+1][1]
                l = e - s
                c = "1w"
                empty = c + " " * l
            elif self.combined and idx == 2:
                return set()
            lines = []
            for li in range(1, 4): # Loop on lines
                good = empty
                for k, v in self.text.items():
                    raws = {k: v for k, v in self.text.items() if int(k[0]) == li}
                    for k, v in raws.items():
                        # normalize
                        if len(v) < FMA_LINE_LENGTH:
                            v = v + " " * (FMA_LINE_LENGTH - len(v))
                        if len(v) > FMA_LINE_LENGTH:
                            v = v[:FMA_LINE_LENGTH]
                        # extract
                        m = v[s:e]
                        if len(m) != l:
                            logger.warning(f"string '{m}' len {len(m)} has wrong size (should be {l})")
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

        # pylint: disable=W0612
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
                draw.rectangle(
                    (
                        2 * inside,
                        h - text_size / 2,
                        ICON_SIZE - 2 * inside,
                        h + text_size / 2 + 4,
                    ),
                    outline="white",
                    width=3,
                )

        # Paste image on cockpit background and return it.
        bg = self.button.deck.get_icon_background(
            name=self.button_name(),
            width=ICON_SIZE,
            height=ICON_SIZE,
            texture_in=None,
            color_in="black",
            use_texture=False,
            who="FMA",
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
            logger.debug(f"button {self.button.name}: returning cached")
            return self._cached

        # print(">>>" + "0" * 10 + "1" * 10 + "2" * 10 + "3" * 10)
        # print(">>>" + "0123456789" * 4)
        # print("\n".join([f"{k}:{v}:{len(v)}" for k, v in self.text.items()]))
        # print(">>>" + "0123456789" * 4)

        image, draw = self.double_icon(width=8 * ICON_SIZE, height=ICON_SIZE)

        inside = round(0.04 * image.height + 0.5)

        # pylint: disable=W0612
        text, text_format, text_font, text_color, text_size, text_position = self.get_text_detail(self.fmaconfig, "text")
        logger.debug(f"button {self.button.name}: is FMA master")

        # replaces a few bizarre strings...
        if text is not None:
            text = text.replace("THRIDLE", "THR IDLE")  # ?
            text = text.replace("FNL", "FINAL")  # ?

        icon_width = int(8 * ICON_SIZE / 5)
        loffset = 0
        lthinkness = 3
        has_line = False
        for i in range(FMA_COUNT - 1):
            loffset = loffset + icon_width
            if i == 1:  # second line skipped
                continue
            draw.line(((loffset, 0), (loffset, ICON_SIZE)), fill="white", width=lthinkness)
        if self.fma_label_mode > 0:
            ls = 20
            font = self.get_font(text_font, ls)
            offs = icon_width / 2
            h = inside + ls / 2
            lbl = list(FMA_LABELS.keys())
            if self.fma_label_mode == 2:
                lbl = list(FMA_LABELS.values())
            if self.fma_label_mode == 3:
                lbl = list(FMA_LABELS_ALT.values())
            for i in range(FMA_COUNT):
                draw.text(
                    (offs, h),
                    text=lbl[i],
                    font=font,
                    anchor="ms",
                    align="center",
                    fill="white",
                )
                offs = offs + icon_width

        if not self.button.sim.connected:
            logger.debug("not connected")
            if not self.combined:
                draw.line(
                    ((2 * icon_width, 0), (2 * icon_width, int(2 * ICON_SIZE / 3))),
                    fill="white",
                    width=lthinkness,
                )
            bg = self.button.deck.get_icon_background(
                name=self.button_name(),
                width=8 * ICON_SIZE,
                height=ICON_SIZE,
                texture_in=None,
                color_in="black",
                use_texture=False,
                who="FMA",
            )
            bg.alpha_composite(image)
            self._cached = bg.convert("RGB")
            self.previous_text = self.text
            logger.debug("texts updated")
            return self._cached

        loffset = 0
        for i in range(FMA_COUNT):
            if i == 2 and self.combined:  # skip it
                loffset = loffset + icon_width
                continue
            lines = self.get_fma_lines(idx=i)
            logger.debug(f"button {self.button.name}: FMA {i+1}: {lines}")
            logger.debug(f"{i}: {self.combined}")
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
                    currline = text[:2]
                    if (i == 1 or i == 2) and currline in ["3a", "3w"]:
                        wmsg = self.text[currline][FMA_COLUMNS[1][0] : FMA_COLUMNS[2][1]].strip()
                        logger.debug(f"warning message '{wmsg}'")
                        draw.line(
                            (
                                (2 * icon_width, 0),
                                (2 * icon_width, int(2 * ICON_SIZE / 3)),
                            ),
                            fill="white",
                            width=lthinkness,
                        )
                        draw.text(
                            (2 * icon_width, h),
                            text=wmsg,
                            font=font,
                            anchor=p + "m",
                            align=a,
                            fill=FMA_COLORS[text[1]],
                        )
                        has_line = True
                        continue
                    #
                    #
                color = FMA_COLORS[text[1]]
                # logger.debug(f"added {text[2:]} @ {loffset + w}, {h}, {color}")
                lat = loffset + w
                if i == 1 and self.combined:
                    lat = lat + w
                draw.text(
                    (lat, h),
                    text=text[2:],
                    font=font,
                    anchor=p + "m",
                    align=a,
                    fill=color,
                )
                ref = f"{i+1}{idx+1}"
                # logger.debug(ref, text)
                if ref in self.boxed:
                    if WARNING in self.boxed:
                        color = "orange"
                    else:
                        color = "white"
                    draw.rectangle(
                        (
                            loffset + 2 * inside,
                            h - text_size / 2,
                            loffset + icon_width - 2 * inside,
                            h + text_size / 2 + 4,
                        ),
                        outline=color,
                        width=3,
                    )
            loffset = loffset + icon_width

        if not has_line and not self.combined:
            draw.line(
                ((2 * icon_width, 0), (2 * icon_width, ICON_SIZE)),
                fill="white",
                width=lthinkness,
            )

        # Paste image on cockpit background and return it.
        bg = self.button.deck.get_icon_background(
            name=self.button_name(),
            width=8 * ICON_SIZE,
            height=ICON_SIZE,
            texture_in=None,
            color_in="black",
            use_texture=False,
            who="FMA",
        )
        bg.alpha_composite(image)
        self._cached = bg.convert("RGB")
        self.previous_text = self.text
        logger.debug("texts updated")

        # with open("fma_lines.png", "wb") as im:
        #     image.save(im, format="PNG")
        #     logger.debug(f"button {self.button.name}: saved")

        return self._cached
