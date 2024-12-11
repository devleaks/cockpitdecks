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

def make_solari(text):
    def ticks(s, e):
        return abs(CHARACTER_LIST.index(ord(e)) - CHARACTER_LIST.index(ord(s)))

    lines = []
    for line in text.split("\n"):
        if len(line) < 24:
            line = line + " " * (24 - len(line))
        else:
            line = line[:24]
        lines.append(line)
    start_delays = [[[0, 0]] for i in range(4)]
    buttons = []
    for i in range(32):
        l0 = int(i / 8)
        l = l0 * 2
        j0 = i % 8
        j = j0 * 3
        s0 = lines[l][j : j + 3]
        m0 = reduce(lambda a, b: a + b, [ticks(c, START_CHAR) for c in s0])
        s1 = lines[l + 1][j : j + 3]
        m1 = reduce(lambda a, b: a + b, [ticks(c, START_CHAR) for c in s1])
        delay = start_delays[l0][-1] if ADD_DELAY else [0, 0]
        start_delays[l0].append([delay[0] + m0, delay[1] + m1])
        buttons.append({"index": i, "solari": {"text": s0 + s1, "start-delay": delay}})
    buttons[31]["type"] = "reload"
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
