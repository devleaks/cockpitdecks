"""
Virtual deck user interface class
"""

import os
import threading
import socket
import struct
import logging
from typing import List

import pyglet
from pyglet.window import mouse

from PIL import Image

from cockpitdecks.constant import Config, CONFIG_KW, DECK_KW, CONFIG_FOLDER, CONFIG_FILE
from .virtualdeck import VirtualDeck
from .virtualdeckmanager import VirtualDeckManager

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


BUFFER_SIZE = 4096
SOCKET_TIMEOUT = 5


class VirtualDeckUI(VirtualDeck, pyglet.window.Window):

    def __init__(self, name: str, definition: dict, config: dict, cdip: list):

        VirtualDeck.__init__(self, name=name, definition=definition, config=config, cdip=cdip)
        pyglet.window.Window.__init__(self, self.keys_horiz * self.icon_width, self.keys_vert * self.icon_height)

        self.icons = [() for i in range(self.keys_horiz * self.keys_vert)]
        self.update_lock = threading.RLock()

        # Address and port of virtual deck
        self.socket = None

        self.rcv_event = None
        self.rcv_thread = None

        self.init()

    def __enter__(self):
        self.update_lock.acquire()

    def __exit__(self, type, value, traceback):
        self.update_lock.release()

    def init(self):
        # Creates black screen with proper icon spacing
        icon = Image.new("RGB", (self.icon_width, self.icon_height), "purple")
        for i in range(self.keys_horiz * self.keys_vert):
            x, y = self.get_xy(i)
            with self:
                self.icons[i] = (icon.tobytes(), x, y, icon.width, icon.height)

    # ######################################
    #
    def get_xy(self, key: int) -> tuple:
        y = self.icon_height * (self.keys_vert - 1 - int(key / self.keys_horiz))
        x = self.icon_width * (key % self.keys_horiz)
        return (x, y)

    def send_event(self, key, event):
        # Send interaction event to Cockpitdecks virtual deck driver
        # Virtual deck driver transform into Event and enqueue for Cockpitdecks processing
        # Payload is key, pressed(0 or 1), and deck name (bytes of UTF-8 string)
        content = bytes(self.name, "utf-8")
        pressed = 1 if event == "pressed" else 0
        payload = struct.pack(f"II{len(content)}s", key, pressed, content)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((self.cd_address, self.cd_port))
            s.sendall(payload)
            # logger.debug(f"sent {self.name}:{key} = {pressed}")

    def handle_event(self, data: bytes):
        (key, w, h, length), img = struct.unpack("IIII", data[:16]), data[16:]
        x, y = self.get_xy(key)
        # logger.debug(f"received {key}, {x}, {y}, {w}, {h}")
        with self:
            self.icons[key] = (img, x, y, w, h)

    def receive_events(self):
        # Receives update events from Cockpitdecks
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
        if self.socket is None:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.bind((self.address, self.port))
            self.socket.listen()
            self.socket.settimeout(SOCKET_TIMEOUT)

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

    # ######################################
    #
    def on_mouse_press(self, x, y, button, modifiers):
        if button == mouse.LEFT:
            h = int(x / self.icon_width)
            v = self.keys_vert - int(y / self.icon_height) - 1
            # print(f"The left mouse button was pressed at ({x},{y})")
            key = v * self.keys_horiz + h
            self.send_event(key, "pressed")

    def on_mouse_release(self, x, y, button, modifiers):
        if button == mouse.LEFT:
            h = int(x / self.icon_width)
            v = self.keys_vert - int(y / self.icon_height) - 1
            # print(f"The left mouse button was pressed at ({x},{y})")
            key = v * self.keys_horiz + h
            self.send_event(key, "released")

    def on_draw(self):
        self.clear()
        with self:
            [pyglet.image.ImageData(c[3], c[4], "RGB", c[0]).blit(c[1], c[2]) for c in self.icons]


class VirtualDeckManagerUI(VirtualDeckManager):

    @staticmethod
    def enumerate(acpath: str, cdip: list) -> List[VirtualDeck]:
        vdt = VirtualDeckManager.virtual_deck_types()
        vdt_names = [d.get(DECK_KW.TYPE.value) for d in vdt.values()]
        fn = os.path.join(acpath, CONFIG_FOLDER, CONFIG_FILE)
        config = Config(fn)
        decks = config.get(CONFIG_KW.DECKS.value)
        for deck in decks:
            dt = deck.get(CONFIG_KW.TYPE.value)
            if dt in vdt_names:
                name = deck.get(DECK_KW.NAME.value)
                VirtualDeckManager.virtual_decks[name] = VirtualDeckUI(name=name, definition=vdt.get(dt), config=deck, cdip=cdip)
        return VirtualDeckManager.virtual_decks

    @staticmethod
    def run():
        for name, deck in VirtualDeckManager.virtual_decks.items():
            logger.debug(f"starting virtual deck {name}..")
            deck.start()
            logger.debug(f"..started")
        VirtualDeckManager.event_loop = pyglet.app.EventLoop()
        VirtualDeckManager.event_loop.run(interval=0.5)
        logger.info(f"started all virtual decks")

    @staticmethod
    def terminate():
        VirtualDeckManager.event_loop.exit()
        for name, deck in VirtualDeckManager.virtual_decks.items():
            logger.debug(f"terminating virtual deck {name}..")
            deck.terminate()
            logger.debug(f"..terminated")
        logger.info(f"terminated all virtual decks")
