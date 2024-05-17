"""
Virtual deck user interface class
"""

import threading
import socket
import struct
import logging

from PIL import Image

import pyglet
from pyglet.window import mouse

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


DEVICE_MANUFACTURER = "Cockpitdecks"  # verbose descriptive
BUFFER_SIZE = 4096
SOCKET_TIMEOUT = 5


class VirtualDeck(pyglet.window.Window):
    DECK_NAME = "virtualdeck"

    def __init__(self, name: str, definition: dict, config: dict, cdip: list = ("127.0.0.1", 7700)):
        self.name: str = name
        self.virtual_deck_definition: dict = definition  # DeckType
        self.virtual_deck_config: dict = config  # Deck entry in deckconfig/config.yaml

        self.version = "0.0.1"
        self.inited = False
        self.running = False
        self.update_lock = threading.RLock()

        layout = self.virtual_deck_definition.get("layout", [3, 2, 128])

        self.hsize = layout[0]
        self.vsize = layout[1]
        self.icon_width = layout[2]
        self.icon_height = layout[2]
        self.icons = [() for i in range(self.hsize * self.vsize)]
        self.icons_lock = threading.RLock()

        if self.virtual_deck_definition.get("v", False):
            logger.info(f"new virtual deck {name}: {self.virtual_deck_definition}")

        # Address and port of virtual deck
        self.socket = None
        self.address = config.get("address", "127.0.0.1")
        self.port = config.get("port", 7701)
        self.cd_address = cdip[0]
        self.cd_port = cdip[1]

        self.rcv_event = None
        self.rcv_thread = None

        pyglet.window.Window.__init__(self, self.hsize * self.icon_width, self.vsize * self.icon_height)
        self.init()

    def __enter__(self):
        self.update_lock.acquire()

    def __exit__(self, type, value, traceback):
        self.update_lock.release()

    def deck_type(self):
        return VirtualDeck.DECK_TYPE

    def get_info(self):
        return {
            "version": self.version,
            "name": self.name,
            "config": self.virtual_deck_config,
        }

    def get_serial_number(self):
        return f"{self.address}:{self.port}"

    def is_visual(self):
        return True

    def key_image_format(self):
        return {
            "size": (self.icon_width, self.icon_height),
            "format": "",
            "flip": (False, False),
            "rotation": 0,
        }

    # #########################################
    #
    def get_xy(self, key: int) -> tuple:
        y = self.icon_height * (self.vsize - 1 - int(key / self.hsize))
        x = self.icon_width * (key % self.hsize)
        return (x, y)

    def init(self):
        icon = Image.new("RGB", (self.icon_width, self.icon_height), "purple")
        pimg = pyglet.image.ImageData(icon.width, icon.height, "RGB", icon.tobytes())
        for i in range(self.hsize * self.vsize):
            x, y = self.get_xy(i)
            with self.icons_lock:
                self.icons[i] = (pimg, x, y)

    # #########################################
    #
    def open(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((self.address, self.port))
        self.socket.listen()
        self.socket.settimeout(SOCKET_TIMEOUT)

    def close(self):
        pass

    def reset(self):
        pass

    def send_event(key, event):
        payload = struct.pack("II", key, 1 if event == "pressed" else 0)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((self.cd_address, self.cd_port))
            s.sendall(payload)

    def handle_event(self, data: bytes):
        (key, w, h, length), img = struct.unpack("IIII", data[:16]), data[16:]
        pimg = pyglet.image.ImageData(w, h, "RGB", img)
        x, y = get_xy(key)
        with self.icons_lock:
            self.icons[key] = (pimg, x, y)

    def receive_events():
        while self.rcv_event is not None and not self.rcv_event.is_set():
            buff = bytes()
            try:
                conn, addr = self.socket.accept()
                with conn:
                    while True:
                        data = conn.recv(BUFFER_SIZE)
                        if not data:
                            break
                        buff = buff + data
                    self.handle_event(buff)
            except TimeoutError:
                pass
                # logger.debug(f"receive event", exc_info=True)
            except:
                logger.warning(f"receive events: abnormal exception", exc_info=True)

    def start(self):
        if self.rcv_event is None:  # Thread for X-Plane datarefs
            self.rcv_event = threading.Event()
            self.rcv_thread = threading.Thread(target=self.receive_events, name="VirtualDeck::event_listener")
            self.rcv_thread.start()
            logger.info("virtual deck listener started")
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

        event_loop.exit()

    # #########################################
    #
    def on_mouse_press(self, x, y, button, modifiers):
        if button == mouse.LEFT:
            h = int(x / self.icon_width)
            v = self.vsize - int(y / self.icon_height) - 1
            # print(f"The left mouse button was pressed at ({x},{y})")
            key = v * self.hsize + h
            self.send_event(key, "pressed")

    def on_mouse_release(self, x, y, button, modifiers):
        if button == mouse.LEFT:
            h = int(x / self.icon_width)
            v = self.vsize - int(y / self.icon_height) - 1
            # print(f"The left mouse button was pressed at ({x},{y})")
            key = v * self.hsize + h
            self.send_event(key, "released")

    def on_draw(self):
        self.clear()
        c = self.icons
        with self.icons_lock:
            for i in range(self.hsize * self.vsize):
                c[i][0].blit(c[i][1], c[i][2])

    # #########################################
    #
    def test(self):
        pass
