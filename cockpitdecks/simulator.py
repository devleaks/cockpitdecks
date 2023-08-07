# Base classes for interface with the simulation software
#
import threading
import logging
import time
from abc import ABC, abstractmethod

from cockpitdecks import SPAM_LEVEL

loggerDataref = logging.getLogger("Dataref")
# loggerDataref.setLevel(SPAM_LEVEL)
# loggerDataref.setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)  # To see when dataref are updated
# logger.setLevel(logging.DEBUG)

INTERNAL_DATAREF_PREFIX = "data:"  # "internal" datarefs (not exported to X-Plane) start with that prefix
NOT_A_COMMAND = ["none", "noop", "no-operation", "no-command", "do-nothing"]

class Command:
    """
    A Button activation will instruct the simulator software to perform an action.
    A Command is the message that the simulation sofware is expecting to perform that action.
    """    
    def __init__(self, path: str, name: str = None):

        self.path = path            # some/command
        self.name = name

    def __str__(self) -> str:
        return self.name if self.name is not None else (self.path if self.path is not None else "no command")

    def has_command(self) -> bool:
    	return self.path is not None and not self.path.lower() in NOT_A_COMMAND

class Dataref:
    """
    A Dataref is an internal value of the simulation software made accessible to outside modules,
    plugins, or other software in general.
    """

    def __init__(self, path: str, is_decimal:bool = False, is_string:bool = False, length:int = None):

        self.path = path            # some/path/values[6]
        self.dataref = path         # some/path/values
        self.index = 0              # 6
        self.length = length        # length of some/path/values array, if available.
        self.sim_datatype = None
        self.data_type = "float"    # int, float, byte
        self.is_array = False       # array of above
        self.is_decimal = is_decimal
        self.is_string = is_string
        self._previous_value = None  # raw values
        self._current_value = None
        self._last_updated = None
        self.previous_value = None
        self.current_value = None
        self.current_array = []
        self.listeners = {}         # buttons using this dataref, will get notified if changes.
        self.round = None

        # dataref/path:t where t in d, i, f, s, b.
        if len(path) > 3 and path[-2:-1] == ":" and path[-1] in "difsb":  # decimal, integer, float, string, byte(s)
            path = path[:-2]
            typ = path[-1]
            if typ == "d":
                self.is_decimal = True
                self.data_type = "int"
            elif typ == "s":
                self.is_string = True
                self.data_type = "str"
                self.is_array = True
            elif typ == "b":
                self.is_string = "byte"


        if is_decimal and is_string:
            loggerDataref.error(f"__init__: index {path} cannot be both decimal and string")

        if length is not None and length > 1:
            self.is_array = True

        # is dataref a path to an array element?
        if "[" in path:  # sim/some/values[4]
            self.dataref = self.path[:self.path.find("[")]
            self.index = int(self.path[self.path.find("[")+1:self.path.find("]")])
            self.is_array = True
            if self.length is None:
                self.length = self.index + 1  # at least that many values
            if self.index >= self.length:
                loggerDataref.error(f"__init__: index {self.index} out of range [0,{self.length-1}]")

    @staticmethod
    def is_internal_dataref(path):
        return path.startswith(INTERNAL_DATAREF_PREFIX)

    @staticmethod
    def mk_internal_dataref(path):
        return INTERNAL_DATAREF_PREFIX + path

    def is_internal(self):
        return self.path.startswith(INTERNAL_DATAREF_PREFIX)

    def set_round(self, rounding):
        self.round = rounding

    def value(self):
        return self.current_value

    def value_typed(self):
        # May fail during conversion
        if self.current_value is None:
            return None
        if self.data_type == "float":
            return float(self.current_value)
        elif self.data_type == "int" or self.is_decimal:
            return int(self.current_value)
        elif self.data_type == "str" or self.data_type == "string" or self.is_string:
            return str(self.current_value)
        # arrays, etc
        return self.current_value

    def exists(self):
        return self.path is not None

    def has_changed(self):
        if self.previous_value is None and self.current_value is None:
            return False
        elif self.previous_value is None and self.current_value is not None:
            return True
        elif self.previous_value is not None and self.current_value is None:
            return True
        return self.current_value != self.previous_value

    def update_value(self, new_value, cascade: bool = False):
        self._previous_value = self._current_value
        self._current_value = new_value
        self.previous_value = self.current_value
        if self.round is not None:
            self.current_value = round(new_value, self.round)
            loggerDataref.debug(f"update_value: dataref {self.path} value {new_value} rounded to {self.current_value}")
        else:
            self.current_value = new_value
        if self.has_changed():
            loggerDataref.log(SPAM_LEVEL, f"update_value: dataref {self.path} updated {self.previous_value} -> {self.current_value}")
            if cascade:
                self.notify()
        # loggerDataref.error(f"update_value: dataref {self.path} updated")

    def add_listener(self, button):
        self.listeners[button.get_id()] = button
        # if obj not in self.listeners:
        #     self.listeners.append(obj)
        loggerDataref.debug(f"add_listener: {self.dataref} added {button.get_id()} ({len(self.listeners)})")

    def notify(self):
        if self.has_changed():
            for k, v in self.listeners.items():
                v.dataref_changed(self)
                if hasattr(v, "page") and v.page is not None:
                    loggerDataref.log(SPAM_LEVEL, f"notify: {self.path}: notified {v.page.name}/{v.name}")
                else:
                    loggerDataref.log(SPAM_LEVEL, f"notify: {self.path}: notified {v.name} (not on a page)")
        # else:
        #     loggerDataref.error(f"notify: dataref {self.path} not changed")


class Simulator(ABC):
    """
    Abstract class for execution of operations and collection of data in the simulation software.
    """
    def __init__(self, decks):
        self.cockpit = decks
        self.use_flight_loop = False
        self.running = False
        self.all_datarefs = {}

        self.datarefs_to_monitor = {}  # dataref path and number of objects monitoring
        self.simlaneValues = {}         # key = dataref-path, value = value

        # Values of datarefs
        self.previous_values = {}
        self.current_values = {}

        self.dataref_db_lock = threading.RLock()

        self.roundings = {}    # path: int
        self.slow_datarefs = {}

        self.cockpit.set_logging_level(__name__)

    def set_roundings(self, roundings):
        self.roundings = roundings

    def set_slow_datarefs(self, slow_datarefs):
        self.slow_datarefs = slow_datarefs

    def detect_changed(self):
        """
        Update dataref values that have changed between 2 fetches.
        """
        try:
            currvalues = None
            with self.dataref_db_lock:
                currvalues = self.current_values.copy()  # we take a copy first so that it does not change...

            if currvalues is not None:
                for d in currvalues.keys():
                    if d not in self.previous_values.keys() or currvalues[d] != self.previous_values[d]:
                        # logger.debug(f"detect_changed: {d}={self.current_values[d]} changed (was {self.previous_values[d] if d in self.previous_values else 'None'}), notifying..")
                        if d in self.datarefs_to_monitor.keys():
                            self.all_datarefs[d].update_value(currvalues[d], cascade=True)
                        else:
                            self.all_datarefs[d].update_value(currvalues[d], cascade=False)  # we just update the value but no notification
                            logger.warning(f"detect_changed: updated dataref '{d}' not in datarefs to monitor. No propagation") #  (was {self.datarefs_to_monitor.keys()})
                            # This means we got a value from X-Plane we never asked for this run...
                            # It could be a dataref-request leak (!) or someone else is requesting datarefs over UDP.
                        # logger.debug(f"detect_changed: ..done")
                    # else:
                    #     logger.debug(f"detect_changed: {d}={self.current_values[d]} not changed (was {self.previous_values[d]})")
            else:
                logger.warning(f"detect_changed: no current values") #  (was {self.datarefs_to_monitor.keys()})
        except RuntimeError:
            logger.warning(f"detect_changed:", exc_info=True)

    def register(self, dataref):
        if dataref.path not in self.all_datarefs:
            if dataref.exists():
                dataref.set_round(rounding=self.roundings.get(dataref.path))
                self.all_datarefs[dataref.path] = dataref
            else:
                logger.warning(f"register: invalid dataref {dataref.path}")
        return dataref


    # ################################
    # Cockpit interface
    #
    def clean_datarefs_to_monitor(self):
        self.datarefs_to_monitor = {}

    def add_datarefs_to_monitor(self, datarefs: dict):
        prnt = []
        for d in datarefs.values():
            if d.path.startswith(INTERNAL_DATAREF_PREFIX):
                logger.debug(f"add_datarefs_to_monitor: local dataref {d.path} is not monitored")
                continue
            if d.path not in self.datarefs_to_monitor.keys():
                self.datarefs_to_monitor[d.path] = 1
                prnt.append(d.path)
            else:
                self.datarefs_to_monitor[d.path] = self.datarefs_to_monitor[d.path] + 1
        logger.debug(f"add_datarefs_to_monitor: added {prnt}")
        logger.debug(f"add_datarefs_to_monitor: currently monitoring {self.datarefs_to_monitor}")

    def remove_datarefs_to_monitor(self, datarefs):
        prnt = []
        for d in datarefs.values():
            if d.path.startswith(INTERNAL_DATAREF_PREFIX):
                logger.debug(f"remove_datarefs_to_monitor: local dataref {d.path} is not monitored")
                continue
            if d.path in self.datarefs_to_monitor.keys():
                self.datarefs_to_monitor[d.path] = self.datarefs_to_monitor[d.path] - 1
                if self.datarefs_to_monitor[d.path] == 0:
                    prnt.append(d.path)
                    del self.datarefs_to_monitor[d.path]
            else:
                logger.warning(f"remove_datarefs_to_monitor: dataref {d.path} not monitored")
        logger.debug(f"remove_datarefs_to_monitor: removed {prnt}")
        logger.debug(f"remove_datarefs_to_monitor: currently monitoring {self.datarefs_to_monitor}")

    def remove_all_datarefs(self):
        logger.debug(f"remove_all_datarefs: removing..")
        self.all_datarefs = {}
        self.datarefs_to_monitor = {}
        self.simlaneValues = {}
        self.previous_values = {}
        self.current_values = {}
        logger.debug(f"remove_all_datarefs: ..removed")

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def terminate(self):
        pass

    # ################################
    # X-Plane Interface
    #
    @abstractmethod
    def commandOnce(self, command: Command):
        pass

    @abstractmethod
    def commandBegin(self, command: Command):
        pass

    @abstractmethod
    def commandEnd(self, command: Command):
        pass
