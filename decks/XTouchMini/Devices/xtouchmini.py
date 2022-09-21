# Deck controller for Behringer X-Touch Mini devices
#
import time
import logging
import threading
import random
import mido
from enum import Enum

logger = logging.getLogger("XTouchMini")

GLOBAL_CHANNEL = 0
CHANNEL = 10

class LED_MODE(Enum):
    SINGLE = 0
    PAN = 1
    FAN = 2
    SPREAD = 3
    TRIM = 4

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


    def id(self):
        return self.name

    def open(self):
        pass

    def close(self):
        pass

    def reset(self):
        for i in range(16):
            self.set_key(i)
        for i in range(1, 9):
            self.set_control(i, value=0)

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


    def _read(self, msg: mido.Message) -> None:
        logger.debug(f"_read: {msg}")

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
        self.running = True
        t = threading.Thread(target=self.loop)
        t.name = "XTouchMini::loop"
        t.start()
        logger.debug(f"start: ..started")

    def loop(self) -> None:
        m = None
        try:
            logger.debug(f'start: opening MIDI device: "{self.name}"..')
            m = mido.open_input(self.name, callback=self._read)
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
        logger.debug(f"stop: stopping {self.name}..")
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
        velocity = 0
        if on:
            velocity = 1
        elif blink:
            velocity = 2
        m = mido.Message(type="note_on", note=key, velocity=velocity)
        self.send(m)

    # Modes: There are 11 LEDs
    # Single Led Lit:  00010000000 (Values 0 - 11)
    # Trim:   11110000000 (Values 16 - 27)
    # Fan:    00111100000 (Values 32 - 43)
    # Spread: 00011111000 (Values 48 - 59)
    #
    def set_control(self, key: int, value:int, mode: LED_MODE = LED_MODE.SINGLE):
        def decode_value(v):
            if v == 0:
                return "all off"
            elif v < 14:
                return f"single {v} on"
            elif v > 13 and v < 27:
                return f"single {v - 13} blink"
            elif v == 27:
                return "all on"
            elif v == 28:
                return "all blink"
            else:
                return "ignored"

        m = mido.Message(type="control_change", control=key, value=mode.value)
        self.send(m)
        m = mido.Message(type="control_change", control=8+key, value=value)
        self.send(m)
        logger.debug(f"set_control: encoder {key}: {mode.name}: {decode_value(value)}")


    def test(self):
        m = mido.Message(type="control_change", control=127, value=1)
        self.send(m)
        time.sleep(1)
        m = mido.Message(type="control_change", control=127, value=0)
        self.send(m)
        time.sleep(1)

        for i in range(16):
            self.set_key(i, on=random.choice([True, False]), blink=random.choice([True, False, False, False, False, False, False, False]))

        for i in range(1, 9):
            self.set_control(i, value=random.randrange(29), mode=random.choice(list(LED_MODE)))

        # for k in range(5):
        #     for i in range(60):
        #         m = mido.Message(type="control_change", control=8, value=4)
        #         self.send(m)
        #         m = mido.Message(type="control_change", control=16, value=i)
        #         self.send(m)
        #         time.sleep(0.2)
