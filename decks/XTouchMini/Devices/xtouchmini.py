# Deck controller for Behringer X-Touch Mini devices
#
import time
import logging
import threading
import random
import mido
from enum import Enum

logger = logging.getLogger("XTouchMini")
# logger.setLevel(logging.DEBUG)

GLOBAL_CHANNEL = 0
CHANNEL = 10

class LED_MODE(Enum):
    SINGLE = 0
    TRIM = 1
    FAN = 2
    SPREAD = 3

MAKIE_MAPPING = {
    0: 89,
    1: 90,
    2: 40,
    3: 41,
    4: 42,
    5: 43,
    6: 44,
    7: 45,
    8: 87,
    9: 88,
   10: 91,
   11: 92,
   12: 86,
   13: 93,
   14: 94,
   15: 95,
  "A": 84,
  "B": 85
}

class XTouchMini:

    def __init__(self, input_device_name: str, output_device_name: str):
        self.name = input_device_name   # label
        self.input_device_name = input_device_name
        self.output_device_name = output_device_name

        self._input_device = None
        self._output_device = mido.open_output(output_device_name)

        self.callback = None
        self.timeout = 10
        self.wait_finished = None
        self.makie = False


    def id(self):
        return self.name

    def deck_type(self):
        return "xtouchmini"

    def open(self):
        pass

    def close(self):
        pass

    def reset(self, silence: bool = True):
        if silence:
            l= logger.getEffectiveLevel()
            logger.setLevel(logging.WARNING)
        logger.debug(f"reset: reseting..")
        for i in MAKIE_MAPPING.keys():
            self.set_key(i)
        for i in range(8):
            self.set_control(i, value=0)
        logger.debug(f"reset: ..reset")
        if silence:
            logger.setLevel(l)

    def is_visual(self):
        return False

    def get_serial_number(self):
        return self.input_device_name

    def key_names(self):
        a = [i for i in range(16)]
        for i in range(1, 9):
            a.append(f"Knob{i}")
        return a

    def set_callback(self, callback: callable):
        self.callback = callback


    def _read_makie(self, msg: mido.Message) -> None:
        # ** MAKIE VERSION **
        # logger.debug(f"_read: {msg}")
        payload = None
        if msg.type == "note_on":
            payload = { "key": msg.note, "state": 1 if msg.velocity == 127 else 0 }
        elif msg.type == "note_off":
            payload = { "key": msg.note, "state": 0 }
        elif msg.type == "control_change":
            if msg.control in [9, 10]:  # slider A and B
                payload = { "key": msg.control, "state": msg.value }
            else:
                payload = { "key": msg.control, "state": 2 if msg.value > 64 else 3 }
        elif msg.type == "pitchwheel":
                payload = { "key": msg.channel, "state": msg.pitch }

        if self.callback is not None and payload is not None:
            payload["deck"] = self
            self.callback(**payload)


    def _read(self, msg: mido.Message) -> None:
        # ** STANDARD VERSION **
        #logger.debug(f"_read: {msg}")
        payload = None
        if msg.type == "note_on":
            payload = { "key": msg.note, "state": 1 }
        elif msg.type == "note_off":
            payload = { "key": msg.note, "state": 0 }
        elif msg.type == "control_change":
            if msg.control in [9, 10]:  # slider A and B
                payload = { "key": msg.control, "state": msg.value }
            else:
                payload = { "key": msg.control, "state": 2 if msg.value > 64 else 3 }

        if self.callback is not None and payload is not None:
            payload["deck"] = self
            self.callback(**payload)


    def _write(self, message: mido.Message) -> None:
        if self._output_device is not None:
            logger.debug(f"send: sending '{str(message)}'")
            self._output_device.send(message)


    def send(self, message: mido.Message):
        self._write(message)
        # logger.debug(f"send: sent: {message}")

    def start(self) -> None:
        logger.debug(f"start: starting {self.name}..")

        logger.debug(f"start: setting Makie mode..")
        m = mido.Message(type="control_change", control=127, value=1)
        self.send(m)
        self.makie = True
        time.sleep(1)
        logger.debug(f"start: ..set")

        self.running = True
        t = threading.Thread(target=self.loop)
        t.name = "XTouchMini::loop"
        t.start()
        logger.debug(f"start: ..started")

    def loop(self) -> None:
        m = None
        try:
            logger.debug(f'start: opening MIDI device: "{self.name}"..')
            m = mido.open_input(self.name, callback=self._read_makie if self.makie else self._read)
            logger.debug('start: ..device opened')
            while self.running:
                time.sleep(self.timeout)
            if self.wait_finished is not None:
                self.wait_finished.set()
        except Exception as e:
            logger.error(f"start: exception:", exc_info=1)
        except KeyboardInterrupt:
            if m is not None:
                m.close()
                logger.debug(f'start: closed MIDI device: "{self.name}"')


    def stop(self) -> None:
        logger.debug(f"stop: stopping {self.name} (wait can last up to {2 * self.timeout}s)..")
        self.wait_finished = threading.Event()
        self.running = False
        if not self.wait_finished.wait(2 * self.timeout):
            logger.warning(f"stop: did not stop cleanly")
        self.wait_finished = None
        logger.debug(f"stop: ..stopped")


    # ##########################################
    # User Interface
    #
    def set_brightness(self, brightness: int):
        pass

    def set_key(self, key: int, on:bool=False, blink:bool=False):
        # https://stackoverflow.com/questions/39435550/changing-leds-on-x-touch-mini-mackie-control-mc-mode
        # To blink, key must be on=True and blink=True
        if key not in MAKIE_MAPPING.keys():
            logger.warning(f"set_key: invalid key {key}")
            return
        velocity = 0
        if on:
            velocity = 127
            if blink:
                velocity = 1
        m = mido.Message(type="note_on", note=MAKIE_MAPPING[key], velocity=velocity)
        self.send(m)

    # #: Modes : There are 11 LEDs: 0-4, middle=5, 6-10
    # 0: Single: 00000001000
    # 1: Fan   : 00000111000
    # 2: Trim  : 11111111000
    # 3: Spread: 00111111100
    #
    def set_control(self, key: int, value:int, mode: LED_MODE = LED_MODE.SINGLE):
        if key < 0 or key > 7:
            logger.warning(f"set_control: invalid key {key}")
            return
        if value < 0:
            logger.warning(f"set_control: invalid value {value}, setting min")
            value = 0
        elif value > 11:
            logger.warning(f"set_control: invalid value {value}, setting max")
            value = 11
        m = mido.Message(type="control_change", control=48+key, value=(mode.value * 16)+value)
        self.send(m)


    def test(self):
        m = mido.Message(type="control_change", control=127, value=1)
        self.send(m)
        time.sleep(1)
        value_offset = 8
        mode = None

        for i in range(128):
            self.set_key(i)
        logger.debug(f"test: ..reset")

        for i in range(40, 46):
            self.set_key(i, on=True, blink=False)
            time.sleep(1)

        # for i in range(0, 8):
        #     for j in range(1, 127):
        #         if mode is not None:
        #             m = mido.Message(type="control_change", control=i, value=mode)
        #             self.send(m)
        #         m = mido.Message(type="control_change", control=48+(i%8), value=j)
        #         self.send(m)
        #         time.sleep(0.1)
