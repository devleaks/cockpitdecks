import json
import os
import sys
import urllib.parse
import base64
import socket
import struct
import threading
import logging

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))  # we assume we're in subdir "bin/"

from cockpitdecks import __NAME__, COCKPITDECKS_HOST, PROXY_HOST, APP_HOST

from flask import Flask, render_template, send_from_directory, request
from simple_websocket import Server, ConnectionClosed

FORMAT = "[%(asctime)s] %(levelname)s %(threadName)s %(filename)s:%(funcName)s:%(lineno)d: %(message)s"
logging.basicConfig(level=logging.INFO, format=FORMAT)

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


SOCKET_TIMEOUT = 5
BUFFER_SIZE = 4096


# ##################################
# Web Proxy between Cockpitdecks and websockets to web pages with decks
#
#
class CDProxy:

    def __init__(self) -> None:
        self.inited = False
        self._requested = False
        self.web_decks = {}
        self.defaults = {}
        self.vd_ws_conn = {}

        # Address and port of Flask communication channel
        self.socket = None
        self.address = PROXY_HOST[0]
        self.port = PROXY_HOST[1]

        # Address and port of Cockpitdecks to send interactions
        self.cd_address = COCKPITDECKS_HOST[0]
        self.cd_port = COCKPITDECKS_HOST[1]

        # Thread to listen to Cockpitdecks image proxy
        self.rcv_event = None
        self.rcv_thread = None

        self._err = []

        self.init()

    def init(self):
        if not self.inited:
            self.send_code(deck=__NAME__, code=3)  # request initialisation

    def err_clear(self):
        self._err = []

    def register_deck(self, deck: str, websocket):
        if deck not in self.vd_ws_conn:
            self.vd_ws_conn[deck] = []
            logger.debug(f"{deck}: new registration")
            self.send_code(deck, 1)
        self.vd_ws_conn[deck].append(websocket)
        logger.debug(f"{deck}: registration added ({len(self.vd_ws_conn[deck])})")

    def remove(self, websocket):
        # we unfortunately have to scan all decks to find the ws to remove
        #
        for deck in self.vd_ws_conn:
            remove = []
            for ws in deck:
                if ws == websocket:
                    remove.append(websocket)
            for ws in remove:
                deck.remove(ws)
        for deck in self.vd_ws_conn:
            if len(self.vd_ws_conn[deck]) == 0:
                self.send_code(deck, 2)

    def get_deck_description(self, deck: str) -> dict:
        return self.web_decks.get(deck)

    def send_code(self, deck: str, code: int) -> bool:
        deck_name = bytes(deck, "utf-8")
        payload = struct.pack(f"IIIII{len(deck_name)}s", code, 0, len(deck_name), 0, 0, deck_name)
        # print(">>>>> send_code", code, 0, len(deck_name), 0, 0, deck_name, "", "")
        # unpack in Cockpit.receive_event()
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((self.cd_address, self.cd_port))
                s.sendall(payload)
            return True
        except:
            logger.warning(f"{deck}: problem sending event to {(self.cd_address, self.cd_port)}", exc_info=True)
        return False

    def send_event(self, deck: str, key, event, data=None) -> bool:
        # Send interaction event to Cockpitdecks virtual deck driver
        # Virtual deck driver transform into Event and enqueue for Cockpitdecks processing
        # Payload is key, pressed(0 or 1), and deck name (bytes of UTF-8 string)
        code = 0
        deck_name = bytes(deck, "utf-8")
        key_name = bytes(str(key), "utf-8")
        data_bytes = bytes(json.dumps(data), "utf-8")
        payload = struct.pack(
            f"IIIII{len(deck_name)}s{len(key_name)}s{len(data_bytes)}s",
            code,
            event,
            len(deck_name),
            len(key_name),
            len(data_bytes),
            deck_name,
            key_name,
            data_bytes,
        )
        # print(">>>>> send_event", code, event, len(deck_name), len(key_name), deck, key, data)
        # unpack in Cockpit.receive_event()
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((self.cd_address, self.cd_port))
                s.sendall(payload)
            return True
        except:
            logger.warning(f"{deck}: problem sending event")
        return False

    def handle_code(self, deck: str, code: int, data: bytes):
        logger.debug(f"deck {deck} handling code {code}")
        self.err_clear()

        # print("<<<<< handle_code", code, deck)
        if deck == __NAME__ and code == 4:  # Cockpitdecks started, we request initialisation
            logger.info(f"Cockpitdecks started, requesting deck list..")
            self._requested = True
            self.send_code(deck=__NAME__, code=3)  # request initialisation
        if deck == __NAME__ and code == 5:  # Cockpitdecks started, we request initialisation
            logger.info(f"Cockpitdecks terminated")
            self.inited = False
            ##
        if deck == __NAME__ and code == 3:  # receive initialisation, install web decks
            datastr = data.decode("utf-8")
            config = json.loads(datastr)
            self.web_decks = config["webdecks"]
            self.defaults = config["virtual-deck-defaults"]
            # logger.debug(self.web_decks)
            self.inited = True
            if self._requested:
                self._requested = False
                logger.info(f".. got deck list")
            logger.info(f"inited: {(len(self.web_decks))} web decks received")
            # We notify all decks. that there is a new definition
            for deck in self.web_decks:
                response = {"code": 1, "deck": deck, "meta": {}}
                client_list = self.vd_ws_conn.get(deck)
                closed_ws = []
                if client_list is not None:
                    for ws in client_list:  # send to each instance of this deck connected to this websocket server
                        if self.is_closed(ws):
                            closed_ws.append(ws)
                            continue
                        ws.send(json.dumps(response))
                        logger.debug(f"sent for {deck}")
                    if len(closed_ws) > 0:
                        for ws in closed_ws:
                            client_list.remove(ws)
                else:
                    if deck not in self._err:
                        logger.warning(f"no client for {deck}")
                        self._err.append(deck)
            logger.info(f"inited: {(len(self.web_decks))}  decks notified")

    def is_closed(self, ws):
        return ws.__dict__.get("environ").get("werkzeug.socket").fileno() < 0  # there must be a better way to do this...

    def handle_event(self, data: bytes):
        # packed in Cockpit handle_code() (code!=0) or virtual deck _send_key_image_to_device() (code=0)
        # payload = struct.pack(f"IIII{len(key_name)}s{len(deck_name)}s{len(content)}s", int(code), len(deck_name), len(key_name), len(content), deck_name, key_name, content)
        (code, deck_length, key_length, image_length, meta_length), payload = struct.unpack("IIIII", data[:20]), data[20:]
        # print("<<--- received from Cockpitdecks", code, deck_length, key_length, image_length, meta_length)
        deck = payload[:deck_length].decode("utf-8")
        key = payload[deck_length : deck_length + key_length].decode("utf-8")
        image = payload[
            deck_length + key_length : deck_length + key_length + image_length
        ]  # this is a stream of bytes that represent the file content as PNG image.
        meta = json.loads(payload[deck_length + key_length + image_length :].decode("utf-8"))
        # print("<<--- received from Cockpitdecks", code, deck_length, key_length, image_length, meta_length, deck, key, "<content>", meta)
        if code != 0:
            self.handle_code(deck=deck, code=code, data=image)
            return
        response = {"code": 0, "deck": deck, "key": key, "image": base64.encodebytes(image).decode("ascii"), "meta": meta}
        client_list = self.vd_ws_conn.get(deck)
        closed_ws = []
        if client_list is not None:
            for ws in client_list:  # send to each instance of this deck connected to this websocket server
                if self.is_closed(ws):
                    closed_ws.append(ws)
                    continue
                ws.send(json.dumps(response))
                logger.debug(f"sent for {deck}")
            if len(closed_ws) > 0:
                for ws in closed_ws:
                    client_list.remove(ws)
        else:
            if deck not in self._err:
                logger.warning(f"no client for {deck}")
                self._err.append(deck)

    def receive_events(self):
        # Receives update events from Cockpitdecks
        while self.rcv_event is not None and not self.rcv_event.is_set():
            buff = bytes()
            try:
                logger.debug(f"accepting.. ({self.address}, {self.port})")
                conn, addr = self.socket.accept()
                with conn:
                    while True:
                        data = conn.recv(BUFFER_SIZE)
                        logger.debug("got event from Cockpitdecks")
                        if not data:
                            break
                        buff = buff + data
                    self.handle_event(buff)
            except TimeoutError:
                logger.debug("..timed out")
                # logger.debug(f"receive event", exc_info=True)
                pass
            except:
                logger.warning(f"receive events: abnormal exception", exc_info=True)

    def start(self):
        if self.socket is None:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.bind((self.address, self.port))
            self.socket.listen()
            self.socket.settimeout(SOCKET_TIMEOUT)
            logger.info(f"web deck proxy listening on ({self.address}, {self.port})")

        if self.rcv_event is None:  # Thread for X-Plane datarefs
            self.rcv_event = threading.Event()
            self.rcv_thread = threading.Thread(target=self.receive_events, name="CDProxy::receive_events")
            self.rcv_thread.start()
            logger.info(f"web deck proxy started")
        else:
            logger.info("web deck proxy already running")

    def stop(self):
        if self.rcv_event is not None:
            self.rcv_event.set()
            logger.debug("stopping web deck proxy..")
            wait = SOCKET_TIMEOUT
            logger.debug(f"..asked to stop web deck proxy (this may last {wait} secs. for accept to timeout)..")
            self.rcv_thread.join(wait)
            if self.rcv_thread.is_alive():
                logger.warning("..thread may hang in socket.accept()..")
            self.rcv_event = None
            logger.debug("..web deck proxy stopped")
        else:
            logger.debug("web deck proxy not running")


cdproxy = CDProxy()
cdproxy.start()


# ##################################
# Flask Web Server (& WebSocket)
#
# Serves decks and their assets.
# Proxy WebSockets to TCP Sockets
#
TEMPLATE_FOLDER = os.path.join("..", "cockpitdecks", "decks", "resources", "templates")
ASSET_FOLDER = os.path.join("..", "cockpitdecks", "decks", "resources", "assets")

app = Flask(__name__, template_folder=TEMPLATE_FOLDER)

app.logger.setLevel(logging.INFO)
# app.config['EXPLAIN_TEMPLATE_LOADING'] = True


@app.route("/")
def index():
    cdproxy.init()  # provoque deck request
    return render_template("index.j2", virtual_decks=cdproxy.web_decks)


@app.route("/favicon.ico")
def send_favicon():
    return send_from_directory(TEMPLATE_FOLDER, "favicon.ico")


@app.route("/assets/<path:path>")
def send_report(path):
    return send_from_directory(ASSET_FOLDER, path)


@app.route("/deck/<name>")
def deck(name: str):
    uname = urllib.parse.unquote(name)
    app.logger.debug(f"Starting deck {uname}")
    deck_desc = cdproxy.get_deck_description(uname)
    # Inject our contact address:
    if type(deck_desc) is dict:
        deck_desc["ws_url"] = f"ws://{APP_HOST[0]}:{APP_HOST[1]}/cockpit"
        deck_desc["presentation-default"] = cdproxy.defaults
    else:
        app.logger.debug(f"deck desc is not a dict {deck_desc}")
    return render_template("deck.j2", deck=deck_desc)


@app.route("/cockpit", websocket=True)  # How convenient...
def cockpit():
    ws = Server.accept(request.environ)
    try:
        while True:
            data = ws.receive()
            app.logger.debug(f"received {data}")
            data = json.loads(data)
            code = data.get("code")
            if code == 1:
                deck = data.get("deck")
                cdproxy.register_deck(deck, ws)
                app.logger.info(f"registered deck {deck}")
                cdproxy.send_code(deck, code)
                app.logger.debug(f"forwarded code deck={deck}, code={code}")
            elif code == 0:
                deck = data.get("deck")
                key = data.get("key")
                event = data.get("event")
                payload = data.get("data")
                cdproxy.send_event(deck=deck, key=key, event=event, data=payload)
                app.logger.debug(f"event sent deck={deck}, event={event} data={payload}")

    except ConnectionClosed:
        app.logger.debug(f"connection closed")
        cdproxy.remove(ws)
        app.logger.debug(f"client removed")

    return ""


app.run(host=APP_HOST[0], port=APP_HOST[1])
