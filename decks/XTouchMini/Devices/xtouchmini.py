import mido
import time
import logging
import threading
import random
import time

logger = logging.getLogger("XTouchMini")

CHANNEL = 10

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

        self.test()

    def id(self):
        return self.name

    def open(self):
        pass

    def close(self):
        pass

    def reset(self):
        pass

    def is_visual(self):
        return False

    def get_serial_number(self):
        return self.input_device_name

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
        logger.debug(f"send: sent: {message}")

    def start(self) -> None:
        self.running = True
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
        self.wait_finished = threading.Event()
        self.running = False
        if not self.wait_finished.wait(2 * self.timeout):
            logger.warning(f"stop: did not stop cleanly")
        self.wait_finished = None


    # ##########################################
    # User Interface
    #
    def set_key(self, key: int, on:bool):
        m = mido.Message(type="note_on" if on else "note_off", note=key, velocity=127, channel=CHANNEL)
        self.send(m)

    # Modes: There are 11 LEDs
    # Single Led Lit:  00010000000 (Values 0 - 11)
    # Trim:   11110000000 (Values 16 - 27)
    # Fan:    00111100000 (Values 32 - 43)
    # Spread: 00011111000 (Values 48 - 59)
    #
    def set_control(self, key: int, value:int, mode: str = "single"):
        if value < 12 and mode != "single":
            if mode == "trim":
                value = value + 16
            elif mode == "fan":
                value = value + 32
            elif mode == "spread":
                value = value + 48
        elif mode == "single" and value < 0 or value > 11:
            logger.warning(f"set_control: invalid value {value}")
        elif value < 0 or value > 127:
            logger.warning(f"set_control: invalid value {value}")

        m = mido.Message(type="control_change", control=key, value=value, channel=CHANNEL)
        self.send(m)


    def test(self):
        for i in range(8, 24):
            self.set_key(i, on=random.choice([True, False]))

        for i in range(1, 9):
            self.set_control(i, value=random.randrange(127), mode=None)
