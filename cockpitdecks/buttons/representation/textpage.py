# ###########################
# Abstract Base Representation for weather icons.
# The ABC offerts basic update structures, just need
#  - A Weather data feed
#  - get_image_for_icon() to provide an iconic representation of the weather provided as above.
#
from __future__ import annotations
import logging
from functools import reduce
from textwrap import wrap
from math import ceil

from PIL import Image, ImageDraw

from cockpitdecks import ICON_SIZE
from cockpitdecks.buttons.representation.draw import DrawBase
from cockpitdecks.strvar import TextWithVariables

logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)
# logger.setLevel(logging.DEBUG)


class TextPageIcon(DrawBase):
    """Display text in pages, pressing icon flip pages"""

    REPRESENTATION_NAME = "textpage"

    PARAMETERS = {
        "textpages": {"type": "string", "prompt": "Text pages"},
    }

    def __init__(self, button: "Button"):
        DrawBase.__init__(self, button=button)
        self._textpage = TextWithVariables(
            owner=button, config=self._representation_config, prefix="text"
        )  # note: solely used has property older for font, size, and color

        self.text = self._representation_config.get("text")  # self._textpage.get_text()?
        self.width = self._representation_config.get("width", 20)
        self.lines = self._representation_config.get("lines", 7)
        self.pagenum = self._representation_config.get("page-number", True)

    # #############################################
    # Cockpitdecks Representation interface
    #
    def updated(self) -> bool:
        return self.button.has_changed()  # to cycle pages

    def get_lines(self, page: int = 0) -> list | None:
        text = self.text.split(".")
        all_lines = reduce(lambda x, t: x + wrap(t, width=self.width), text, [])
        npages = ceil(len(all_lines) / self.lines)
        l = (page % npages) * self.lines
        if self.pagenum:
            return [f"Page {1 + (page % npages)} / {npages}"] + all_lines[l : l + self.lines]
        else:
            return all_lines[l : l + self.lines]

    def get_image_for_icon(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        if not self.updated() and self._cached is not None:
            return self._cached

        # Generic display text in small font on icon
        image, draw = self.double_icon(width=ICON_SIZE, height=ICON_SIZE)
        inside = round(0.04 * image.width + 0.5)

        page = self.button.value
        page = 0 if page is None else int(float(page))
        lines = self.get_lines(page=page)

        if lines is not None:
            font = self.get_font(self._textpage.font, self._textpage.size)
            w = inside
            p = "l"
            a = "left"
            h = image.height / 3
            il = self._textpage.size
            for line in lines:
                draw.text(
                    (w, h),
                    text=line.strip(),
                    font=font,
                    anchor=p + "m",
                    align=a,
                    fill=self._textpage.color,
                )
                h = h + il
        else:
            logger.warning("no weather information")

        # Paste image on cockpit background and return it.
        bg = self.button.deck.get_icon_background(
            name=self.button_name,
            width=ICON_SIZE,
            height=ICON_SIZE,
            texture_in=self.cockpit_texture,
            color_in=self.cockpit_color,
            use_texture=True,
            who="Weather",
        )
        bg.alpha_composite(image)
        self._cached = bg
        return self._cached
