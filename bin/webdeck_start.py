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
logger.setLevel(logging.INFO)


SOCKET_TIMEOUT = 5
BUFFER_SIZE = 4096

# ##################################
# Web Proxy between Cockpitdecks and websockets to web pages with decks
#
#
class CDProxy:

    def __init__(self) -> None:
        self.inited = False
        self.all_decks = {}
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

        self.init()

    def init(self):
        self.send_code(deck=__NAME__, code=3)  # request initialisation

    def ready(self):
        if self.inited:
            return True
        self.init()
        return False

    def register_deck(self, deck, websocket):
        if deck not in self.vd_ws_conn:
            self.vd_ws_conn[deck] = []
            logger.debug(f"{deck}: new registration")
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

    def get_deck_description(self, deck):
        return self.all_decks.get(deck)

    def send_code(self, deck, code) -> bool:
        # Send interaction event to Cockpitdecks virtual deck driver
        # Virtual deck driver transform into Event and enqueue for Cockpitdecks processing
        # Payload is key, pressed(0 or 1), and deck name (bytes of UTF-8 string)
        content = bytes(deck, "utf-8")
        payload = struct.pack(f"III{len(content)}s", code, 0, 0, content)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((self.cd_address, self.cd_port))
                s.sendall(payload)
            return True
        except:
            logger.warning(f"{deck}: problem sending event")
        return False

    def send_event(self, deck, key, event) -> bool:
        # Send interaction event to Cockpitdecks virtual deck driver
        # Virtual deck driver transform into Event and enqueue for Cockpitdecks processing
        # Payload is key, pressed(0 or 1), and deck name (bytes of UTF-8 string)
        content = bytes(deck, "utf-8")
        code = 0
        payload = struct.pack(f"III{len(content)}s", code, key, event, content)
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
        if deck == __NAME__ and code == 3:  # initialisation
            datastr = data.decode("utf-8")
            self.all_decks = json.loads(datastr)
            logger.debug(self.all_decks)
            self.inited = True
            logger.info(f"inited: {(len(self.all_decks))} web decks received")

    def is_closed(self, ws):
        return ws.__dict__.get("environ").get("werkzeug.socket").fileno() < 0  # need a better way to do this...

    def handle_event(self, data: bytes):
        # payload = struct.pack(f"IIIIII{len(content2)}s{len(content)}s", int(code), int(key), width, height, len(content2), len(content), content2, content)
        (code, key, w, h, deck_length, image_length), payload = struct.unpack("IIIIII", data[:24]), data[24:]
        deck = payload[:deck_length].decode("utf-8")
        image = payload[deck_length:]  # this is a stream of bytes that represent the file content as PNG image.
        if code != 0:
            self.handle_code(deck=deck, code=code, data=image)
            return
        response = {"code": 0, "deck": deck, "key": key, "image": base64.encodebytes(image).decode("ascii")}
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
            logger.warning(f"no client for {deck}")

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
                        logger.debug("got event from web deck")
                        if not data:
                            break
                        buff = buff + data
                    self.handle_event(buff)
            except TimeoutError:
                logger.debug("..timed out")
                pass
                # logger.debug(f"receive event", exc_info=True)
            except:
                logger.warning(f"receive events: abnormal exception", exc_info=True)

    def start(self):
        if self.socket is None:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.bind((self.address, self.port))
            self.socket.listen()
            self.socket.settimeout(SOCKET_TIMEOUT)
            logger.info(f"listening on ({self.address}, {self.port})")

        if self.rcv_event is None:  # Thread for X-Plane datarefs
            self.rcv_event = threading.Event()
            self.rcv_thread = threading.Thread(target=self.receive_events, name="VirtualDeck::event_listener")
            self.rcv_thread.start()
            logger.info(f"virtual deck listener started (port {self.port})")
        else:
            logger.info("virtual deck listener already running")

    def stop(self):
        if self.rcv_event is not None:
            self.rcv_event.set()
            logger.debug("stopping virtual deck listener..")
            wait = SOCKET_TIMEOUT
            logger.debug(f"..asked to stop virtual deck listener (this may last {wait} secs. for accept to timeout)..")
            self.rcv_thread.join(wait)
            if self.rcv_thread.is_alive():
                logger.warning("..thread may hang in socket.accept()..")
            self.rcv_event = None
            logger.debug("..virtual deck listener stopped")
        else:
            logger.debug("virtual deck listener not running")


cdproxy = CDProxy()
cdproxy.start()


# ##################################
# Flask Web Server (& WebSocket)
#
#
TEMPLATE_FOLDER = os.path.join("..", "cockpitdecks", "decks", "resources", "templates")

app = Flask(__name__, template_folder=TEMPLATE_FOLDER)

app.logger.setLevel(logging.INFO)

# app.config['EXPLAIN_TEMPLATE_LOADING'] = True

@app.route("/")
def index():
    dummy = cdproxy.ready()  # provoque deck request
    return render_template("index.j2", virtual_decks=cdproxy.all_decks)

@app.route('/favicon.ico')
def send_favicon():
    return send_from_directory(TEMPLATE_FOLDER, 'favicon.ico')

@app.route("/deck/<name>")
def deck(name: str):
    uname = urllib.parse.unquote(name)
    app.logger.debug(f"Starting deck {uname}")
    deck_desc = cdproxy.get_deck_description(uname)
    # Inject our contact address:
    deck_desc["ws_url"] = f"ws://{APP_HOST[0]}:{APP_HOST[1]}/cockpit"
    return render_template("deck.j2", deck=cdproxy.get_deck_description(uname))


@app.route("/cockpit", websocket=True)
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
                if type(key) is str:
                    app.logger.warning(f"invalid key '{key}'")
                    key = 0
                cdproxy.send_event(deck, key, int(data.get("z")))
                app.logger.debug(f"event sent deck={deck}, value={int(data.get('z'))}")

    except ConnectionClosed:
        app.logger.debug(f"connection closed")
        cdproxy.remove(ws)
        app.logger.debug(f"client removed")

    return ""

# @app.route("/image/<deck>/<name>")
# def image(deck: str, name: str):
#     deck = urllib.parse.unquote(deck)
#     with open(name, "rb") as fp:
#         image = fp.read()
#     response = {"code": 0, "deck": deck, "image": base64.b64encode(image).decode("utf-8")}
#     vd[deck]["ws"].send(json.dumps(response))
#     return f"{name} ok"

app.run(host=APP_HOST[0], port=APP_HOST[1])
