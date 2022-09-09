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
                logger.debug(f"detect_changed: {d}={self.current_values[d]} changed (was {self.previous_values[d] if d in self.previous_values else 'None'}), notifying..")
                if d in self.datarefs_to_monitor.keys():
                    self.datarefs_to_monitor[d].update_value(self.current_values[d], cascade=True)
                else:
                    logger.warning(f"detect_changed: updated dataref not in dataref to monitor (was {self.datarefs_to_monitor.keys()})")
                logger.debug(f"detect_changed: ..done")
            # else:
            #     logger.debug(f"detect_changed: {d}={self.current_values[d]} not changed (was {self.previous_values[d]})")
        self.previous_values = self.current_values.copy()

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
