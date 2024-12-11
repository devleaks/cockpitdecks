# ###########################
# Buttons that are drawn on render()
#
import logging
import time

from PIL import Image, ImageDraw

from cockpitdecks import ICON_SIZE
from cockpitdecks.constant import CONFIG_KW

from .draw_animation import DrawAnimation

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


#
# ###############################
# DRAWN REPRESENTATION (using Pillow, continued)
#
#
#
# ###############################
# DRAWN REPRESENTATION (using Pillow, continued)
#
#
CHARACTER_LIST = sorted([i for i in range(ord("0"), ord("9")+1)] + [i for i in range(ord("A"), ord("Z")+1)] +[ord(c) for c in ":/-"])

print(CHARACTER_LIST)
def solari(text, last_text: str = None, mode: str = "one"):
    start_char = "0" * len(text) if (last_text is None or len(text) != len(last_text)) else last_text
    screen = [" " for i in range(len(text))]
    j = 0
    if mode == "one":
        for c in text:
            start = ord(start_char[j])
            end = ord(c) + 1
            if start < end:
                for i in range(start, end):
                    if (i > 57 and i < 65) or (i > 96):  # only keep number and letters
                        continue
                    screen[j] = chr(i)
                    # playsound("/Users/pierre/Developer/fs/cockpitdecks/cockpitdecks/resources/sounds/clic.mp3")
                    yield "".join(screen)
                j = j + 1
            else:
                for i in range(start, ord("Z")+1):
                    if (i > 57 and i < 65) or (i > 96):  # only keep number and letters
                        continue
                    screen[j] = chr(i)
                    # playsound("/Users/pierre/Developer/fs/cockpitdecks/cockpitdecks/resources/sounds/clic.mp3")
                    yield "".join(screen)
                for i in range(ord("0"), end):
                    if (i > 57 and i < 65) or (i > 96):  # only keep number and letters
                        continue
                    screen[j] = chr(i)
                    # playsound("/Users/pierre/Developer/fs/cockpitdecks/cockpitdecks/resources/sounds/clic.mp3")
                    yield "".join(screen)
                j = j + 1
    elif mode == "simultaneous":
        start = min([ord(c) for c in last_text])
        end = max([ord(c) for c in text]) + 1
        if start > end:
            start = ord("0")
        for i in range(start, end):
            if (i > 57 and i < 65) or (i > 96):  # only keep number and letters
                continue
            for j in range(len(text)):
                if i <= ord(text[j]):
                    screen[j] = chr(i)
                else:
                    screen[j] = text[j]
            # playsound("/Users/pierre/Developer/fs/cockpitdecks/cockpitdecks/resources/sounds/clic.mp3")
            yield "".join(screen)


class SolariIcon(DrawAnimation):
    """Display up to 2 lines of 3 characters in a split flap/solari animation
    """

    REPRESENTATION_NAME = "solari"

    PARAMETERS = {
        "text": {"type": "string", "prompt": "Characters (up to 6)"},
    }

    def __init__(self, button: "Button"):
        DrawAnimation.__init__(self, button=button)
        self.speed = self._representation_config.get("speed", 0.08)
        self.display = self._representation_config.get("display", "one") # alt: line, lineend
        self.color = self._representation_config.get("text-color", "black")

        self.bg = self.button.deck.get_icon_background(
            name=self.button_name(),
            width=ICON_SIZE,
            height=ICON_SIZE,
            texture_in=self.icon_color,
            color_in=self.icon_texture,
            use_texture=True,
            who="Solari",
        )
        self.font = self.get_font("Skyfont.otf", 160)
        self._cached = None # complete unchanged image

        self.base_line = [70, 190]

        text = self._representation_config.get(CONFIG_KW.TEXT.value, "      ")
        if len(text) < 6:
            text = text + " "*(6 - len(text))
        self.text = [text[:3], text[3:]]
        self.last_text = ["000" for i in range(len(self.text))]
        self.solari = [solari(text=self.text[i], last_text=self.last_text[i], mode="simultaneous") for i in range(len(self.text))]
        self.completed = [False for text in self.text]

        self.start_delay = self._representation_config.get("start-delay", [0 for i in range(len(self.text))])
        if len(self.start_delay) != len(self.text):
            logger.warning("invalid start delay array size, ignored")
            self.start_delay = [0 for i in range(len(self.text))]

    def should_run(self):
        return False in self.completed

    def restart(self):
        self.solari = [solari(text=self.text[i], last_text=self.last_text[i]) for i in range(len(self.text))]
        self.completed = [False for text in self.text]

    def animate(self):
        if not False in self.completed:
            return self._cached

        image, draw = self.double_icon()
        for i in range(len(self.text)):
            if self.start_delay[i] > 0:
                self.start_delay[i] = self.start_delay[i] - 1
                draw.text(
                    (6, self.base_line[i]),
                    text=" "*len(self.text[i]),
                    font=self.font,
                    anchor="lm",
                    align="center",
                    fill=self.color,
                )
                continue
            try:
                text = next(self.solari[i])
                draw.text(
                    (6, self.base_line[i]),
                    text=text,
                    font=self.font,
                    anchor="lm",
                    align="center",
                    fill=self.color,
                )
            except StopIteration:
                draw.text(
                    (6, self.base_line[i]),
                    text=self.text[i],
                    font=self.font,
                    anchor="lm",
                    align="center",
                    fill=self.color,
                )
                self.last_text[i] = self.text[i]
                self.completed[i] = True
        self._cached = self.bg.copy()
        self._cached.alpha_composite(image)

    def get_image_for_icon(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        return self._cached

