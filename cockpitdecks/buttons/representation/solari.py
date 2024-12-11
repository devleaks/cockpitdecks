# ###########################
# Buttons that are drawn on render()
#
import logging
from functools import reduce

from cockpitdecks import ICON_SIZE, yaml
from cockpitdecks.constant import CONFIG_KW

from .draw_animation import DrawAnimation

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


#
# ###############################
#
# SOLARIS SPLIT FLAPS DISPLAY
#
CHARACTER_LIST = sorted({i for i in range(ord("0"), ord("9") + 1)} | {i for i in range(ord("A"), ord("Z") + 1)} | {ord(c) for c in " *:/-"})
START_CHAR = chr(CHARACTER_LIST[0])
SIMULTANEOUS = "simultaneous"
AS_ONE = "one"
ADD_DELAY = True


def solari(text, last_text: str | None = None, mode: str = AS_ONE):
    def bad(c: int):
        return (32 < c < 42) or (42 < c < 48) or (57 < c < 65) or (c > 96)

    start_char = START_CHAR * len(text) if (last_text is None or len(text) != len(last_text)) else last_text
    screen = [" " for i in range(len(text))]
    j = 0
    if mode == AS_ONE:
        for c in text:
            start = ord(start_char[j])
            end = ord(c) + 1
            if start < end:
                for i in range(start, end):
                    if bad(i):  # only keep number and letters
                        continue
                    screen[j] = chr(i)
                    # playsound("/Users/pierre/Developer/fs/cockpitdecks/cockpitdecks/resources/sounds/clic.mp3")
                    yield "".join(screen)
                j = j + 1
            else:
                for i in range(start, ord("Z") + 1):
                    if bad(i):  # only keep number and letters
                        continue
                    screen[j] = chr(i)
                    # playsound("/Users/pierre/Developer/fs/cockpitdecks/cockpitdecks/resources/sounds/clic.mp3")
                    yield "".join(screen)
                for i in range(ord(START_CHAR), end):
                    if bad(i):  # only keep number and letters
                        continue
                    screen[j] = chr(i)
                    # playsound("/Users/pierre/Developer/fs/cockpitdecks/cockpitdecks/resources/sounds/clic.mp3")
                    yield "".join(screen)
                j = j + 1
    elif mode == SIMULTANEOUS:
        start = min([ord(c) for c in start_char])
        end = max([ord(c) for c in text]) + 1
        for i in range(start, ord("Z") + 1):
            if bad(i):  # only keep number and letters
                continue
            for j in range(len(text)):
                if screen[j] != text[j]:
                    screen[j] = chr(i)
            # playsound("/Users/pierre/Developer/fs/cockpitdecks/cockpitdecks/resources/sounds/clic.mp3")
            yield "".join(screen)
        for i in range(ord(START_CHAR), end):
            if bad(i):  # only keep number and letters
                continue
            for j in range(len(text)):
                if screen[j] != text[j]:
                    screen[j] = chr(i)
            # playsound("/Users/pierre/Developer/fs/cockpitdecks/cockpitdecks/resources/sounds/clic.mp3")
            yield "".join(screen)


class SolariIcon(DrawAnimation):
    """Display up to 2 lines of 3 characters in a split flap/solari animation"""

    REPRESENTATION_NAME = "solari"

    # Number of characters on display
    # Per "deck"
    NUM_WIDTH = 8
    NUM_HEIGHT = 4
    OFFSET_WIDTH = 0
    OFFSET_HEIGHT = 0
    # Per "cell"
    NUM_LINES = 3
    NUM_CHARS = 5
    LINE_OFFSET = 44
    LINE_OFFSET_X = 10
    LINE_SPACE = 84
    FONT = "Skyfont.otf"
    FONT_SIZE = 100
    SPEED = 0.08
    COLOR = "darkblue"

    PARAMETERS = {
        "text": {"type": "string", "prompt": f"Characters (up to {NUM_LINES * NUM_CHARS})"},
    }

    def __init__(self, button: "Button"):

        DrawAnimation.__init__(self, button=button)

        self.speed = self._representation_config.get("speed", self.SPEED)
        self.display = self._representation_config.get("display", SIMULTANEOUS)  # alt: one, simultaneous
        self.color = self._representation_config.get("text-color", self.COLOR)

        self.bg = self.button.deck.get_icon_background(
            name=self.button_name(),
            width=ICON_SIZE,
            height=ICON_SIZE,
            texture_in=self.icon_color,
            color_in=self.icon_texture,
            use_texture=True,
            who="Solari",
        )
        self.font = self.get_font(self.FONT, self.FONT_SIZE)
        self.base_line = [self.LINE_OFFSET + i * self.LINE_SPACE for i in range(self.NUM_LINES)]

        self._cached = None  # complete unchanged image

        # Text: from last_text to text
        text = self._representation_config.get(CONFIG_KW.TEXT.value, "      ")
        char_count = self.NUM_LINES * self.NUM_CHARS
        if len(text) < char_count:
            text = text + " " * (char_count - len(text))
        self.text = [text[0 + i : self.NUM_CHARS + i] for i in range(0, len(text), self.NUM_CHARS)]
        self.last_text = [START_CHAR * self.NUM_CHARS for i in range(self.NUM_LINES)]
        self.solari = [solari(text=self.text[i], last_text=self.last_text[i], mode=self.display) for i in range(self.NUM_LINES)]
        self.completed = [False for i in range(self.NUM_LINES)]

        # Start delay if display one by one
        self.start_delay = self._representation_config.get("start-delay", [0 for i in range(self.NUM_LINES)])
        if self.display == SIMULTANEOUS:
            self.start_delay = [0 for i in range(self.NUM_LINES)]
        elif len(self.start_delay) != self.NUM_LINES:
            logger.warning("invalid start delay array size, ignored")
            self.start_delay = [0 for i in range(self.NUM_LINES)]

        # logger.debug(f"solari: {self.NUM_WIDTH}×{self.NUM_HEIGHT} × {self.NUM_CHARS}×{self.NUM_LINES} = {self.NUM_WIDTH * self.NUM_CHARS} × {self.NUM_HEIGHT * self.NUM_LINES}")

    def should_run(self):
        return False in self.completed

    def change_text(self, text):
        char_count = self.NUM_LINES * self.NUM_CHARS
        if len(text) < char_count:
            text = text + " " * (char_count - len(text))
        self.text = [text[0 + i : self.NUM_CHARS + i] for i in range(0, len(text), self.NUM_CHARS)]
        self.solari = [solari(text=self.text[i], last_text=self.last_text[i]) for i in range(self.NUM_LINES)]
        self.completed = [False for text in self.text]

    def animate(self):
        image, draw = self.double_icon()
        for i in range(self.NUM_LINES):
            if self.start_delay[i] > 0:
                self.start_delay[i] = self.start_delay[i] - 1
                draw.text(
                    (self.LINE_OFFSET_X, self.base_line[i]),
                    text=" " * len(self.text[i]),
                    font=self.font,
                    anchor="lm",
                    align="center",
                    fill=self.color,
                )
                continue
            try:
                text = next(self.solari[i])
                draw.text(
                    (self.LINE_OFFSET_X, self.base_line[i]),
                    text=text,
                    font=self.font,
                    anchor="lm",
                    align="center",
                    fill=self.color,
                )
            except StopIteration:
                draw.text(
                    (self.LINE_OFFSET_X, self.base_line[i]),
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
        return self._cached if self._cached is not None else self.bg


# def make_solari(text):
#     def ticks(s, e):
#         return abs(CHARACTER_LIST.index(ord(e)) - CHARACTER_LIST.index(ord(s)))
#
#     lines = []
#     for line in text.split("\n"):
#         if len(line) < 24:
#             line = line + " " * (24 - len(line))
#         else:
#             line = line[:24]
#         lines.append(line)
#     start_delays = [[[0, 0]] for i in range(4)]
#     buttons = []
#     for i in range(32):
#         l0 = int(i / 8)
#         l = l0 * 2
#         j0 = i % 8
#         j = j0 * 3
#         s0 = lines[l][j : j + 3]
#         m0 = reduce(lambda a, b: a + b, [ticks(c, START_CHAR) for c in s0])
#         s1 = lines[l + 1][j : j + 3]
#         m1 = reduce(lambda a, b: a + b, [ticks(c, START_CHAR) for c in s1])
#         delay = start_delays[l0][-1] if ADD_DELAY else [0, 0]
#         start_delays[l0].append([delay[0] + m0, delay[1] + m1])
#         buttons.append({"index": i, "solari": {"text": s0 + s1, "start-delay": delay}})
#     buttons[31]["type"] = "reload"
#     with open("solary.yaml", "w") as fp:
#         yaml.dump({"buttons": buttons}, fp)
