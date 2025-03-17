import json
import threading
import logging
import base64

from simple_websocket import Client, ConnectionClosed

from api import Dataref, Command, Cache, API, REST_KW
from mcdu import MCDU


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# logger.setLevel(logging.INFO)

INDICES = "indices"

class ReqNumber:
    def __init__(self) -> None:
        self.req_number = 0

    def next(self) -> int:
        self.req_number = self.req_number + 1
        return self.req_number


class XPWebSocket:

    def __init__(self, host: str, port: int, callback) -> None:
        self.curr_reqnr = ReqNumber()
        self.run = threading.Event()
        self.receiver_thread = threading.Thread(target=self.receiver)
        self.api = API(host="192.168.1.140", port=8080)
        self.api.set_api()
        self.ws = Client.connect(self.api.url.replace("http:", "ws:"))
        self.all_datarefs = Cache(self.api)
        self.all_datarefs.load("/datarefs")
        self.all_commands = {}
        if self.api.version == "v2":
            self.all_commands = Cache(self.api)
            self.all_commands.load("/commands")
        self.callback = callback
        self.start()

    def reload_caches(self):
        self.all_datarefs = Cache(self.api)
        self.all_datarefs.load("/datarefs")
        if self.api.version == "v2":
            self.all_commands = Cache(self.api)
            self.all_commands.load("/commands")

    def receiver(self):
        try:
            logger.debug("started")
            while not self.run.is_set():
                try:
                    response = self.ws.receive(timeout=2)
                    if response is not None:
                        message = json.loads(response)
                        resp_type = message[REST_KW.TYPE.value]
                        logger.debug(f"received {resp_type}")
                        if resp_type == "dataref_update_values":
                            for didx, value in message[REST_KW.DATA.value].items():
                                dref = self.all_datarefs.get_by_id(int(didx))
                                if dref is not None:
                                    d = dref.name

                                    if dref.value_type is not None and dref.value_type in ["int_array", "float_array"]:

                                        # Arrays
                                        # Whole array
                                        if len(dref[INDICES]) == 0:
                                            v = value
                                            dref._value = v
                                            logger.debug(f"DREF WHOLE ARRAY: {d} = {v}")
                                            continue

                                        # Single array element
                                        if INDICES not in dref or len(value) != len(dref[INDICES]):
                                            logger.warning(f"dataref array {d} size mismatch ({len(value)}/{len(dref[INDICES])})")
                                            logger.warning(f"dataref array {d}: value: {value}, indices: {dref[INDICES]})")
                                        for v1, idx in zip(value, dref[INDICES]):
                                            d1 = f"{d}[{idx}]"
                                            v = v1
                                            dref._value = v
                                            logger.debug(f"DREF ARRAY: {d}[{idx}] = {v}")

                                    else:
                                        # Scalar values
                                        v = value
                                        # String
                                        if (
                                            dref.value_type is not None
                                            and dref.value_type == "data"
                                            and type(value) in [bytes, str]
                                        ):  # data = string
                                            v = base64.b64decode(value).decode("ascii").replace("\u0000", "")
                                        # Other than string
                                        elif type(v) in [int, float]:
                                            v = value
                                        dref._value = v
                                        logger.debug(f"DREF: {d} = {v}")

                                    if self.callback is not None:
                                        # print(">> callback", dref)
                                        self.callback(dref)

                                else:
                                    logger.warning(f"dataref {didx} not found")



                except:
                    logger.debug("no message", exc_info=True)

        except (EOFError, ConnectionClosed):
            self.ws.close()
            logger.warning("closed")

    def parse(self, data: dict) -> dict:
        ty = data[REST_KW.TYPE.value]
        if ty == "result":
            if not data[REST_KW.SUCCESS.value]:
                logger.warning(f"req. {data[REST_KW.REQID.value]}: {REST_KW.SUCCESS.value if data[REST_KW.SUCCESS.value] else 'failed'}")
            else:
                logger.debug(f"req. {data[REST_KW.REQID.value]}: {REST_KW.SUCCESS.value if data[REST_KW.SUCCESS.value] else 'failed'}")
            return None

        return data

    def start(self):
        self.receiver_thread.start()

    def stop(self):
        self.run.set()

    def send(self, payload: dict) -> int:
        req_id = self.curr_reqnr.next()
        payload["req_id"] = req_id
        self.ws.send(json.dumps(payload))
        logger.debug(f"sent {payload}")
        return req_id

    def register_dataref_value_event(self, path, on: bool = True) -> int:
        dref = self.all_datarefs.get_by_name(name=path)
        action = "dataref_subscribe_values" if on else "dataref_unsubscribe_values"
        return self.send({"type": action, "params": {"datarefs": [{"id": dref.ident}]}})

    def split_dataref_path(self, path):
        name = path
        index = -1
        split = "[" in path and "]" in path
        if split:  # sim/some/values[4]
            name = path[: path.find("[")]
            index = int(path[path.find("[") + 1 : path.find("]")])  # 4
        dref = self.all_datarefs.get_by_name(name)
        return split, dref, name, index

    def append_index(self, dref, i):
        # see https://stackoverflow.com/questions/13694034/is-a-python-list-guaranteed-to-have-its-elements-stay-in-the-order-they-are-inse
        if INDICES not in dref:
            dref[INDICES] = list()  # set() do not preserve order of insertion
        if i not in dref[INDICES]:
            dref[INDICES].append(i)
        # logger.info(f"REG {dref[REST_KW.NAME.value]}: {i} ({dref[INDICES]})")

    def remove_index(self, dref, i):
        if INDICES not in dref:
            logger.warning(f"{dref} has no index list")
            return
        dref[INDICES].remove(i)
        # logger.info(f"DEREG {dref[REST_KW.NAME.value]}: {i} ({dref[INDICES]})")

    def register_bulk_dataref_value_event(self, paths, on: bool = True) -> int:
        drefs = []
        for path in paths:
            split, dref, name, index = self.split_dataref_path(path)
            if dref is None:
                logger.warning(f"dataref {path} not found in X-Plane datarefs database")
                continue
            if split:
                drefs.append({REST_KW.IDENT.value: dref.ident, REST_KW.INDEX.value: index})
                if on:
                    self.append_index(dref, index)
                else:
                    self.remove_index(dref, index)
            else:
                drefs.append({REST_KW.IDENT.value: dref.ident})

        if len(drefs) > 0:
            action = "dataref_subscribe_values" if on else "dataref_unsubscribe_values"
            return self.send({REST_KW.TYPE.value: action, REST_KW.PARAMS.value: {REST_KW.DATAREFS.value: drefs}})
        action = "register" if on else "unregister"
        logger.warning(f"no bulk datarefs to {action}")
        return -1

    def register_command_event(self, path, on: bool = True) -> int:
        cmd = Command(path=path, cache=self.all_commands)
        action = "command_subscribe_is_active" if on else "command_unsubscribe_is_active"
        return self.send({"type": action, "params": {"commands": [{"id": cmd.ident}]}})


if __name__ == "__main__":

    mcdu = MCDU()
    ws = XPWebSocket(host="192.168.1.140", port=8080, callback=mcdu.variable_changed)
    data = mcdu.get_variables()
    ws.register_bulk_dataref_value_event(paths=data, on=True)
