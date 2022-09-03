import threading
import logging
import time

logger = logging.getLogger("Xplane")


class XPlane:
    """
    Abstract class for execution of operations in X-Plane
    """
    def __init__(self, decks):
        self.decks = decks
        self.running = False
        self.datarefs = {}  # list of datarefs to monitor and buttons attached to each

        # Values of datarefs
        self.previous_values = {}
        self.current_values = {}

    def detect_changed(self):
        """
        Detects datarefs that have changed between 2 fetches and notifies interested buttons.
        """
        for d in self.current_values.keys():
            if d not in self.previous_values.keys() or self.current_values[d] != self.previous_values[d]:
                self.notify_changed(d, self.current_values[d])
        self.previous_values = self.current_values.copy()

    def notify_changed(self, dataref, value):
        if dataref in self.datarefs.keys():
            for b in self.datarefs[dataref]:
                b.dataref_changed(dataref, value)

    # X-Plane Interface
    #
    #
    def commandOnce(self, command: str):
        pass

    def commandBegin(self, command: str):
        pass

    def commandEnd(self, command: str):
        pass

    def read(self, dataref: str):
        return None
