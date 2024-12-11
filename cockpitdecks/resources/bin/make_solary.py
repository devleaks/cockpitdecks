import ruamel
from ruamel.yaml import YAML

from functools import reduce

ruamel.yaml.representer.RoundTripRepresenter.ignore_aliases = lambda x, y: True

yaml = YAML(typ="safe", pure=True)
yaml.default_flow_style = False

CHARACTER_LIST = sorted({i for i in range(ord("0"), ord("9") + 1)} | {i for i in range(ord("A"), ord("Z") + 1)} | {ord(c) for c in " *:/-"})
START_CHAR = chr(CHARACTER_LIST[0])
SIMULTANEOUS = "simultaneous"
AS_ONE = "one"
ADD_DELAY = True

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


def make_solari(text):
    def ticks(s, e):
        return abs(CHARACTER_LIST.index(ord(e)) - CHARACTER_LIST.index(ord(s)))

    lines = []
    line_length = NUM_CHARS * NUM_WIDTH
    for line in text.split("\n"):
        if len(line) < line_length:
            line = line + " " * (line_length - len(line))
        else:
            line = line[:line_length]
        lines.append(line)
    num_lines = NUM_HEIGHT * NUM_LINES
    if len(lines) < num_lines:
        while len(lines) < num_lines:
            lines.append(" "*(NUM_WIDTH*NUM_CHARS))
    start_delays = [[[0 for j in range(NUM_LINES)]] for i in range(NUM_HEIGHT)]
    buttons = []
    num_cells = NUM_WIDTH * NUM_HEIGHT
    for i in range(num_cells):
        l0 = int(i / NUM_WIDTH)
        l = l0 * NUM_LINES
        j0 = i % NUM_WIDTH
        j = j0 * NUM_CHARS

        delay = start_delays[l0][-1] if ADD_DELAY else [0 for i in range(NUM_LINES)]
        new_delay = []
        total_s = ""
        for k in range(NUM_LINES):
            s = lines[l+k][j : j + NUM_CHARS]
            total_s = total_s + s
            m = reduce(lambda a, b: a + b, [ticks(c, START_CHAR) for c in s])
            new_delay.append(m + delay[k])
        start_delays[l0].append(new_delay)
        buttons.append({"index": i, "solari": {"text": total_s, "start-delay": new_delay}})
    buttons[-1]["type"] = "reload"
    with open("solary.yaml", "w") as fp:
        yaml.dump({"buttons": buttons}, fp)


# 3ABC123ABC123ABC123ABC
# -----123ABC123ABC123ABC123ABC
make_solari(
    """TEST                 ***
MINI*COCKPIT ROCKS
BRUSSELS     1450 ON TIM
TOULOUSE     1510 DELAYE
HAMBURG      1520 DELAYE
ZURICH       1540 ON TIM
DOHA         1600 ON TIM
MUNICH       1610 DELAYE"""
)
