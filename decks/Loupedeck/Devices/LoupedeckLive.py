"""
Main Loupedeck and LoupedeckLive classes.
"""
import glob
import io
import logging
import math
import serial
import sys
import threading
import time
from datetime import datetime
from queue import Queue

from PIL import Image
from ..ImageHelpers import PILHelper
from .Loupedeck import Loupedeck


from .constants import BIG_ENDIAN, WS_UPGRADE_HEADER, WS_UPGRADE_RESPONSE
from .constants import HEADERS, BUTTONS, HAPTIC, MAX_BRIGHTNESS, DISPLAYS, BUTTON_SIZES
from .. import __NAME__, __version__

logger = logging.getLogger("LoupedeckLive")
# logger.setLevel(logging.DEBUG)

MAX_TRANSACTIONS = 256
READING_TIMEOUT = 1     # seconds

def print_bytes(buff, begin:int = 18, end:int = 10):
    if buff is None:
        return None
    if len(buff) > 20:
        return f"{buff[0:begin]} ... {buff[-end:]}"
    return f"{buff}"

class LoupedeckLive(Loupedeck):


    def __init__(self, path:str, baudrate:int = 460800, timeout:int = READING_TIMEOUT, auto_start:bool = True):
        Loupedeck.__init__(self)

        self.path = path
        # See https://lucidar.me/en/serialib/most-used-baud-rates-table/ for baudrates
        self.connection = serial.Serial(port=path, baudrate=baudrate, timeout=timeout)
        logger.debug(f"__init__: connection opened")
        self.auto_start = auto_start
        self.reading_thread = None  # read
        self.process_thread = None  # messages
        self.reading_running = False
        self.process_running = False
        self.reading_finished = None
        self.process_finished = None
        self.get_serial = None
        self.touches = {}

        self.handlers = {
            HEADERS["BUTTON_PRESS"]: self.on_button,
            HEADERS["KNOB_ROTATE"]: self.on_rotate,
            HEADERS["SERIAL_IN"]: self.on_serial,
            HEADERS["TICK"]: self.on_tick,
            HEADERS["TOUCH"]: self.on_touch,
            HEADERS["TOUCH_END"]: self.on_touch_end,
            HEADERS["VERSION_IN"]: self.on_version
        }

        self.get_timeout = 1  # seconds

        self.init()

    def __del__(self):
        """
        Delete handler for the automatically closing the serial port.
        """
        try:
            if self.connection is not None:
                self.connection.close()
                logger.debug(f"__del__: connection closed")
        except:
            logger.error(f"__del__: exception:", exc_info=1)

    def open(self):
        pass

    def close(self):
        pass

    def is_visual(self):
        return True

    def key_image_format(self):
        return {
            'size': (90, 90),
            'format': "RGB565",
            'flip': None,
            'rotation': None,
        }

    def init(self):
        self.init_ws()
        if self.auto_start:
            self.start()
            self.info()  # this is more to test it is working...

    def init_ws(self):
        self.send(WS_UPGRADE_HEADER, raw=True)
        while True and not self.inited:
            raw_byte = self.connection.readline()
            logger.debug(raw_byte)
            if raw_byte == b"\r\n":  # got entire WS_UPGRADE_RESPONSE
                self.inited = True
        logger.debug(f"init_ws: inited")

    def info(self):
        if self.connection is not None:
            logger.info(f"{__NAME__}: {__version__}")
            logger.info(f"Device: {self.path}")
            self.get_serial = threading.Event()
            self.do_action(HEADERS["SERIAL_OUT"], track=True)
            self.do_action(HEADERS["VERSION_OUT"], track=True)
            if not self.get_serial.wait(10):
                logger.debug(f"info: could not get serial number")

            time.sleep(4 * self.get_timeout) # give time to get answers

    def id(self):
        return self.serial

    def key_layout(self):
        return (4, 3)

    def key_count(self):
        return 4 * 3

    def key_names(self, big: bool = False):
        if big:
            return ["left", "center", "right"]
        return ["left", "right"] + list(range(self.key_count()))

    # #########################################@
    # Serial Connection
    #
    def send(self, buff, raw = False):
        """
        Send buffer to device

        :param      buffer:  The buffer
        :type       buffer:  { type_description }
        """
        # logger.debug(f"send: to send: len={len(buff)}, raw={raw}, {print_bytes(buff)}")
        if not raw:
            prep = None
            if len(buff) > 0x80:
                prep = bytearray(14)
                prep[0] = 0x82
                prep[1] = 0xff
                buff_len = len(buff)
                prep[6:10] = buff_len.to_bytes(4, BIG_ENDIAN)
            else:
                prep = bytearray(6)
                prep[0] = 0x82
                prep[1] = 0x80 + len(buff)
                # prep.insert(2, buff_length.to_bytes(4, "big", False))
            # logger.debug(f"send: PREP: len={len(buff)}: {prep}")
            with self:
                self.connection.write(prep)
                self.connection.write(buff)
        else:
            with self:
                # logger.debug(f"send: buff: len={len(buff)}, {print_bytes(buff)}") # {buff},
                self.connection.write(buff)

    # #########################################@
    # Threading
    #
    def _read_serial(self):

        def magic_byte_length_parser(chunk, magicByte = 0x82):
            """
            Build local _buffer and scan it for complete messages.
            Enqueue messages (responses) when reconstituted.

            :param      chunk:      New chunk of data
            :type       chunk:      bytearray
            :param      magicByte:  The magic byte delimiter
            :type       magicByte:  byte
            """
            trace = False
            self._buffer = self._buffer + chunk
            position = self._buffer.find(magicByte)
            while position != -1:
                if trace:
                    logger.debug(f"magic: found {magicByte:x} at {position}")
                #  We need to at least be able to read the length byte
                if len(self._buffer) < position + 2:
                    if trace:
                        logger.debug(f"magic: not enough bytes ({len(self._buffer)}), waiting for more")
                    break
                nextLength = self._buffer[position + 1]
                #  Make sure we have enough bytes to meet self length
                expectedEnd = position + nextLength + 2
                if len(self._buffer) < expectedEnd:
                    if trace:
                        logger.debug(f"magic: not enough bytes for message ({len(self._buffer)}, exp={expectedEnd}), waiting for more")
                    break
                if trace:
                    logger.debug(f"magic: message from {position + 2} to {expectedEnd} (len={nextLength}), enqueueing ({self._messages.qsize()})")
                self._messages.put(self._buffer[position+2:expectedEnd])
                self._buffer = self._buffer[expectedEnd:]
                position = self._buffer.find(magicByte)

        logger.debug("_read_serial: starting")

        while self.reading_running:
            try:
                raw_byte = self.connection.read()
                if raw_byte != b"":
                    magic_byte_length_parser(raw_byte)
            except:
                logger.error(f"_read_serial: exception:", exc_info=1)
                logger.error(f"_read_serial: resuming")

        self.reading_running = False

        if self.reading_finished is not None:
            self.reading_finished.set()
            logger.debug(f"_read_serial: reading_finished set")
        else:
            logger.warning(f"_read_serial: no event set")

        logger.debug("_read_serial: terminated")


    def _process_messages(self):

        logger.debug("_process_messages: starting")

        while self.process_running:
            try:
                # logger.debug(f"_process_messages: dequeueing {self._messages.qsize()}")
                buff = self._messages.get(timeout=self.get_timeout)
                try:
                    # logger.debug(f"_process_messages: got {buff}")
                    header = int.from_bytes(buff[0:2], BIG_ENDIAN)
                    handler = self.handlers[header] if header in self.handlers else None
                    transaction_id = buff[2]
                    # logger.debug(f"_process_messages: transaction_id {transaction_id}, header {header:x}")
                    response = handler(buff[3:]) if handler is not None else buff
                    resolver = self.pendingTransactions[transaction_id] if transaction_id in self.pendingTransactions else None
                    if resolver is not None:
                        resolver(transaction_id, response)
                    else:
                        self.on_default_callback(transaction_id, response)
                except:
                    logger.error(f"_process_messages: exception:", exc_info=1)
                    logger.error(f"_process_messages: resuming")
            except: # timeout, continue while self.process_running==True
                pass
                # logger.debug(f"_process_messages: timed out, continuing")

        logger.debug("_process_messages: no longer running")

        self.process_running = False

        if self.process_finished is not None:
            self.process_finished.set()
            logger.debug(f"_process_messages: process_finished set")
        else:
            logger.warning(f"_process_messages: no event set")

        logger.debug("_process_messages: terminated")

    def start(self):
        if self.inited:
            if not self.reading_running:
                self.reading_thread = threading.Thread(target=self._read_serial)
                self.reading_thread.name = "LoupedeckLive::_read_serial"
                self.reading_running = True
                self.reading_thread.start()
                logger.debug("start: read started")
            else:
                logger.warning("start: read already running")
            if not self.process_running:
                self.process_thread = threading.Thread(target=self._process_messages)
                self.process_thread.name = "LoupedeckLive::_process_messages"
                self.process_running = True
                self.process_thread.start()
                logger.debug("start: process started")
            else:
                logger.warning("start: process already running")
            logger.debug("start: started")
        else:
            logger.warning("start: cannot start, not initialized")

    def stop(self):
        self.reading_finished = threading.Event()
        self.process_finished = threading.Event()
        self.reading_running = False
        self.process_running = False
        logger.info("stop: requested threads to stop, waiting..")
        # self._messages.put("__STOP__")
        if not self.reading_finished.wait(timeout=2*READING_TIMEOUT):   # sloppy but ok.
            logger.warning("stop: reader thread did not finish cleanly")
        if not self.process_finished.wait(timeout=2*self.get_timeout):
            logger.warning("stop: reader thread did not finish cleanly")

        logger.info("stop: ..stopped")

    # #########################################@
    # Callbacks
    #
    def do_action(self, action, data:bytearray = None, track:bool = False):
        if not self.inited:
            logger.warning(f"do_action: not started")
            return

        if data is not None and type(data) != bytearray and type(data) != bytes:
            data = data.to_bytes(1, BIG_ENDIAN)
            # logger.debug(f"do_action: converted data") #  '{data}'")

        # logger.debug(f"do_action: {action:04x}, {print_bytes(data)}")
        self.transaction_id = (self.transaction_id + 1) % MAX_TRANSACTIONS
        if self.transaction_id == 0:  # Skip transaction ID's of zero since the device seems to ignore them
             self.transaction_id = self.transaction_id + 1
        header = action.to_bytes(2, BIG_ENDIAN) + self.transaction_id.to_bytes(1, BIG_ENDIAN)
        # logger.debug(f"do_action: id={self.transaction_id}, header={header}, track={track}")
        payload = header
        if data is not None:
            # logger.debug(f"do_action: has data {payload} + '{print_bytes(data)}'")
            payload = payload + data

        if track:
            # logger.debug(f"do_action: tracking {self.transaction_id}")
            self.pendingTransactions[self.transaction_id] = action
        self.send(payload)

    def on_serial(self, serial:bytearray):
        self.serial = serial.decode("ascii").strip()
        if self.get_serial is not None:
            self.get_serial.set()
        # logger.info(f"Serial number: {self.serial}")

    def on_version(self, version:bytearray):
        self.version = f"{version[0]}.{version[1]}.{version[2]}"
        # logger.info(f"Version: {self.version}")

    def on_button(self, buff:bytearray):
        idx = BUTTONS[buff[0]]
        event = 'down' if buff[1] == 0x00 else 'up'
        if self.callback:
            self.callback(self, {
                "id": idx,
                "action": "push",
                "state": event,
                "ts": datetime.now().timestamp()
            })
        # logger.debug(f"on_button: {idx}, {event}")

    def on_rotate(self, buff:bytearray):
        idx = BUTTONS[buff[0]]
        event = "right" if buff[1] == 0x01 else "left"
        if self.callback:
            self.callback(self, {
                "id": idx,
                "action": "rotate",
                "state": event,
                "ts": datetime.now().timestamp()
            })
        # logger.debug(f"on_rotate: {idx}, {event}")

    def on_touch(self, buff:bytearray, event="touchmove"):
        x = int.from_bytes(buff[1:3], BIG_ENDIAN)
        y = int.from_bytes(buff[3:5], BIG_ENDIAN)
        idx = buff[5]

        # Determine target
        screen = "center"
        if x < 60:
            screen = "left"
        elif x > 420:
            screen = "right"

        key = None
        if screen == "center":
            column = math.floor((x - 60) / 90)
            row = math.floor(y / 90)
            key = row * 4 + column

        # Create touch
        touch = {
            "id": idx,
            "action": event,
            "screen": screen,
            "key": key,
            "x": x,
            "y": y,
            "ts": datetime.now().timestamp()
        }
        if event == "touchmove":
            if idx not in self.touches:
                touch["action"] = "touchstart"
                self.touches[idx] = touch
        else:
            del self.touches[idx]

        if self.callback:
            self.callback(self, touch)

        # logger.debug(f"on_touch: {event}, {buff}")

    def on_touch_end(self, buff:bytearray):
        self.on_touch(buff, event="touchend")

    def on_tick(self, buff:bytearray):
        logger.debug(f"on_tick: {buff}")

    def on_default_callback(self, transaction_id: int, response:bytearray):
        # logger.debug(f"on_default_callback: {transaction_id}: {response}")
        self.pendingTransactions[transaction_id] = None

    def set_callback(self, callback: callable):
        """
        This is the user's callback called when action
        occurred on the Loupedeck device

        :param      callback:  The callback
        :type       callback:  Function
        """
        # callback signature: callback(self:Loupedeck, message:dict)
        self.callback = callback

    # #########################################@
    # Loupedeck Functions
    #
    def set_brightness(self, brightness: int):
        """
        Set brightness, from 0 (dark) to 100.
        """
        brightness = math.floor(brightness/10)
        if brightness < 1:
            logger.warning(f"set_brightness: brightness set to 0")
            brightness = 0
        if brightness > MAX_BRIGHTNESS:
            brightness = MAX_BRIGHTNESS
        self.do_action(HEADERS["SET_BRIGHTNESS"], brightness.to_bytes(1, BIG_ENDIAN))
        # logger.debug(f"set_brightness: sent {brightness}")

    def set_button_color(self, name: str, color: tuple):
        keys = list(filter(lambda k: BUTTONS[k] == name, BUTTONS))
        if len(keys) != 1:
            logger.info(f"set_button_color: invalid button key {name}")
            return
        key = keys[0]
        (r, g, b) = color
        data = bytearray([key, r, g, b])
        self.do_action(HEADERS["SET_COLOR"], data)
        # logger.debug(f"set_button_color: sent {name}, {color}")

    def vibrate(self, pattern = "SHORT"):
        if pattern not in HAPTIC.keys():
            logger.error(f"vibrate: invalid pattern {pattern}")
            return
        self.do_action(HEADERS["SET_VIBRATION"], HAPTIC[pattern])
        # logger.debug(f"vibrate: sent {pattern}")

    # Image display functions
    #
    def refresh(self, display:int):
        display_info = DISPLAYS[display]
        self.do_action(HEADERS["DRAW"], display_info["id"], track=True)
        # logger.debug("refresh: refreshed")

    def draw_buffer(self, buff, display:str, width: int = None, height: int = None, x:int = 0, y:int = 0, auto_refresh:bool = True):
        display_info = DISPLAYS[display]
        if width is None:
            width = display_info["width"]
        if height is None:
            height = display_info["height"]
        expected = width * height * 2
        if len(buff) != expected:
            logger.error(f"draw_buffer: invalid buffer {len(buff)}, expected={expected}")
            return  # don't do anything because it breaks the connection to send invalid length buffer

        # logger.debug(f"draw_buffer: o={x},{y}, dim={width},{height}")

        header = x.to_bytes(2, BIG_ENDIAN)
        header = header + y.to_bytes(2, BIG_ENDIAN)
        header = header + width.to_bytes(2, BIG_ENDIAN)
        header = header + height.to_bytes(2, BIG_ENDIAN)
        payload = display_info["id"] + header + buff
        self.do_action(HEADERS["WRITE_FRAMEBUFF"], payload, track=True)
        # logger.debug(f"draw_buffer: buffer sent {len(buff)} bytes")
        if auto_refresh:
            self.refresh(display)

    def draw_image(self, image, display:str, width: int = None, height: int = None, x:int = 0, y:int = 0, auto_refresh:bool = True):
        buff = PILHelper.to_native_format(display, image)
        self.draw_buffer(buff, display=display, width=width, height=height, x=x, y=y, auto_refresh=auto_refresh)

    def draw_screen(self, image, display:str, auto_refresh:bool = True):
        if type(image) == bytearray:
            self.draw_buffer(image, display=display, auto_refresh=auto_refresh)
        else: # type(image) == PIL.Image.Image
            self.draw_image(image, display=display, auto_refresh=auto_refresh)

    def set_key_image(self, idx: str, image):
        # Get offset x/y for key index
        if idx == "left":
            display = idx
            x = 0
            y = 0
        elif idx == "right":
            display = idx
            x = 420
            y = 0
        else:
            display = "center"
            try:
                idx = int(idx)
                width = BUTTON_SIZES[display][0]
                height = BUTTON_SIZES[display][1]
                x = idx % 4 * width
                y = math.floor(idx / 4) * height
            except ValueError:
                logger.warning(f"set_key_image: key {idx}: invalid index for center display, aborting set_key_image")
                return

        width = BUTTON_SIZES[display][0]
        height = BUTTON_SIZES[display][1]
        # logger.info(f"set_key_image: key {idx}: {x}, {y}, {width}, {height}")

        if type(image) == bytearray:
            self.draw_buffer(image, display=display, width=width, height=height, x=x, y=y, auto_refresh=True)
        else: # type(image) == PIL.Image.Image
            self.draw_image(image, display=display, width=width, height=height, x=x, y=y, auto_refresh=True)

    def reset(self):
        colors = ["black" for i in range(3)]  # ["cyan", "magenta", "blue"]
        image = Image.new("RGBA", (60, BUTTON_SIZES["left"][1]), colors[0])
        self.draw_image(image, display="left", auto_refresh=True)
        image = Image.new("RGBA", (360, 270), colors[2])
        self.draw_image(image, display="center", auto_refresh=True)
        image = Image.new("RGBA", (60, BUTTON_SIZES["left"][1]), colors[1])
        self.draw_image(image, display="right", auto_refresh=True)


    # #########################################@
    # Development and testing
    #
    def test(self):
        self.vibrate("REV_FAST")
        time.sleep(1)
        self.vibrate("LOW")
        time.sleep(1)
        self.vibrate("LONG")
        self.set_brightness(50)
        self.set_button_color("1", "red")
        self.set_button_color("2", "orange")
        self.set_button_color("3", "yellow")
        self.set_button_color("4", "green")
        self.set_button_color("5", "blue")
        self.set_button_color("6", "purple")
        self.set_button_color("7", "white")
        self.test_image()

    def test_image(self):
        # image = Image.new("RGBA", (360, 270), "cyan")
        with open("yumi.jpg", "rb") as infile:
            image = Image.open(infile).convert("RGBA")
            self.draw_image(image, display="center")
        with open("left.jpg", "rb") as infile:
            image = Image.open(infile).convert("RGBA")
            self.draw_image(image, display="left")
        with open("right.jpg", "rb") as infile:
            image = Image.open(infile).convert("RGBA")
            self.draw_image(image, display="right")
        # image2 = Image.new("RGBA", (90, 90), "blue")
        # self.set_key_image(6, image2)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    devices = LoupedeckLive.list()
    def callback(msg):
        print(f"received {msg}")

    l = LoupedeckLive(path=devices[1], baudrate=256000, timeout=1)
    l.set_callback(callback)

    l.start()
    # test
    # time.sleep(10)
    # l.stop()
