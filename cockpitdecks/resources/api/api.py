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


if __name__ == "__main__":
    api = API(host="192.168.1.140", port=8080)
    # api.set_api("vx")
    api.set_api()
    all_datarefs = Cache(api)
    all_datarefs.load("/datarefs")
    if api.version == "v2":
        all_commands = Cache(api)
        all_commands.load("/commands")

    # # number
    # dref = Dataref("sim/cockpit2/gauges/actuators/barometer_setting_in_hg_pilot", cache=all_datarefs)
    # print(dref.ident, dref)

    # # string
    # dref = Dataref("sim/aircraft/view/acf_ICAO", cache=all_datarefs)
    # print(dref.ident, dref)

    # # write
    # dref = Dataref("sim/multiplayer/position/plane15_strobe_lights_on", cache=all_datarefs)
    # print(dref.ident, dref)
    # v = 0 if dref.value == 1 else 1
    # if dref.write(v):
    #     print("dataref written", dref)
    # else:
    #     print("dataref not written", dref)

    # cmd = Command("sim/map/show_current", cache=all_commands)
    # print(f"command {cmd.ident} was {'' if cmd.execute() else 'not '}executed")

    dref = Dataref("sim/network/dataout/data_to_screen", cache=all_datarefs)
    print(dref)
    dref.write_arr(1, 21)