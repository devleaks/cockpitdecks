import json
import threading
import logging

from simple_websocket import Client, ConnectionClosed

from api import Dataref, Command, Cache, API

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Keywords
TYPE = "type"
REQID = "req_id"
SUCCESS = "success"


class ReqNumber:
    def __init__(self) -> None:
        self.req_number = 0

    def next(self) -> int:
        self.req_number = self.req_number + 1
        return self.req_number


class XPWebSocket:

    def __init__(self, host: str, port: int) -> None:
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
                    data = self.ws.receive(timeout=2)
                    if data is not None:
                        prnt = self.parse(json.loads(data))
                        if prnt is not None:
                            logger.debug(prnt)
                except:
                    logger.debug("no data", exc_info=True)

        except (EOFError, ConnectionClosed):
            self.ws.close()
            logger.warning("closed")

    def parse(self, data: dict) -> dict:
        ty = data[TYPE]
        if ty == "result":
            if not data[SUCCESS]:
                logger.warning(f"req. {data[REQID]}: {SUCCESS if data[SUCCESS] else 'failed'}")
            else:
                logger.debug(f"req. {data[REQID]}: {SUCCESS if data[SUCCESS] else 'failed'}")
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
        logger.debug("sent", payload)
        return req_id

    def register_dataref_value_event(self, path, on: bool = True) -> int:
        dref = Dataref(path=path, cache=self.all_datarefs)
        action = "dataref_subscribe_values" if on else "dataref_unsubscribe_values"
        return self.send({"type": action, "params": {"datarefs": [{"id": dref.ident}]}})

    def register_command_event(self, path, on: bool = True) -> int:
        cmd = Command(path=path, cache=self.all_commands)
        action = "command_subscribe_is_active" if on else "command_unsubscribe_is_active"
        return self.send({"type": action, "params": {"commands": [{"id": cmd.ident}]}})


if __name__ == "__main__":

    ws = XPWebSocket(host="192.168.1.140", port=8080)
    ws.register_dataref_value_event(path="sim/cockpit2/gauges/actuators/barometer_setting_in_hg_pilot")
    ws.register_command_event("sim/map/show_current")
