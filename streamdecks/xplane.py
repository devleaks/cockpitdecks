import threading
import logging
import time

logger = logging.getLogger("Xplane")


class XPlane:  # (abc.ABC)
    """
    Abstract class for execution of operations in X-Plane
    """
    def __init__(self, decks):
        self.decks = decks
        self.running = False
        self.datarefs_to_monitor = {}  # list of datarefs to monitor and buttons attached to each

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
        if dataref in self.datarefs_to_monitor.keys():
            for b in self.datarefs_to_monitor[dataref]:
                # logger.debug(f"notify_changed: notified {b.name}")
                b.dataref_changed(dataref, value)

    # ################################
    # Streamdecks interface
    #
    def set_datarefs(self, datarefs):
        logger.debug(f"set_datarefs: not implemented")
        pass

    def start(self):
        logger.debug(f"start: not implemented")
        pass

    def terminate(self):
        logger.debug(f"terminate: not implemented")
        pass

    # ################################
    # X-Plane Interface
    #
    def commandOnce(self, command: str):
        logger.debug(f"commandOnce: not implemented")

    def commandBegin(self, command: str):
        logger.debug(f"commandBegin: not implemented")

    def commandEnd(self, command: str):
        logger.debug(f"commandEnd: not implemented")

    def get_value(self, dataref: str):
        logger.debug(f"get_value: not implemented")
        return None
