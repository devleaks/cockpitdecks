"""
Loupedeck base class. Kind of ABC for future loupedeck devices.
"""
import logging
from queue import Queue

logger = logging.getLogger("Loupedeck")

class Loupedeck:

    def __init__(self):
        self.connection = None
        self.serial = None
        self.version = None
        self.inited = False
        self.running = False
        self.path = None

        self._buffer = bytearray(b"")
        self._messages = Queue()

        self.pendingTransactions = [None for _ in range(256)]
        self.transaction_id = 0

        self.callback = None

    def get_info(self):
        if self.inited:
            return {
                "version": self.version,
                "serial": self.serial,
                "path": self.path
            }
        return None

    def get_serial_number(self):
        return self.serial if self.inited else None
