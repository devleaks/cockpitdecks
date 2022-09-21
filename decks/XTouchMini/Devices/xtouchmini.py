import mido
import time
import logging
import threading

logger = logging.getLogger("XTouchMini")


class XTouchMini:

    def __init__(self, input_device_name: str, output_device_name: str):
        self.input_device_name = input_device_name
        self.output_device_name = output_device_name

        self._input_device = None
        self._output_device = None

        self.callback = None
        self.timeout = 10
        self.wait_finished = None


    def open(self):
        pass

    def close(self):
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
            payload = (msg.note, 1)
        elif msg.type == "note_off":
            payload = (msg.note, 0)
        elif msg.type == "control_change":
            if msg.control in [9, 10]:  # slider A and B
                payload = (msg.control, msg.value)
            else:
                payload = (msg.control, 2 if msg.value > 64 else 3)

        if self.callback is not None and payload is not None:
            self.callback(payload)


    def _write(self, msg: mido.Message) -> None:
        pass


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
        m = mido.Message(type="note_on" if on else "note_off", note=key)


    def set_control(self, key: int, value:int, mode: str):
        m = mido.Message(type="control_change", control=key, value=value)
