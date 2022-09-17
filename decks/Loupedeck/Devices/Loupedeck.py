"""
Loupedeck base class. Kind of ABC for future loupedeck devices.
"""
import logging
import threading
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

        self.update_lock = threading.RLock()

    def __del__(self):
        try:
            self.connection.close()
        except:
            pass

    def __enter__(self):
        """
        Enter handler for the StreamDeck, taking the exclusive update lock on
        the deck. This can be used in a `with` statement to ensure that only one
        thread is currently updating the deck, even if it is doing multiple
        operations (e.g. setting the image on multiple keys).
        """
        self.update_lock.acquire()

    def __exit__(self, type, value, traceback):
        """
        Exit handler for the StreamDeck, releasing the exclusive update lock on
        the deck.
        """
        self.update_lock.release()

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
