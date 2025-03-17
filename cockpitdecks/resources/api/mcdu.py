import logging
import json
import curses

from cockpitdecks.resources.api.api import NAME

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# logger.setLevel(logging.INFO)


MCDU_COLORS = {
    "a": "\033[38;5;208m",  # amber, dark yellow
    "b": "\033[38;5;39m",
    "g": "\033[38;5;46m",
    "m": "\033[38;5;165m",
    "w": "\033[38;5;231m",
    "y": "\033[38;5;226m",
    "s": "\033[38;5;196m",  # special characters, not a color
    "Lw": "\033[38;5;15m",  # bold white, bright white
    "Lg": "\033[38;5;10m",  # bold white, bright green
}


class MCDU:

    def __init__(self) -> None:
        self.datarefs = {}
        self.lines = {}
        self._req_vars = 0
        self.stdscr = None
        self.CURSES_COLORS = {}

    def init(self):
        pass

    def get_variables(self) -> set:
        variables = set()
        variables.add("AirbusFBW/MCDU1VertSlewKeys")
        for mcdu_unit in range(1, 2):
            variables = variables | self.get_variables1unit(mcdu_unit=mcdu_unit)
        self._req_vars = len(variables)
        return variables

    def get_variables1unit(self, mcdu_unit: int = 1) -> set:
        variables = set()
        # label
        for code in ["title", "stitle"]:
            for color in "bgwys":
                if code == "stitle" and color == "s":
                    continue  # skip
                variables.add(f"AirbusFBW/MCDU{mcdu_unit}{code}{color}")
        # scratchpad
        code = "sp"
        for color in "aw":
            variables.add(f"AirbusFBW/MCDU{mcdu_unit}{code}{color}")
        # lines
        for line in range(1, 7):
            for code in ["label", "cont", "scont"]:
                for color in MCDU_COLORS:
                    if code.endswith("cont") and color.startswith("L"):
                        continue  # skip
                    variables.add(f"AirbusFBW/MCDU{mcdu_unit}{code}{line}{color}")
        return variables

    def variable_changed(self, variable):
        ROOT = "AirbusFBW/MCDU"
        if not variable.value_changed():
            return
        if not variable.name.startswith(ROOT):
            return
        self.datarefs[variable.name] = variable
        mcdu_unit = -1
        try:
            mcdu_unit = int(variable.name[len(ROOT)])
        except:
            logger.warning("error for int {variable.name[len(ROOT)]}, {variable}")
            return
        if "title" in variable.name:
            self.update_title(variable, mcdu_unit=mcdu_unit)
        elif "sp" in variable.name:
            self.update_sp(variable, mcdu_unit=mcdu_unit)
        else:
            line = variable.name[-2]
            if line == "L":
                line = variable.name[-3]
            if "label" in variable.name:
                self.update_label(variable, mcdu_unit=mcdu_unit, line=line)
            else:
                self.update_line(variable, mcdu_unit=mcdu_unit, line=line)
        if len(self.datarefs) == self._req_vars:  # if got all data
            self.live_screen()

    def combine(self, l1, l2):
        line = []
        for i in range(24):
            if l1[i][0] == " ":
                line.append(l2[i])
                continue
            if l2[i][0] != " ":
                logger.debug(f"2 chars {l1[i]} / {l2[i]}")
            line.append(l1[i])
        return line

    def update_title(self, variable, mcdu_unit: int):
        lines = self.get_line_extra(mcdu_unit=mcdu_unit, what=["title", "stitle"], colors="bgwys")
        self.lines[f"AirbusFBW/MCDU{mcdu_unit}title"] = self.combine(lines[0], lines[1])

    def update_sp(self, variable, mcdu_unit: int):
        self.lines[f"AirbusFBW/MCDU{mcdu_unit}sp"] = self.get_line_extra(mcdu_unit=mcdu_unit, what=["sp"], colors="aw")[0]

    def update_label(self, variable, mcdu_unit: int, line: int):
        self.lines[f"AirbusFBW/MCDU{mcdu_unit}label{line}"] = self.get_line(mcdu_unit=mcdu_unit, line=line, what=["label"], colors=MCDU_COLORS)[0]

    def update_line(self, variable, mcdu_unit: int, line: int):
        lines = self.get_line(mcdu_unit=mcdu_unit, line=line, what=["cont", "scont"], colors=MCDU_COLORS)
        self.lines[f"AirbusFBW/MCDU{mcdu_unit}cont{line}"] = self.combine(lines[0], lines[1])

    def get_line_extra(self, mcdu_unit, what, colors):
        lines = []
        for code in what:
            this_line = []
            for c in range(24):
                has_char = []
                for color in colors:
                    if code == "stitle" and color == "s":  # if code in ["stitle", "title"] and color == "s":
                        continue
                    name = f"AirbusFBW/MCDU{mcdu_unit}{code}{color}"
                    d = self.datarefs.get(name)
                    if d is None:
                        logger.debug(f"no dataref {name}")
                        continue
                    v = d.value
                    if c < len(v):
                        if v[c] != " ":
                            has_char.append((v[c], color))
                if len(has_char) == 1:
                    this_line = this_line + has_char
                else:
                    if len(has_char) > 1:
                        logger.debug(f"mutiple char {code}, {c}: {has_char}")
                    this_line.append((" ", "w"))
            lines.append(this_line)
        return lines

    def get_line(self, mcdu_unit, line, what, colors):
        lines = []
        for code in what:
            this_line = []
            for c in range(24):
                has_char = []
                for color in colors:
                    if code.endswith("cont") and color.startswith("L"):
                        continue
                    name = f"AirbusFBW/MCDU{mcdu_unit}{code}{line}{color}"
                    d = self.datarefs.get(name)
                    if d is None:
                        logger.debug(f"no dataref {name}")
                        continue
                    v = d.value
                    if c < len(v):
                        if v[c] != " ":
                            has_char.append((v[c], color))
                if len(has_char) == 1:
                    this_line = this_line + has_char
                else:
                    if len(has_char) > 1:
                        logger.debug(f"mutiple char {code}, {c}: {has_char}")
                    this_line.append((" ", "w"))
            lines.append(this_line)
        return lines

    def build_screen(self):
        variable = list(self.datarefs.values())[0]
        mcdu_unit = int(variable.name[14])
        self.update_title(variable, mcdu_unit)
        self.update_sp(variable, mcdu_unit)
        for line in range(1, 7):
            self.update_label(variable, mcdu_unit, line)
            self.update_line(variable, mcdu_unit, line)

    def show_mcdu(self, mcdu_unit: int):
        def show_line(line):
            curr = ""
            for c in line:
                if c[1] == "s":  # "special" characters (rev. eng.)
                    if c[0] == "E":
                        c = ("☐", "a")
                    elif c[0] == "0":
                        c = ("←", "b")
                    elif c[0] == "2":
                        c = ("←", "w")
                    elif c[0] == "3":
                        c = ("→", "w")
                    elif c[0] == "A":
                        c = ("[", "b")
                    elif c[0] == "B":
                        c = ("]", "b")
                    elif c[0] == "`":  # does not print on terminal
                        c = ("°", c[1])
                if curr != c[1]:
                    curr = c[1]
                    print(MCDU_COLORS[c[1]], end="")
                print(c[0], end="")
            print("\033[0m")  # reset

        show_line(self.lines[f"AirbusFBW/MCDU{mcdu_unit}title"])
        for l in range(1, 7):
            show_line(self.lines[f"AirbusFBW/MCDU{mcdu_unit}label{l}"])
            show_line(self.lines[f"AirbusFBW/MCDU{mcdu_unit}cont{l}"])
        show_line(self.lines[f"AirbusFBW/MCDU{mcdu_unit}sp"])

    def live_screen(self):
        for mcdu_unit in range(1, 2):
            self.live_screen1unit(mcdu_unit=mcdu_unit)

    def live_screen1unit(self, mcdu_unit):
        # curses
        def show_line(line, linenum):
            curr = ""
            idx = 0
            for c in line:
                idx = idx + 1
                if c[1] == "s":  # "special" characters (rev. eng.)
                    if c[0] == "E":
                        c = ("☐", "a")
                    elif c[0] == "0":
                        c = ("←", "b")
                    elif c[0] == "1":
                        c = ("→", "w")
                    elif c[0] == "2":
                        c = ("←", "w")
                    elif c[0] == "3":
                        c = ("→", "w")
                    elif c[0] == "A":
                        c = ("[", "b")
                    elif c[0] == "B":
                        c = ("]", "b")
                    elif c[0] == "`":  # does not print on terminal
                        c = ("°", c[1])
                if curr != c[1]:
                    curr = c[1]
                color = self.CURSES_COLORS[c[1]]
                if c[1].startswith("L"):
                    color = color | curses.A_BOLD
                self.stdscr.addstr(linenum, idx, c[0], color)
                # print(linenum, idx, c[0])

        start_unit = 15 * (mcdu_unit - 1)

        if self.stdscr is None:
            self.stdscr = curses.initscr()
            curses.start_color()
            curses.use_default_colors()
            for i in range(0, curses.COLORS):
                curses.init_pair(i + 1, i, -1)
                self.CURSES_COLORS = {
                    "a": curses.color_pair(209),  # amber, dark yellow
                    "b": curses.color_pair(40),
                    "g": curses.color_pair(47),
                    "m": curses.color_pair(165),
                    "w": curses.color_pair(0),
                    "y": curses.color_pair(12),
                    "s": curses.color_pair(10),  # special characters, not a color
                    "Lw": curses.color_pair(16),  # bold white, bright white
                    "Lg": curses.color_pair(83),  # bold white, bright green
                }

        show_line(self.lines[f"AirbusFBW/MCDU{mcdu_unit}title"], start_unit + 1)
        for l in range(1, 7):
            show_line(self.lines[f"AirbusFBW/MCDU{mcdu_unit}label{l}"], start_unit + l * 2)
            show_line(self.lines[f"AirbusFBW/MCDU{mcdu_unit}cont{l}"], start_unit + l * 2 + 1)
        show_line(self.lines[f"AirbusFBW/MCDU{mcdu_unit}sp"], start_unit + 14)
        self.stdscr.refresh()

    def show_screen(self):
        for mcdu_unit in range(1, 2):
            self.show_mcdu(mcdu_unit=mcdu_unit)

    def save(self, fn):
        with open(fn, "w") as fp:
            json.dump({k: v.value for k, v in self.datarefs.items()}, fp, indent=2)

    def end(self):
        if self.stdscr is not None:
            self.stdscr.endwin()
            logger.info("ended nicely")


# import curses
# def main(stdscr):
#     curses.start_color()
#     curses.use_default_colors()
#     for i in range(0, curses.COLORS):
#         curses.init_pair(i + 1, i, -1)
#     try:
#         for i in range(0, 255):
#             stdscr.addstr(str(i) + "|", curses.color_pair(i))
#     except curses.ERR:
#         # End of screen reached
#         pass
#     stdscr.getch()
# curses.wrapper(main)
