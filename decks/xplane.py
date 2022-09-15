import threading
import logging
import time

loggerDataref = logging.getLogger("Dataref")
logger = logging.getLogger("XPlane")


class Dataref:

    def __init__(self, path: str, is_decimal:bool = False, is_string:bool = False, length:int = None):
        self.path = path            # some/path/values[6]
        self.dataref = path         # some/path/values
        self.index = 0              # 6
        self.length = length        # length of some/path/values array, if available.
        self.xp_datatype = None
        self.data_type = "float"    # int, float, byte
        self.is_array = False       # array of above
        self.is_decimal = is_decimal
        self.is_string = is_string
        self.previous_value = None
        self.current_value = None
        self.current_array = []
        self.listeners = []         # buttons using this dataref, will get notified if changes.

        # is dataref a path to an array element?
        if "[" in path:  # sim/some/values[4]
            self.dataref = self.path[:self.path.find("[")]
            self.index = int(self.path[self.path.find("[")+1:self.path.find("]")])
            self.is_array = True
            if self.length is None:
                self.length = self.index + 1  # at least that many values
            if self.index >= self.length:
                loggerDataref.error(f"__init__: index {self.index} out of range [0,{self.length-1}]")

    def changed(self):
        if self.previous_value is None and self.current_value is None:
            return False
        elif self.previous_value is None and self.current_value is not None:
            return True
        elif self.previous_value is not None and self.current_value is None:
            return True
        return self.current_value != self.previous_value

    def update_value(self, new_value, cascade: bool = False):
        self.previous_value = self.current_value
        self.current_value = new_value
        if cascade:
            self.notify()
        # loggerDataref.error(f"update_value: dataref {self.path} updated")

    def add_listener(self, obj):
        self.listeners.append(obj)

    def notify(self):
        if self.changed():
            for l in self.listeners:
                l.dataref_changed(self)
        # else:
        #     loggerDataref.error(f"notify: dataref {self.path} not changed")


class XPlane:
    """
    Abstract class for execution of operations in X-Plane
    """
    def __init__(self, decks):
        self.decks = decks
        self.use_flight_loop = False
        self.running = False

        self.datarefs_to_monitor = {}  # list of datarefs to monitor and buttons attached to each
        self.xplaneValues = {}         # key = dataref-path, value = value

        # Values of datarefs
        self.previous_values = {}
        self.current_values = {}

    def detect_changed(self):
        """
        Update dataref values that have changed between 2 fetches.
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
    # Decks interface
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
