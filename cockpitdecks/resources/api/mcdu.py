import logging
import base64
import json

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

DATA = "data"
IDENT = "id"
INDEX = "index"
NAME = "name"
DURATION = "duration"


class API:

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.version = ""
        self._api = ""
        self._capabilities = {}
        self.capabilities()

    @property
    def url(self):
        return f"http://{self.host}:{self.port}/api{self._api}"

    def capabilities(self) -> dict:
        # Guess capabilties and caches it
        if len(self._capabilities) > 0:
            return self._capabilities
        try:
            response = requests.get(self.url + "/capabilities")
            if response.status_code == 200:  # We have version 12.1.4 or above
                self._capabilities = response.json()
                logger.debug(f"capabilities: {self._capabilities}")
                return self._capabilities
            response = requests.get(self.url + "/v1/datarefs/count")
            if response.status_code == 200:  # OK, /api/v1 exists, we use it, we have version 12.1.1 or above
                self._capabilities = {"api": {"versions": ["v1"]}, "x-plane": {"version": "12"}}
                logger.debug(f"capabilities: {self._capabilities}")
                return self._capabilities
            logger.error(f"capabilities: response={response.status_code}")
        except:
            logger.error("capabilities", exc_info=True)
        return self._capabilities

    @property
    def xp_version(self) -> str | None:
        a = self._capabilities.get("x-plane")
        if a is None:
            return None
        return a.get("version")

    def set_api(self, api: str | None = None):
        api_details = self._capabilities.get("api")
        if api_details is not None:
            api_versions = api_details.get("versions")
            if api is None:
                if api_versions is None:
                    logger.error("cannot determine api")
                    return
                api = api_versions[-1]
            if api in api_versions:
                self.version = api
                self._api = "/" + api
                logger.info(f"set api {api}, xp {self.xp_version}")
            else:
                logger.warning(f"no api {api} in {api_versions}")
            return
        logger.warning(f"could not check api {api} in {self._capabilities}")


class Cache:
    def __init__(self, api: API) -> None:
        self.api = api
        self._data = dict()
        self._valid = set()

    def load(self, path):
        url = self.api.url + path
        response = requests.get(url)
        if response.status_code == 200:  # We have version 12.1.4 or above
            raw = response.json()
            data = raw[DATA]
            self._data = {c[NAME]: c for c in data}
            self._valid = set()
            logger.debug(f"{path[1:]} cached")
            return
        logger.error(f"load: response={response.status_code}")

    @property
    def has_data(self) -> bool:
        return self._data is not None and len(self._data) > 0

    def get(self, name):
        r = self._data.get(name)
        if r is not None:
            self._valid.add(name)
            return r
        return None

    def is_valid(self, name):
        return name in self._valid


class XPObject:

    def __init__(self, path: str, cache: Cache) -> None:
        self.path = path
        self.config = cache.get(self.path)
        self.api = None
        self.valid = False
        if self.config is None:
            logger.error(f"{type(self)} {self.path} not found")
        else:
            self.api = cache.api
            self.valid = True

    @property
    def ident(self) -> int | None:
        if not self.valid:
            return None
        return self.config[IDENT]


class Dataref(XPObject):
    def __init__(self, path: str, cache: Cache) -> None:
        XPObject.__init__(self, path=path, cache=cache)

    def __str__(self) -> str:
        return f"{self.path}={self.value}"

    @property
    def value(self):
        if not self.valid:
            logger.error(f"dataref {self.path} not found")
            return None
        url = f"{self.api.url}/datarefs/{self.ident}/value"
        response = requests.get(url)
        data = response.json()
        logger.debug(f"result: {data}")
        if DATA in data and type(data[DATA]) in [bytes, str]:
            return base64.b64decode(data[DATA])[:-1].decode("ascii").replace("\u0000", "")
        return data[DATA]

    def write(self, value) -> bool:
        if not self.valid:
            logger.error(f"dataref {self.path} not found")
            return False
        payload = {IDENT: self.ident, DATA: value}
        url = f"{self.api.url}/datarefs/{self.ident}/value"
        response = requests.patch(url, json=payload)
        if response.status_code == 200:
            data = response.json()
            logger.debug(f"result: {data}")
            return True
        logger.error(f"write: {response.reason}")
        return False

    def write_arr(self, value, index) -> bool:
        if not self.valid:
            logger.error(f"dataref {self.path} not found")
            return False
        payload = {IDENT: self.ident, DATA: int(value), INDEX: index}
        url = f"{self.api.url}/datarefs/{self.ident}/value"
        print("payload", payload)
        response = requests.patch(url, json=payload)
        if response.status_code == 200:
            data = response.json()
            logger.debug(f"result: {data}")
            return True
        logger.error(f"write: {response.reason}, {response.text}")
        return False


class Command(XPObject):
    def __init__(self, path: str, cache: Cache) -> None:
        XPObject.__init__(self, path=path, cache=cache)

    def execute(self) -> bool:
        if not self.valid:
            logger.error(f"command {self.path} not found")
            return False
        payload = {IDENT: self.ident, DURATION: 0.0}
        url = f"{self.api.url}/command/{self.ident}/activate"
        response = requests.post(url, json=payload)
        data = response.json()
        if response.status_code == 200:
            logger.debug(f"result: {data}")
            return True
        logger.error(f"execute: {response}, {data}")
        return False


MCDU_COLORS = {
    "a": "\033[38;5;208m",  # amber, dark yellow
    "b": "\033[38;5;39m",
    "g": "\033[38;5;46m",
    "m": "\033[38;5;165m",
    "w": "\033[38;5;231m",
    "y": "\033[38;5;226m",
    "s": "\033[38;5;196m",
    "Lw": "\033[38;5;15m",  # bold white, bright white
    "Lg": "\033[38;5;10m",
}


def print_extra(lines, mcdu_unit, what, colors):
    screen = []
    for code in what:
        this_line = []
        for c in range(24):
            has_char = []
            for color in colors:
                if code == "stitle" and color == "s":
                    continue
                d = f"AirbusFBW/MCDU{mcdu_unit}{code}{color}"
                v = lines.get(d)
                if v is None:
                    print("no dataref", d)
                else:
                    if c < len(v):
                        if v[c] != " ":
                            has_char.append((v[c], color))
            if len(has_char) == 1:
                this_line = this_line + has_char
            else:
                if len(has_char) > 1:
                    print(f"mutiple char {code}, {c}: {has_char}")
                this_line.append((" ", "w"))
        screen.append(this_line)
    return screen


def get_char(lines, mcdu_unit, l, c, line_code):
    for color in MCDU_COLORS:
        if line_code.endswith("cont") and color.startswith("L"):
            continue
        d = f"AirbusFBW/MCDU{mcdu_unit}{line_code}{l}{color}"
        # line.format(mcdu_unit=1, line=l, color=color)
        v = lines.get(d)
        if v is None:
            print("no dataref", d)
            continue
        if c < len(v):
            if v[c] != " ":
                return v[c], color
    return " ", "w"


def print_screen(lines, mcdu_unit):
    screen = []
    for l in range(6):
        line = l + 1
        for code in ["label", "cont", "scont"]:
            this_line = []
            for char in range(24):
                d = get_char(lines, mcdu_unit, line, char, code)
                this_line.append(d)
            screen.append(this_line)
    return screen


def combine(lines):
    def combi(l1, l2):
        line = []
        for i in range(24):
            if l1[i][0] == " ":
                line.append(l2[i])
                continue
            if l2[i][0] != " ":
                print(f"2 chars {l1[i]} / {l2[i]}")
            line.append(l1[i])
        return line

    screen = []
    for i in range(0, 21, 3):
        screen.append(combi(lines[i], lines[i + 1]))
        screen.append(lines[i + 2])
    return screen


def print_mcdu(lines, mcdu_unit):
    screen = print_extra(lines, mcdu_unit, ["title", "stitle"], "bgwys")
    screen = screen + print_screen(lines, mcdu_unit)
    screen = screen + print_extra(lines, mcdu_unit, ["sp"], "aw")
    screen = combine(screen)
    return screen


def print_color(lines):
    for line in lines:
        curr = ""
        for c in line:
            if c[1] == "s":  # "special" characters (rev. eng.)
                if c[0] == "E":
                    c = ("☐", "a")
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


if __name__ == "__main__":
    api = API(host="192.168.1.140", port=8080)
    # api.set_api("vx")
    api.set_api()
    all_datarefs = Cache(api)
    all_datarefs.load("/datarefs")
    if api.version == "v2":
        all_commands = Cache(api)
        all_commands.load("/commands")

    data = []
    with open("mcdu.txt", "r") as fp:
        data = fp.readlines()
        # data = txt.split("\n")

    print("getting data..", end="", flush=True)
    mcdu = {}
    for d in data:
        d = d[:-1]
        dref = Dataref(d, cache=all_datarefs)
        mcdu[d] = dref.value
        # print(d, mcdu[d], f"({len(mcdu[d])})" if type(mcdu[d]) is str else type(mcdu[d]))
        print(".", end="", flush=True)
    print("..done")

    with open("mcdu.out", "w") as fp:
        json.dump(mcdu, fp, indent=2)

    print_color(print_mcdu(mcdu, 1))
