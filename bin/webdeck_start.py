import json
import os
import urllib.parse
import base64
import socket
import struct
import threading
import logging

from flask import Flask, render_template, request, jsonify
from simple_websocket import Server, ConnectionClosed

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

WS = "_ws"
BUFFER_SIZE = 4096
SOCKET_TIMEOUT = 5


class WebReceiver:

    def __init__(self) -> None:
        self.all_decks = {}
        self.vd_ws_conn = {}

        # Address and port of Flask communication channel
        self.socket = None
        self.address = "127.0.0.1"
        self.port = 7699

        # Address and port of Cockpitdecks to send interactions
        self.cd_address = "127.0.0.1"
        self.cd_port = 7700

        # Thread to listen to Cockpitdecks image proxy
        self.rcv_event = None
        self.rcv_thread = None

        self.init()

    def init(self):
        with open("vdecks.json", "r") as fp:
            self.all_decks = json.load(fp)

    def register_deck(self, deck, websocket):
        if deck not in self.vd_ws_conn:
            self.vd_ws_conn[deck] = []
        self.vd_ws_conn[deck].append(websocket)

    def get_deck_description(self, deck):
        return self.all_decks.get(deck)

    def send_event(self, deck, key, event):
        # Send interaction event to Cockpitdecks virtual deck driver
        # Virtual deck driver transform into Event and enqueue for Cockpitdecks processing
        # Payload is key, pressed(0 or 1), and deck name (bytes of UTF-8 string)
        content = bytes(deck, "utf-8")
        pressed = 1 if event == "pressed" else 0
        code = 0
        payload = struct.pack(f"III{len(content)}s", code, key, pressed, content)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((self.cd_address, self.cd_port))
                s.sendall(payload)
        except:
            logger.warning(f"{deck}: problem sending event")

    def handle_event(self, data: bytes):
        # payload = struct.pack(f"IIIIII{len(content2)}s{len(content)}s", int(code), int(key), width, height, len(content2), len(content), content2, content)
        (code, key, w, h, deck_length, image_length), payload = struct.unpack("IIIIII", data[:24]), data[24:]
        deck = payload[:deck_length].decode("utf-8")
        image = payload[deck_length:]  # this is a stream of bytes that represent the file content as PNG image.
        if code != 0:
            self.handle_code(code)
            return
        response = {"code": 0, "deck": deck, "key": key, "image": base64.encodebytes(image).decode("ascii")}
        client_list = self.vd_ws_conn.get(deck)
        if client_list is not None:
            for ws in client_list:  # send to each instance of this deck connected to this websocket server
                ws.send(json.dumps(response))
                print(f"sent for {deck}")
        else:
            print(f"no client for {deck}")

    def receive_events(self):
        # Receives update events from Cockpitdecks
        while self.rcv_event is not None and not self.rcv_event.is_set():
            buff = bytes()
            try:
                print(f"accepting.. ({self.address}, {self.port})")
                conn, addr = self.socket.accept()
                with conn:
                    while True:
                        data = conn.recv(BUFFER_SIZE)
                        print("got data")
                        if not data:
                            break
                        buff = buff + data
                    self.handle_event(buff)
            except TimeoutError:
                print("..timed out")
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
            print(f"listening on ({self.address}, {self.port})")

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


# ##################################
# Flask Web Server (& WebSocket)
#
#
web_receiver = WebReceiver()
web_receiver.start()

app = Flask(__name__, template_folder=os.path.join("..", "cockpitdecks", "decks", "resources", "templates"))


@app.route("/")
def index():
    return render_template("index.html", virtual_decks=web_receiver.all_decks)


@app.route("/deck/<name>")
def deck(name: str):
    uname = urllib.parse.unquote(name)
    logger.debug(f"Starting deck {uname}")
    return render_template("deck.html", deck=web_receiver.get_deck_description(uname))


@app.route("/cockpit", websocket=True)
def cockpit():
    ws = Server.accept(request.environ)
    try:
        while True:
            data = ws.receive()
            print("received", data)
            logger.debug(data)
            data = json.loads(data)
            if data.get("code") == 1:
                deck = data.get("deck")
                web_receiver.register_deck(deck, ws)
                print("registerd new deck", deck)
            elif data.get("code") == 0:
                deck = data.get("deck")
                key = data.get("key")
                if type(key) is str:
                    print("invalid key", key)
                    key = 0
                web_receiver.send_event(deck, key, int(data.get("z")))
                print("event sent", deck, int(data.get("z")))

    except ConnectionClosed:
        pass

    # Start a thread to listen to socket
    # and forward to websocket

    return ""

# @app.route("/image/<deck>/<name>")
# def image(deck: str, name: str):
#     deck = urllib.parse.unquote(deck)
#     with open(name, "rb") as fp:
#         image = fp.read()
#     response = {"code": 0, "deck": deck, "image": base64.b64encode(image).decode("utf-8")}
#     vd[deck]["ws"].send(json.dumps(response))
#     return f"{name} ok"

app.run(host="0.0.0.0", port=7777)
