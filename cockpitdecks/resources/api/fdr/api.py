from __future__ import annotations

import socket
import threading
import logging
import json
import base64
import time

from abc import ABC, abstractmethod
from enum import Enum
from datetime import datetime, timedelta

# Packaging is used in Cockpit to check driver versions
from packaging.version import Version

# REST API
import requests

# WEBSOCKET API
from simple_websocket import Client, ConnectionClosed

from beacon import XPlaneBeacon, BEACON_DATA_KW

from fdr import FDR

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
webapi_logger = logging.getLogger("webapi")

# #############################################
# CONFIGURATION AND OPTIONS
#
# Data too delicate to be put in constant.py
# !! adjust with care !!
# UDP sends at most ~40 to ~50 dataref values per packet.
RECONNECT_TIMEOUT = 10  # seconds, times between attempts to reconnect to X-Plane when not connected (except on initial startup, see dynamic_timeout)
RECEIVE_TIMEOUT = 5  # seconds, assumes no awser if no message recevied withing that timeout

XP_MIN_VERSION = 121400
XP_MIN_VERSION_STR = "12.1.4"
XP_MAX_VERSION = 121499
XP_MAX_VERSION_STR = "12.1.4"

RUNNING_TIME = "sim/time/total_flight_time_sec"  # Total time since the flight got reset by something


# /api/capabilities introduced in /api/v2. Here is a default one for v1.
V1_CAPABILITIES = {"api": {"versions": ["v1"]}, "x-plane": {"version": "12.1.1"}}
USE_REST = True  # force REST usage for remote access, otherwise websockets is privileged


# REST KEYWORDS
class REST_KW(Enum):
    COMMANDS = "commands"
    DATA = "data"
    DATAREFS = "datarefs"
    DESCRIPTION = "description"
    DURATION = "duration"
    IDENT = "id"
    INDEX = "index"
    ISACTIVE = "is_active"
    ISWRITABLE = "is_writable"
    NAME = "name"
    PARAMS = "params"
    REQID = "req_id"
    RESULT = "result"
    SUCCESS = "success"
    TYPE = "type"
    VALUE = "value"
    VALUE_TYPE = "value_type"


# DATAREF VALUE TYPES
class DATAREF_DATATYPE(Enum):
    INTEGER = "int"
    FLOAT = "float"
    DOUBLE = "double"
    INTARRAY = "int_array"
    FLOATARRAY = "float_array"
    DATA = "data"


# WEB API RETURN CODES
class REST_RESPONSE(Enum):
    RESULT = "result"
    COMMAND_ACTIVE = "command_update_is_active"
    DATAREF_UPDATE = "dataref_update_values"


# #############################################
# CORE ENTITIES
#
class DatarefMeta:

    def __init__(self, name: str, value_type: str, is_writable: bool, **kwargs) -> None:
        self.name = name
        self.ident = kwargs.get("id")
        self.value_type = value_type
        self.is_writable = is_writable
        self.indices = list()
        self.indices_history = []

        self.updates = 0
        self._last_req_number = 0
        self._previous_value = None
        self._current_value = None

    @property
    def value(self):
        return self._current_value

    @value.setter
    def value(self, value):
        self._previous_value = self._current_value
        self._current_value = value
        self.updates = self.updates + 1

    @property
    def is_array(self) -> bool:
        return self.value_type in [DATAREF_DATATYPE.INTARRAY.value, DATAREF_DATATYPE.FLOATARRAY.value]

    def save_indices(self):
        self.indices_history.append(self.indices.copy())

    def last_indices(self) -> list:
        if len(self.indices_history) > 0:
            return self.indices_history[-1]
        return []

    def append_index(self, i):
        if i not in self.indices:
            self.indices.append(i)
            """Note from Web API instruction/manual:
            If you subscribed to certain indexes of the dataref, they’ll be sent in the index order
            but no sparse arrays will be sent. For example if you subscribed to indexes [1, 5, 7] you’ll get
            a 3 item array like [200, 200, 200], meaning you need to remember that the first item of that response
            corresponds to index 1, the second to index 5 and the third to index 7 of the dataref.
            This also means that if you subscribe to index 2 and later to index 0 you’ll get them as [0,2].

            HENCE current_indices.sort()

            So bottom line is — keep it simple: either ask for a single index, or a range,
            or all; and if later your requirements change, unsubscribe, then subscribe again.
            """
            self.indices.sort()

    def remove_index(self, i):
        # there is a problem if we remove a key here, and then still get
        # an array of values that contains the removed index
        if i in self.indices:
            self.indices.remove(i)
        else:
            logger.warning(f"{self.name} index {i} not in {self.indices}")


class CommandMeta:

    def __init__(self, name: str, description: str, **kwargs) -> None:
        self.name = name
        self.ident = kwargs.get("id")
        self.description = description


class APIMeta:

    @classmethod
    def new(cls, **kwargs):
        if "is_writable" in kwargs:
            return DatarefMeta(**kwargs)
        return CommandMeta(**kwargs)


class Cache:
    """Accessory structure to host datarref and command cache
    of current X-Plane instance.
    Must be "refreshed" each time a new connection is created.
    Must be refreshed each time a new aircraft is loaded (for new datarefs, commands, etc.)
    Reload_cache() is provided in XPlaneREST.

    There is no faster structure than a python dict() for (name,value) pair storage.
    """

    def __init__(self, api: XPlaneREST) -> None:
        self.api = api
        self._raw = {}
        self._by_name = dict()
        self._by_ids = dict()
        self._last_updated = 0

    def load(self, path):
        url = self.api.api_url + path
        response = requests.get(url)
        if response.status_code != 200:  # We have version 12.1.4 or above
            logger.error(f"load: response={response.status_code}")
            return
        raw = response.json()
        data = raw[REST_KW.DATA.value]
        self._raw = data

        metas = [APIMeta.new(**c) for c in data]
        self.last_cached = datetime.now().timestamp()
        self._by_name = {m.name: m for m in metas}
        self._by_ids = {m.ident: m for m in metas}

        logger.debug(f"{path[1:]} cached ({len(metas)} entries)")

    @property
    def count(self) -> int:
        return 0 if self._by_name is None else len(self._by_name)

    @property
    def has_data(self) -> bool:
        return self._by_name is not None and len(self._by_name) > 0

    def get(self, name) -> DatarefMeta | CommandMeta | None:
        return self.get_by_name(name=name)

    def get_by_name(self, name) -> DatarefMeta | CommandMeta | None:
        return self._by_name.get(name)

    def get_by_id(self, ident: int) -> DatarefMeta | CommandMeta | None:
        return self._by_ids.get(ident)

    def save(self, filename):
        with open(filename, "w") as fp:
            json.dump(self._raw, fp)

    def equiv(self, ident) -> str | None:
        r = self._by_ids.get(ident)
        if r is not None:
            return f"{ident}({r.name})"
        return f"no equivalence for {ident}"


class Dataref:
    def __init__(self, path: str, api):
        # Data
        self.api = api
        self.name = path
        self._monitored = 0

        # path with array index sim/some/values[4]
        self.path = path
        self.index = None  # sign is it not a selected array element
        if "[" in path:
            self.path = self.name[: self.name.find("[")]  # sim/some/values
            self.index = int(self.name[self.name.find("[") + 1 : self.name.find("]")])  # 4

    def __str__(self) -> str:
        if self.index is not None:
            return f"{self.path}[{self.index}]={self.value}"
        else:
            return f"{self.path}={self.value}"

    @property
    def meta(self) -> DatarefMeta | None:
        r = self.api.all_datarefs.get(self.path) if self.api.all_datarefs is not None else None
        if r is None:
            logger.error(f"dataref {self.path} has no api meta data")
        return r

    @property
    def valid(self) -> bool:
        return self.meta is not None

    @property
    def ident(self) -> int | None:
        if not self.valid:
            logger.error(f"dataref {self.path} not valid")
            return None
        return self.meta.ident

    @property
    def value_type(self) -> str | None:
        if not self.valid:
            logger.error(f"dataref {self.path} not valid")
            return None
        return self.meta.value_type

    @property
    def is_writable(self) -> bool:
        if not self.valid:
            logger.error(f"dataref {self.path} not valid")
            return False
        return self.meta.is_writable

    @property
    def is_array(self) -> bool:
        if not self.valid:
            logger.error(f"dataref {self.path} not valid")
            return False
        return self.value_type in [DATAREF_DATATYPE.INTARRAY.value, DATAREF_DATATYPE.FLOATARRAY.value]

    @property
    def selected_indices(self) -> bool:
        if not self.valid:
            logger.error(f"dataref {self.path} not valid")
            return False
        return len(self.meta.indices) > 0

    @property
    def use_rest(self):
        return USE_REST and (hasattr(self.api, "same_host") and not self.api.same_host())

    @property
    def rest_value(self):
        if not self.valid:
            logger.error(f"dataref {self.path} not valid")
            return False
        url = f"{self.api.api_url}/datarefs/{self.ident}/value"
        response = requests.get(url)
        if response.status_code == 200:
            respjson = response.json()
            webapi_logger.info(f"GET {self.path}: {url} = {respjson}")
            if REST_KW.DATA.value in respjson and type(respjson[REST_KW.DATA.value]) in [bytes, str]:
                return base64.b64decode(respjson[REST_KW.DATA.value]).decode("ascii").replace("\u0000", "")
            return respjson[REST_KW.DATA.value]
        webapi_logger.info(f"ERROR {self.path}: {response} {response.reason} {response.text}")
        logger.error(f"rest_value: {response} {response.reason} {response.text}")
        return None

    @property
    def is_monitored(self):
        return self._monitored > 0

    @property
    def monitored_count(self) -> int:
        return self._monitored

    def monitor(self):
        self._monitored = self._monitored + 1

    def unmonitor(self) -> bool:
        # IF returns False, no longer monitored
        if self._monitored > 0:
            self._monitored = self._monitored - 1
        else:
            logger.warning(f"{self.name} currently not monitored")
        return self._monitored > 0

    def rest_write(self) -> bool:
        if not self.valid:
            logger.error(f"dataref {self.path} not valid")
            return False
        if not self.is_writable:
            logger.warning(f"dataref {self.path} is not writable")
            return False
        value = self.value
        if self.value_type == DATAREF_DATATYPE.DATA.value:
            # Encode string
            value = str(value).encode("ascii")
            value = base64.b64encode(value).decode("ascii")
        payload = {REST_KW.DATA.value: value}
        url = f"{self.api.api_url}/datarefs/{self.ident}/value"
        if self.index is not None and self.value_type in [DATAREF_DATATYPE.INTARRAY.value, DATAREF_DATATYPE.FLOATARRAY.value]:
            # Update just one element of the array
            url = url + f"?index={self.index}"
        webapi_logger.info(f"PATCH {self.path}: {url}, {payload}")
        response = requests.patch(url, json=payload)
        if response.status_code == 200:
            data = response.json()
            logger.debug(f"result: {data}")
            return True
        webapi_logger.info(f"ERROR {self.path}: {response} {response.reason} {response.text}")
        logger.error(f"write: {response} {response.reason} {response.text}")
        return False

    def ws_write(self) -> int:
        return self.api.set_dataref_value(self.name, self.value)

    def _write(self) -> bool:
        return self.rest_write() if self.use_rest else (self.ws_write() != -1)

    def save(self) -> bool:
        if not self.valid:
            logger.error(f"dataref {self.path} not valid")
            return False
        return self._write()

    def parse_raw_value(self, raw_value):
        if not self.valid:
            logger.error(f"dataref {self.path} not valid")
            return None

        if self.value_type in [DATAREF_DATATYPE.INTARRAY.value, DATAREF_DATATYPE.FLOATARRAY.value]:
            # 1. Arrays
            # 1.1 Whole array
            if type(raw_value) is not list:
                logger.warning(f"dataref array {self.name}: value: is not a list ({value}, {type(value)})")
                return None

            if len(self.meta.indices) == 0:
                logger.debug(f"dataref array {self.name}: no index, returning whole array")
                return raw_value

            # 1.2 Single array element
            if len(raw_value) != len(self.meta.indices):
                logger.warning(f"dataref array {self.name} size mismatch ({len(raw_value)}/{len(self.meta.indices)})")
                logger.warning(f"dataref array {self.name}: value: {raw_value}, indices: {self.meta.indices})")
                return None

            idx = self.meta.indices.index(self.index)
            if idx == -1:
                logger.warning(f"dataref index {self.index} not found in {self.meta.indices}")
                return None

            logger.debug(f"dataref array {self.name}: returning {self.name}[{idx}]={raw_value[idx]}")
            return raw_value[idx]

        else:
            # 2. Scalar values
            # 2.1  String
            if self.value_type == "data" and type(raw_value) in [bytes, str]:
                return base64.b64decode(raw_value).decode("ascii").replace("\u0000", "")

            # 2.1  Number
            elif type(raw_value) not in [int, float]:
                logger.warning(f"unknown value type for {self.name}: {type(raw_value)}, {raw_value}, expected {self.value_type}")

        return raw_value


class Instruction(ABC):
    """An Instruction sent to the XPlane Simulator to execute some action.

    This is more an abstract base class, with a new() factory to handle instruction block.
    """

    def __init__(self, name: str, api) -> None:
        self.name = name
        self.api = api

    @property
    def meta(self) -> CommandMeta | None:
        r = self.api.all_commands.get(self.path) if self.api.all_commands is not None else None
        if r is None:
            logger.error(f"dataref {self.path} hos no api meta data")
        return r

    @property
    def valid(self) -> bool:
        return self.meta is not None

    @property
    def ident(self) -> int | None:
        if not self.valid:
            logger.error(f"dataref {self.path} not valid")
            return None
        return self.meta.ident

    @property
    def description(self) -> str | None:
        if not self.valid:
            return None
        return self.meta.description

    @property
    def use_rest(self):
        return USE_REST and (hasattr(self.api, "same_host") and not self.api.same_host())

    @property
    def is_no_operation(self) -> bool:
        return self.path is not None and self.path.lower().replace("-", "") in NOT_A_COMMAND

    @abstractmethod
    def rest_execute(self) -> bool:  # ABC
        return False

    @abstractmethod
    def ws_execute(self) -> int:  # ABC
        return -1

    def _execute(self):
        if self.use_rest:
            self.rest_execute()
        else:
            self.ws_execute()


class Command(Instruction):
    """
    X-Plane simple Command, executed by CommandOnce API.
    """

    def __init__(self, api, path: str, name: str | None = None):
        Instruction.__init__(self, name=name if name is not None else path, api=api)
        self.path = path  # some/command

    def __str__(self) -> str:
        return f"{self.name} ({self.path})"

    def is_valid(self) -> bool:
        return not self.is_no_operation

    def rest_execute(self) -> bool:
        if not self.is_valid():
            logger.error(f"command {self.path} is not valid")
            return False
        if not self.valid:
            self.init(cache=self.api.all_commands)
            if not self.valid:
                logger.error(f"command {self.path} is not valid")
                return False
        payload = {REST_KW.IDENT.value: self.ident, REST_KW.DURATION.value: 0.0}
        url = f"{self.api.api_url}/command/{self.ident}/activate"
        response = requests.post(url, json=payload)
        webapi_logger.info(f"POST {url} {payload} {response}")
        data = response.json()
        if response.status_code == 200:
            logger.debug(f"result: {data}")
            return True
        logger.error(f"execute: {response}, {data}")
        return False

    def ws_execute(self) -> int:
        return self.api.set_command_is_active_with_duration(path=self.path)


class BeginEndCommand(Command):
    """
    X-Plane long command, executed between CommandBegin/CommandEnd API.
    """

    DURATION = 5

    def __init__(self, api, path: str, name: str | None = None):
        Command.__init__(self, api=api, path=path, name=name)  # force no delay for commandBegin/End
        self.is_on = False

    def rest_execute(self) -> bool:
        if not self.valid:
            self.init(cache=self.api.all_commands)
            if not self.valid:
                logger.error(f"command {self.path} is not valid")
                return False
        if not self.is_valid():
            logger.error(f"command {self.path} is not valid")
            return False
        payload = {REST_KW.IDENT.value: self.ident, REST_KW.DURATION.value: self.DURATION}
        url = f"{self.api.api_url}/command/{self.ident}/activate"
        response = requests.post(url, json=payload)
        webapi_logger.info(f"POST {url} {payload} {response}")
        data = response.json()
        if response.status_code == 200:
            logger.debug(f"result: {data}")
            return True
        logger.error(f"execute: {response}, {data}")
        return False

    def ws_execute(self) -> int:
        if not self.is_valid:
            logger.error(f"command {self.path} not found")
            return -1
        self.is_on = not self.is_on
        return self.api.set_command_is_active_without_duration(path=self.path, active=self.is_on)


class SetDataref(Instruction):
    """
    Instruction to update the value of a dataref in X-Plane api.
    """

    def __init__(self, api, path: str, value=None):
        Instruction.__init__(self, name=path, api=api)
        self.path = path  # some/dataref/to/set
        self._variable = api.get_variable(path)

        # Generic, non computed static fixed value
        self._value = value

    def __str__(self) -> str:
        return "set-dataref: " + self.name

    @property
    def value(self):
        if self.formula is not None:
            if self.text_value is not None:
                logger.warning(f"{type(self).__name__} for {self.path} has both formula and text value, returning formula (text value ignored)")
            return self.formula.value
        if self.text_value is not None:
            return self.text_value.value
        return self._value

    @value.setter
    def value(self, value):
        self._value = value

    def rest_execute(self) -> bool:
        if not self.valid:
            self.init(cache=self.api.all_datarefs)
            if not self.valid:
                logger.error(f"dataref {self.path} is not valid")
                return False
        value = self.value
        if self.value_type == "data":
            value = str(value).encode("ascii")
            value = base64.b64encode(value).decode("ascii")
        payload = {REST_KW.DATA.value: self.value}
        url = f"{self.api.api_url}/datarefs/{self.ident}/value"
        response = requests.patch(url, json=payload)
        webapi_logger.info(f"PATCH {url} {payload} {response}")
        if response.status_code == 200:
            return True
        if response.status_code == 403:
            logger.warning(f"{self.name}: dataref not writable")
            return False
        logger.error(f"execute: {response}")
        return False

    def ws_execute(self) -> int:
        if not self.valid:
            logger.error(f"set-dataref {self.path} invalid")
            return -1
        return self.api.set_dataref_value(path=self.path, value=self.value)

    def _execute(self):
        super()._execute()


# #############################################
# REST API
#
class XPlaneREST:
    """Utility routines specific to REST API.
       Used by variables and instructions to execute their tasks.

    See https://developer.x-plane.com/article/x-plane-web-api/#REST_API.
    """

    def __init__(self, host: str, port: int, api: str, api_version: str) -> None:
        self.host = host
        self.port = port
        self._api_root_path = api
        if not self._api_root_path.startswith("/"):
            self._api_root_path = "/" + api
        self._api_version = api_version  # /v1, /v2, to be appended to URL
        if not self._api_version.startswith("/"):
            self._api_version = "/" + self._api_version
        self._first_try = True

        self.version = api_version  # v1, v2, etc.
        if self.version.startswith("/"):
            self.version = self.version[1:]

        self._capabilities = {}
        self._beacon = XPlaneBeacon()
        self.dynamic_timeout = RECONNECT_TIMEOUT
        self._beacon.set_callback(self.beacon_callback)
        self._running_time = Dataref(path=RUNNING_TIME, api=self)  # cheating, side effect, works for rest api only, do not force!

        self.all_datarefs: Cache | None = None
        self.all_commands: Cache | None = None
        self._last_updated = 0
        self._warning_count = 0
        self._dataref_by_id = {}  # {dataref-id: Dataref}

    @property
    # See https://stackoverflow.com/questions/7019643/overriding-properties-in-python
    # to overwrite @property definition
    def api_url(self) -> str:
        """URL for the REST API"""
        return f"http://{self.host}:{self.port}{self._api_root_path}{self._api_version}"

    @property
    def uptime(self) -> float:
        if self._running_time is not None:
            r = self._running_time.rest_value
            if r is not None:
                return float(r)
        return 0.0

    @property
    def api_is_available(self) -> bool:
        """Important call that checks whether API is reachable
        API may not be reachable if:
         - X-Plane version before 12.1.4,
         - X-Plane is not running
        """
        CHECK_API_URL = f"http://{self.host}:{self.port}/api/v1/datarefs/count"
        response = None
        if self._first_try:
            logger.info(f"trying to connect to {CHECK_API_URL}..")
            self._first_try = False
        try:
            # Relies on the fact that first version is always provided.
            # Later verion offer alternative ot detect API
            response = requests.get(CHECK_API_URL)
            if response.status_code == 200:
                return True
        except requests.exceptions.ConnectionError:
            if self._warning_count % 20 == 0:
                logger.warning("api unreachable, may be X-Plane is not running")
                self._warning_count = self._warning_count + 1
        except:
            logger.error("api unreachable, may be X-Plane is not running", exc_info=True)
        return False

    def same_host(self) -> bool:
        return self._beacon.same_host() if self.connected else False

    def beacon_callback(self, connected: bool):
        if connected:
            logger.info("X-Plane beacon connected")
            if self._beacon.connected:
                self.dynamic_timeout = 0.5  # seconds
                same_host = self._beacon.same_host()
                if same_host:
                    self.host = "127.0.0.1"
                    self.port = 8086
                else:
                    self.host = self._beacon.beacon_data[BEACON_DATA_KW.IP.value]
                    self.port = 8080
                xp_version = self._beacon.beacon_data.get(BEACON_DATA_KW.XPVERSION.value)
                if xp_version is not None:
                    use_rest = ", use REST" if USE_REST and not same_host else ""
                    if self._beacon.beacon_data[BEACON_DATA_KW.XPVERSION.value] >= 121400:
                        self._api_version = "/v2"
                        self._first_try = True
                        logger.info(f"XPlane API at {self.api_url} from UDP beacon data{use_rest}")
                    elif self._beacon.beacon_data[BEACON_DATA_KW.XPVERSION.value] >= 121100:
                        self._api_version = "/v1"
                        self._first_try = True
                        logger.info(f"XPlane API at {self.api_url} from UDP beacon data{use_rest}")
                    else:
                        logger.warning(f"could not set API version from {xp_version} ({self._beacon.beacon_data})")
                else:
                    logger.warning(f"could not get X-Plane version from {self._beacon.beacon_data}")
            else:
                logger.info("XPlane UDP beacon is not connected")
        else:
            logger.warning("X-Plane beacon disconnected")

    def capabilities(self) -> dict:
        # Guess capabilties and caches it
        if len(self._capabilities) > 0:
            return self._capabilities
        try:
            CAPABILITIES_API_URL = f"http://{self.host}:{self.port}/api/capabilities"  # independent from version
            response = requests.get(CAPABILITIES_API_URL)
            if response.status_code == 200:  # We have version 12.1.4 or above
                self._capabilities = response.json()
                logger.debug(f"capabilities: {self._capabilities}")
                return self._capabilities
            logger.info(f"capabilities at {self.api_url + '/capabilities'}: response={response.status_code}")
            response = requests.get(self.api_url + "/v1/datarefs/count")
            if response.status_code == 200:  # OK, /api/v1 exists, we use it, we have version 12.1.1 or above
                self._capabilities = V1_CAPABILITIES
                logger.debug(f"capabilities: {self._capabilities}")
                return self._capabilities
            logger.error(f"capabilities at {self.api_url + '/datarefs/count'}: response={response.status_code}")
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
        capabilities = self.capabilities()
        api_details = capabilities.get("api")
        if api_details is not None:
            api_versions = api_details.get("versions")
            if api is None:
                if api_versions is None:
                    logger.error("cannot determine api, api not set")
                    return
                api = sorted(api_versions)[-1]  # takes the latest one, hoping it is the latest in time...
                latest = ""
                try:
                    api = f"v{max([int(v.replace('v', '')) for v in api_versions])}"
                    latest = " latest"
                except:
                    pass
                logger.info(f"selected{latest} api {api} ({sorted(api_versions)})")
            if api in api_versions:
                self.version = api
                self._api_version = f"/{api}"
                logger.info(f"set api {api}, xp {self.xp_version}")
            else:
                logger.warning(f"no api {api} in {api_versions}")
            return
        logger.warning(f"could not check api {api} in {capabilities}")

    def reload_caches(self):
        MINTIME_BETWEEN_RELOAD = 10  # seconds
        if self._last_updated != 0:
            currtime = self._running_time.rest_value
            if currtime is not None:
                difftime = currtime - self._last_updated
                if difftime < MINTIME_BETWEEN_RELOAD:
                    logger.info(f"dataref cache not updated, updated {round(difftime, 1)} secs. ago")
                    return
            else:
                logger.warning("no value for sim/time/total_running_time_sec")
        self.all_datarefs = Cache(self)
        self.all_datarefs.load("/datarefs")
        self.all_datarefs.save("webapi-datarefs.json")
        self.all_commands = Cache(self)
        if self.version == "v2":  # >
            self.all_commands.load("/commands")
            self.all_commands.save("webapi-commands.json")
        currtime = self._running_time.rest_value
        if currtime is not None:
            self._last_updated = self._running_time.rest_value
        else:
            logger.warning("no value for sim/time/total_running_time_sec")
        logger.info(
            f"dataref cache ({self.all_datarefs.count}) and command cache ({self.all_commands.count}) reloaded, sim uptime {str(timedelta(seconds=int(self.uptime)))}"
        )

    def rebuild_dataref_ids(self):
        if self.all_datarefs.has_data and len(self._dataref_by_id) > 0:
            self._dataref_by_id = {d.ident: d for d in self._dataref_by_id}
            logger.info("dataref ids rebuilt")
            return
        logger.warning("no data to rebuild dataref ids")

    def get_dataref_meta_by_name(self, path: str) -> DatarefMeta | None:
        return self.all_datarefs.get_by_name(path) if self.all_datarefs is not None else None

    def get_command_meta_by_name(self, path: str) -> CommandMeta | None:
        return self.all_commands.get_by_name(path) if self.all_commands is not None else None

    def get_dataref_meta_by_id(self, ident: int) -> DatarefMeta | None:
        return self.all_datarefs.get_by_id(ident) if self.all_datarefs is not None else None

    def get_command_meta_by_id(self, ident: int) -> CommandMeta | None:
        return self.all_commands.get_by_id(ident) if self.all_commands is not None else None


# #############################################
# WEBSOCKET API
#
class XPlaneWebSocket(XPlaneREST):
    """Utility routines specific to WebSocket API

    See https://developer.x-plane.com/article/x-plane-web-api/#Websockets_API.
    """

    MAX_WARNING = 5  # number of times it reports it cannot connect

    def __init__(self, host: str = "127.0.0.1", port: int = 8086, api: str = "api", api_version: str = "v2"):
        # Open a UDP Socket to receive on Port 49000
        XPlaneREST.__init__(self, host=host, port=port, api=api, api_version=api_version)
        hostname = socket.gethostname()
        self.local_ip = socket.gethostbyname(hostname)

        self.ws = None  # None = no connection
        self.ws_event = threading.Event()
        self.ws_event.set()  # means it is off
        self.ws_thread = None

        self.req_number = 0
        self._requests = {}

        self.should_not_connect = None  # threading.Event()
        self.connect_thread = None  # threading.Thread()
        self._already_warned = 0
        self._stats = {}

    @property
    def ws_url(self) -> str:
        """URL for the WebSocket API"""
        url = self.api_url
        return url.replace("http:", "ws:")

    @property
    def next_req(self) -> int:
        """Provides request number for WebSocket requests"""
        self.req_number = self.req_number + 1
        return self.req_number

    # ################################
    # Connection to web socket
    #
    @property
    def connected(self) -> bool:
        res = self.ws is not None
        if not res and not self._already_warned > self.MAX_WARNING:
            if self._already_warned == self.MAX_WARNING:
                logger.warning("no connection (last warning)")
            else:
                logger.warning("no connection")
            self._already_warned = self._already_warned + 1
        return res

    def connect_websocket(self):
        if self.ws is None:
            try:
                if self.api_is_available:
                    self.set_api()  # attempt to get latest one
                    url = self.ws_url
                    if url is not None:
                        self.ws = Client.connect(url)
                        self.reload_caches()
                        logger.info(f"websocket opened at {url}")
                    else:
                        logger.warning(f"web socket url is none {url}")
            except:
                logger.error("cannot connect", exc_info=True)
        else:
            logger.warning("already connected")

    def disconnect_websocket(self):
        if self.ws is not None:
            self.ws.close()
            self.ws = None
            logger.info("websocket closed")
        else:
            logger.warning("already disconnected")

    def connect_loop(self):
        """
        Trys to connect to X-Plane indefinitely until self.should_not_connect is set.
        If a connection fails, drops, disappears, will try periodically to restore it.
        """
        logger.debug("starting connection monitor..")
        MAX_TIMEOUT_COUNT = 5
        WARN_FREQ = 10
        number_of_timeouts = 0
        to_count = 0
        noconn = 0
        while self.should_not_connect is not None and not self.should_not_connect.is_set():
            if not self.connected:
                try:
                    if noconn % WARN_FREQ == 0:
                        logger.info("not connected, trying..")
                        noconn = noconn + 1
                    self.connect_websocket()
                    if self.connected:
                        self._already_warned = 0
                        number_of_timeouts = 0
                        self.dynamic_timeout = RECONNECT_TIMEOUT
                        logger.info(f"capabilities: {self.capabilities()}")
                        if self.xp_version is not None:
                            curr = Version(self.xp_version)
                            xpmin = Version(XP_MIN_VERSION_STR)
                            xpmax = Version(XP_MAX_VERSION_STR)
                            if curr < xpmin:
                                logger.warning(f"X-Plane version {curr} detected, minimal version is {xpmin}")
                                logger.warning("Some features in Cockpitdecks may not work properly")
                            elif curr > xpmax:
                                logger.warning(f"X-Plane version {curr} detected, maximal version is {xpmax}")
                                logger.warning("Some features in Cockpitdecks may not work properly")
                            else:
                                logger.info(f"X-Plane version requirements {xpmin}<= {curr} <={xpmax} satisfied")
                        logger.debug("..connected, starting websocket listener..")
                        self.start()
                        logger.info("..websocket listener started..")
                    else:
                        if self.ws_event is not None and not self.ws_event.is_set():
                            number_of_timeouts = number_of_timeouts + 1
                            if number_of_timeouts <= MAX_TIMEOUT_COUNT:  # attemps to reconnect
                                logger.info(f"timeout received ({number_of_timeouts}/{MAX_TIMEOUT_COUNT})")  # , exc_info=True
                            if number_of_timeouts >= MAX_TIMEOUT_COUNT:  # attemps to reconnect
                                logger.warning("too many times out, websocket listener terminated")  # ignore
                                self.ws_event.set()

                        if number_of_timeouts >= MAX_TIMEOUT_COUNT and to_count % WARN_FREQ == 0:
                            logger.error(f"..X-Plane instance not found on local network.. ({datetime.now().strftime('%H:%M:%S')})")
                        to_count = to_count + 1
                except:
                    logger.error(f"..X-Plane instance not found on local network.. ({datetime.now().strftime('%H:%M:%S')})", exc_info=True)
                # If still no connection (above attempt failed)
                # we wait before trying again
                if not self.connected:
                    self.dynamic_timeout = 1
                    self.should_not_connect.wait(self.dynamic_timeout)
                    logger.debug("..no connection. trying to connect..")
            else:
                # Connection is OK, we wait before checking again
                self.should_not_connect.wait(RECONNECT_TIMEOUT)  # could be n * RECONNECT_TIMEOUT
                logger.debug("..monitoring connection..")
        logger.debug("..ended connection monitor")

    # ################################
    # Interface
    #
    def connect(self, reload_cache: bool = False):
        """
        Starts connect loop.
        """
        self._beacon.connect()
        if self.should_not_connect is None:
            self.should_not_connect = threading.Event()
            self.connect_thread = threading.Thread(target=self.connect_loop, name=f"{type(self).__name__}::Connection Monitor")
            self.connect_thread.start()
            logger.debug("connection monitor started")
        else:
            if reload_cache:
                self.reload_caches()
            logger.debug("connection monitor connected")

    def disconnect(self):
        """
        End connect loop and disconnect
        """
        if self.should_not_connect is not None:
            logger.debug("disconnecting..")
            self._beacon.disconnect()
            self.disconnect_websocket()
            self.should_not_connect.set()
            wait = RECONNECT_TIMEOUT
            logger.debug(f"..asked to stop connection monitor.. (this may last {wait} secs.)")
            self.connect_thread.join(timeout=wait)
            if self.connect_thread.is_alive():
                logger.warning("..thread may hang..")
            self.should_not_connect = None
            logger.debug("..disconnected")
        else:
            if self.connected:
                self.disconnect_websocket()
                logger.debug("..connection monitor not running..disconnected")
            else:
                logger.debug("..not connected")

    # ################################
    # I/O
    #
    # Generic payload "send" function, unique
    def send(self, payload: dict, mapping: dict = {}) -> int:
        # Mapping is correspondance dataref_index=dataref_name
        if self.connected:
            if payload is not None and len(payload) > 0:
                req_id = self.next_req
                payload[REST_KW.REQID.value] = req_id
                self._requests[req_id] = None  # may be should remember timestamp, etc. if necessary, create Request class.
                self.ws.send(json.dumps(payload))
                webapi_logger.info(f">>SENT {payload}")
                if len(mapping) > 0:
                    maps = [f"{k}={v}" for k, v in mapping.items()]
                    webapi_logger.info(f">> MAP {', '.join(maps)}")
                return req_id
            else:
                logger.warning("no payload")
        logger.warning("not connected")
        return -1

    # Dataref operations
    #
    # Note: It is not possible get the the value of a dataref just once
    # through web service. No get_dataref_value().
    #
    def set_dataref_value(self, path, value) -> int:
        def split_dataref_path(path):
            name = path
            index = -1
            split = "[" in path and "]" in path
            if split:  # sim/some/values[4]
                name = path[: path.find("[")]
                index = int(path[path.find("[") + 1 : path.find("]")])  # 4
            meta = self.get_dataref_meta_by_name(name)
            return split, meta, name, index

        if value is None:
            logger.warning(f"dataref {path} has no value to set")
            return -1
        split, meta, name, index = split_dataref_path(path)
        if meta is None:
            logger.warning(f"dataref {path} not found in X-Plane datarefs database")
            return -1
        payload = {
            REST_KW.TYPE.value: "dataref_set_values",
            REST_KW.PARAMS.value: {REST_KW.DATAREFS.value: [{REST_KW.IDENT.value: meta.ident, REST_KW.VALUE.value: value}]},
        }
        mapping = {meta.ident: meta.name}
        if split:
            payload[REST_KW.PARAMS.value][REST_KW.DATAREFS.value][0][REST_KW.INDEX.value] = index
        return self.send(payload, mapping)

    def register_bulk_dataref_value_event(self, datarefs, on: bool = True) -> bool:
        drefs = []
        for dataref in datarefs.values():
            if type(dataref) is list:
                meta = self.get_dataref_meta_by_id(dataref[0].ident)  # we modify the global source info, not the local copy in the Dataref()
                webapi_logger.info(f"INDICES bef: {dataref[0].ident} => {meta.indices}")
                meta.save_indices()  # indices of "current" requests
                ilist = []
                otext = "on "
                for d1 in dataref:
                    ilist.append(d1.index)
                    if on:
                        meta.append_index(d1.index)
                    else:
                        otext = "off"
                        meta.remove_index(d1.index)
                    meta._last_req_number = self.req_number  # not 100% correct, but sufficient
                drefs.append({REST_KW.IDENT.value: dataref[0].ident, REST_KW.INDEX.value: ilist})
                webapi_logger.info(f"INDICES {otext}: {dataref[0].ident} => {ilist}")
                webapi_logger.info(f"INDICES aft: {dataref[0].ident} => {meta.indices}")
            else:
                if dataref.is_array:
                    logger.debug(f"dataref {dataref.name}: collecting whole array")
                drefs.append({REST_KW.IDENT.value: dataref.ident})
        if len(datarefs) > 0:
            mapping = {}
            for d in datarefs.values():
                if type(d) is list:
                    for d1 in d:
                        mapping[d1.ident] = d1.name
                else:
                    mapping[d.ident] = d.name
            action = "dataref_subscribe_values" if on else "dataref_unsubscribe_values"
            err = self.send({REST_KW.TYPE.value: action, REST_KW.PARAMS.value: {REST_KW.DATAREFS.value: drefs}}, mapping)
            return err != -1
        if on:
            action = "register" if on else "unregister"
            logger.warning(f"no bulk datarefs to {action}")
        return False

    # Command operations
    #
    def register_command_is_active_event(self, path: str, on: bool = True) -> int:
        cmdref = self.get_command_meta_by_name(path)
        if cmdref is not None:
            mapping = {cmdref.ident: cmdref.name}
            action = "command_subscribe_is_active" if on else "command_unsubscribe_is_active"
            return self.send({REST_KW.TYPE.value: action, REST_KW.PARAMS.value: {REST_KW.COMMANDS.value: [{REST_KW.IDENT.value: cmdref.ident}]}}, mapping)
        logger.warning(f"command {path} not found in X-Plane commands database")
        return -1

    def register_bulk_command_is_active_event(self, paths, on: bool = True) -> int:
        cmds = []
        mapping = {}
        for path in paths:
            cmdref = self.get_command_meta_by_name(path=path)
            if cmdref is None:
                logger.warning(f"command {path} not found in X-Plane commands database")
                continue
            cmds.append({REST_KW.IDENT.value: cmdref.ident})
            mapping[cmdref.ident] = cmdref.name

        if len(cmds) > 0:
            action = "command_subscribe_is_active" if on else "command_unsubscribe_is_active"
            return self.send({REST_KW.TYPE.value: action, REST_KW.PARAMS.value: {REST_KW.COMMANDS.value: cmds}}, mapping)
        if on:
            action = "register" if on else "unregister"
            logger.warning(f"no bulk command active to {action}")
        return -1

    def set_command_is_active_with_duration(self, path: str, duration: float = 0.0) -> int:
        cmdref = self.get_command_meta_by_name(path)
        if cmdref is not None:
            return self.send(
                {
                    REST_KW.TYPE.value: "command_set_is_active",
                    REST_KW.PARAMS.value: {
                        REST_KW.COMMANDS.value: [{REST_KW.IDENT.value: cmdref.ident, REST_KW.ISACTIVE.value: True, REST_KW.DURATION.value: duration}]
                    },
                }
            )
        logger.warning(f"command {path} not found in X-Plane commands database")
        return -1

    def set_command_is_active_without_duration(self, path: str, active: bool) -> int:
        cmdref = self.get_command_meta_by_name(path)
        if cmdref is not None:
            return self.send(
                {
                    REST_KW.TYPE.value: "command_set_is_active",
                    REST_KW.PARAMS.value: {REST_KW.COMMANDS.value: [{REST_KW.IDENT.value: cmdref.ident, REST_KW.ISACTIVE.value: active}]},
                }
            )
        logger.warning(f"command {path} not found in X-Plane commands database")
        return -1

    def set_command_is_active_true_without_duration(self, path) -> int:
        return self.set_command_is_active_without_duration(path=path, active=True)

    def set_command_is_active_false_without_duration(self, path) -> int:
        return self.set_command_is_active_without_duration(path=path, active=False)

    # ################################
    # Start/Run/Stop
    #
    def ws_receiver(self):
        """Read and decode websocket messages and enqueue events"""

        def dref_round(local_path: str, local_value):
            local_r = self.get_rounding(simulator_variable_name=local_path)
            local_v = round(local_value, local_r) if local_r is not None and local_value is not None else local_value
            return 0.0 if local_v < 0.0 and local_v > -0.001 else local_v

        def dref_round_arr(local_path: str, local_value):
            local_r = self.get_rounding(simulator_variable_name=local_path)
            if local_r is not None:
                return [round(l, local_r) for l in local_value]
            return local_value

        logger.debug("starting websocket listener..")
        RECEIVE_TIMEOUT = 1  # when not connected, checks often
        total_reads = 0
        to_count = 0
        TO_COUNT_DEBUG = 10
        TO_COUNT_INFO = 50
        start_time = datetime.now()
        last_read_ts = start_time
        total_read_time = 0.0
        while not self.ws_event.is_set():
            try:
                message = self.ws.receive(timeout=RECEIVE_TIMEOUT)
                if message is None:
                    to_count = to_count + 1
                    if to_count % TO_COUNT_INFO == 0:
                        logger.info("waiting for data from simulator..")  # at {datetime.now()}")
                    elif to_count % TO_COUNT_DEBUG == 0:
                        logger.debug("waiting for data from simulator..")  # at {datetime.now()}")
                    continue

                now = datetime.now()
                if total_reads == 0:
                    logger.debug(f"..first message at {now} ({round((now - start_time).seconds, 2)} secs.)")
                    RECEIVE_TIMEOUT = 5  # when connected, check less often, message will arrive

                total_reads = total_reads + 1
                delta = now - last_read_ts
                total_read_time = total_read_time + delta.microseconds / 1000000
                last_read_ts = now

                # Decode response
                data = {}
                resp_type = ""
                try:
                    data = json.loads(message)
                    resp_type = data[REST_KW.TYPE.value]
                    #
                    #
                    if resp_type == REST_RESPONSE.RESULT.value:

                        webapi_logger.info(f"<<RCV  {data}")
                        req_id = data.get(REST_KW.REQID.value)
                        if req_id is not None:
                            self._requests[req_id] = data[REST_KW.SUCCESS.value]
                        if not data[REST_KW.SUCCESS.value]:
                            errmsg = REST_KW.SUCCESS.value if data[REST_KW.SUCCESS.value] else "failed"
                            errmsg = errmsg + " " + data.get("error_message")
                            errmsg = errmsg + " (" + data.get("error_code") + ")"
                            logger.warning(f"req. {req_id}: {errmsg}")
                        else:
                            logger.debug(f"req. {req_id}: {REST_KW.SUCCESS.value if data[REST_KW.SUCCESS.value] else 'failed'}")
                    #
                    #
                    elif resp_type == REST_RESPONSE.COMMAND_ACTIVE.value:

                        if REST_KW.DATA.value not in data:
                            logger.warning(f"no data: {data}")
                            continue

                        for ident, value in data[REST_KW.DATA.value].items():
                            meta = self.get_command_meta_by_id(int(ident))
                            if meta is not None:
                                webapi_logger.info(f"CMD : {meta.name}={value}")
                                e = CommandActiveEvent(sim=self, command=meta.name, is_active=value, cascade=True)
                            else:
                                logger.warning(f"no command for id={self.all_commands.equiv(ident=int(ident))}")
                    #
                    #
                    elif resp_type == REST_RESPONSE.DATAREF_UPDATE.value:

                        if REST_KW.DATA.value not in data:
                            logger.warning(f"no data: {data}")
                            continue

                        for ident, value in data[REST_KW.DATA.value].items():
                            ident = int(ident)
                            dataref = self._dataref_by_id.get(ident)
                            if dataref is None:
                                logger.debug(
                                    f"no dataref for id={self.all_datarefs.equiv(ident=int(ident))} (this may be a previously requested dataref arriving late..., safely ignore)"
                                )
                                continue

                            if type(dataref) is list:
                                #
                                # 1. One or more values from a dataref array (but not all values)
                                if type(value) is not list:
                                    logger.warning(f"dataref array {self.all_datarefs.equiv(ident=ident)} value is not a list ({value}, {type(value)})")
                                    continue
                                meta = dataref[0].meta
                                if meta is None:
                                    logger.warning(f"dataref array {self.all_datarefs.equiv(ident=ident)} meta data not found")
                                    continue
                                current_indices = meta.indices
                                if len(value) != len(current_indices):
                                    logger.warning(
                                        f"dataref array {self.all_datarefs.equiv(ident=ident)}: size mismatch ({len(value)} vs {len(current_indices)})"
                                    )
                                    logger.warning(f"dataref array {self.all_datarefs.equiv(ident=ident)}: value: {value}, indices: {current_indices})")
                                    # So! since we totally missed this set of data, we ask for the set again to refresh the data:
                                    # err = self.send({REST_KW.TYPE.value: "dataref_subscribe_values", REST_KW.PARAMS.value: {REST_KW.DATAREFS.value: meta.indices}}, {})
                                    last_indices = meta.last_indices()
                                    if len(value) != len(last_indices):
                                        logger.warning("no attempt with previously requested indices, no match")
                                        continue
                                    else:
                                        logger.warning("attempt with previously requested indices (we have a match)..")
                                        logger.warning(f"dataref array: current value: {value}, previous indices: {last_indices})")
                                        current_indices = last_indices
                                for idx, v1 in zip(current_indices, value):
                                    d1 = f"{meta.name}[{idx}]"
                                    print(f"{d1}={v1}")
                                # alternative:
                                # for d in dataref:
                                #     parsed_value = d.parse_raw_value(value)
                                #     print(f"{d.name}={parsed_value}")
                            else:
                                #
                                # 2. Scalar value
                                parsed_value = dataref.parse_raw_value(value)
                                print(f"{dataref.name}={parsed_value}")
                    #
                    #
                    else:
                        logger.warning(f"invalid response type {resp_type}: {data}")

                except:
                    logger.warning(f"decode data {data} failed", exc_info=True)

            except ConnectionClosed:
                logger.warning("websocket connection closed")
                self.ws = None
                self.ws_event.set()

            except:
                logger.error("ws_receiver: other error", exc_info=True)

        if self.ws is not None:  # in case we did not receive a ConnectionClosed event
            self.ws.close()
            self.ws = None

        logger.info("..websocket listener terminated")

    def start(self):
        if not self.connected:
            logger.warning("not connected. cannot not start.")
            return

        if self.ws_event.is_set():  # Thread for X-Plane datarefs
            self.ws_event.clear()
            self.ws_thread = threading.Thread(target=self.ws_receiver, name="XPlane::WebSocket Listener")
            self.ws_thread.start()
            logger.info("websocket listener started")
        else:
            logger.info("websocket listener already running.")

        # When restarted after network failure, should clean all datarefs
        # then reload datarefs from current page of each deck
        self.reload_caches()
        self.rebuild_dataref_ids()
        logger.info(f"{type(self).__name__} started")

    def stop(self):
        if not self.ws_event.is_set():
            if self.all_datarefs is not None:
                self.all_datarefs.save("datarefs.json")
            if self.all_commands is not None:
                self.all_commands.save("commands.json")
            self.ws_event.set()
            if self.ws_thread is not None and self.ws_thread.is_alive():
                logger.debug("stopping websocket listener..")
                wait = RECEIVE_TIMEOUT
                logger.debug(f"..asked to stop websocket listener (this may last {wait} secs. for timeout)..")
                self.ws_thread.join(wait)
                if self.ws_thread.is_alive():
                    logger.warning("..thread may hang in ws.receive()..")
                logger.debug("..websocket listener stopped")
        else:
            logger.debug("websocket listener not running")

    def reset_connection(self):
        self.stop()
        self.disconnect()
        self.connect()
        self.start()

    def terminate(self):
        logger.debug(f"currently {'not ' if self.ws_event is None else ''}running. terminating..")
        logger.info("terminating..")
        # sends instructions to stop sending values/events
        # logger.info("..request to stop sending value updates and events..")
        # self.remove_all_simulator_variables_to_monitor()
        # self.remove_all_simulator_events_to_monitor()
        # stop receiving events from similator (websocket)
        logger.info("..stopping websocket listener..")
        self.stop()
        # cleanup/reset monitored variables or events
        # logger.info("..deleting references to datarefs..")
        # self.cleanup()
        logger.info("..disconnecting from simulator..")
        self.disconnect()
        logger.info("..terminated")

    def add_dataref_to_monitor(self, datarefs, reason: str | None = None):
        if not self.connected:
            logger.debug(f"would add {datarefs.keys()}")
            return
        if len(datarefs) == 0:
            logger.debug("no variable to add")
            return
        # Add those to monitor
        bulk = {}
        for d in datarefs.values():
            if not d.is_monitored:
                ident = d.ident
                if ident is not None:
                    if d.is_array and d.index is not None:
                        if ident not in bulk:
                            bulk[ident] = []
                        bulk[ident].append(d)
                    else:
                        bulk[ident] = d
            d.monitor()

        if len(bulk) > 0:
            self.register_bulk_dataref_value_event(datarefs=bulk, on=True)
            self._dataref_by_id = self._dataref_by_id | bulk
            dlist = []
            for d in bulk.values():
                if type(d) is list:
                    for d1 in d:
                        dlist.append(d1.name)
                else:
                    dlist.append(d.name)
            logger.debug(f">>>>> add_datarefs_to_monitor: {reason}: added {dlist}")
        else:
            logger.debug("no dataref to add")

    def remove_datarefs_to_monitor(self, datarefs: dict, reason: str | None = None):
        if not self.connected and len(self.simulator_variable_to_monitor) > 0:
            logger.debug(f"would remove {datarefs.keys()}/{self._max_datarefs_monitored}")
            return
        if len(datarefs) == 0:
            logger.debug("no variable to remove")
            return
        # Add those to monitor
        bulk = {}
        for d in datarefs.values():
            if d.is_monitored:
                if not d.unmonitor():  # will be decreased by 1 in super().remove_simulator_variable_to_monitor()
                    ident = d.ident
                    if ident is not None:
                        if d.is_array and d.index is not None:
                            if ident not in bulk:
                                bulk[ident] = []
                            bulk[ident].append(d)
                        else:
                            bulk[ident] = d
                else:
                    logger.debug(f"{d.name} monitored {d.monitored_count} times, not removed")
            else:
                logger.debug(f"no need to remove {d.name}, not monitored")

        if len(bulk) > 0:
            self.register_bulk_dataref_value_event(datarefs=bulk, on=False)
            for i in bulk.keys():
                if i in self._dataref_by_id:
                    del self._dataref_by_id[i]
                else:
                    logger.warning(f"no dataref for id={self.all_datarefs.equiv(ident=i)}")
            dlist = []
            for d in bulk.values():
                if type(d) is list:
                    for d1 in d:
                        dlist.append(d1.name)
                else:
                    dlist.append(d.name)
            logger.debug(f">>>>> remove_datarefs_to_monitor: {reason}: removed {dlist}")
        else:
            logger.debug("no variable to remove")

    def wait_connection(self):
        logger.debug("connecting..")
        while not ws.connected:
            logger.debug("..waiting for connection..")
            time.sleep(1)
        logger.debug("..connected")


if __name__ == "__main__":
    fdr = FDR()
    try:
        ws = XPlaneWebSocket(host="192.168.1.140", port=8080)
        ws.connect()
        ws.start()
        fdr = FDR()
        datarefs = {}
        for d in fdr.get_variables():
            datarefs[d] = Dataref(path=d, api=ws)
        ws.wait_connection()
        ws.add_dataref_to_monitor(datarefs=datarefs)
    except KeyboardInterrupt:
        fdr.terminate()
        ws.terminate()
