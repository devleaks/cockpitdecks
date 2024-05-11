# Base classes for interface with the simulation software
#
import threading
import logging
from typing import List, Any
from datetime import datetime, timedelta
from abc import ABC, abstractmethod

from cockpitdecks import SPAM_LEVEL, now
from cockpitdecks.event import Event

loggerDataref = logging.getLogger("Dataref")
# loggerDataref.setLevel(SPAM_LEVEL)
# loggerDataref.setLevel(logging.DEBUG)

loggerCommand = logging.getLogger("Command")
# loggerCommand.setLevel(SPAM_LEVEL)
# loggerCommand.setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)  # To see when dataref are updated
# logger.setLevel(logging.DEBUG)

# ########################################
# Command
#
# The command keywords are not executed, ignored with a warning
NOT_A_COMMAND = [
    "none",
    "noop",
    "no-operation",
    "no-command",
    "do-nothing",
]  # all forced to lower cases


class Command:
    """
    A Button activation will instruct the simulator software to perform an action.
    A Command is the message that the simulation sofware is expecting to perform that action.
    """

    def __init__(self, path: str | None, name: str | None = None):
        self.path = path  # some/command
        self.name = name

    def __str__(self) -> str:
        return self.name if self.name is not None else (self.path if self.path is not None else "no command")

    def has_command(self) -> bool:
        return self.path is not None and not self.path.lower() in NOT_A_COMMAND


# ########################################
# Dataref
#
INTERNAL_DATAREF_PREFIX = "data:"  # "internal" datarefs (not exported to X-Plane) start with that prefix
NOT_A_DATAREF = ["DatarefPlaceholder"]


class Dataref:
    """
    A Dataref is an internal value of the simulation software made accessible to outside modules,
    plugins, or other software in general.
    """

    def __init__(
        self,
        path: str,
        is_decimal: bool = False,
        is_string: bool = False,
        length: int | None = None,
    ):
        self.path = path  # some/path/values[6]
        self.dataref = path  # some/path/values
        self.index = 0  # 6
        self.length = length  # length of some/path/values array, if available.
        self.is_array = False  # array of above
        self.is_decimal = is_decimal
        self._is_string = is_string
        self._previous_value = None  # raw values
        self._current_value = None
        self._last_updated = None
        self._last_changed = None
        self._updated = 0  # number of time value updated
        self._changed = 0  # number of time value changed
        self.previous_value = None
        self.current_value: Any | None = None
        self.current_array: List[float] = []
        self.listeners: List[DatarefListener] = []  # buttons using this dataref, will get notified if changes.
        self._round = None
        self.update_frequency = 1  # sent by the simulator that many times per second.
        self.expire = None

        self.data_type = "float"  # int, float, byte, UDP always returns a float...
        if self.is_decimal:
            self.data_type = "int"
            if self._is_string:
                loggerDataref.error(f"__init__: index {self.path} cannot be both decimal and string")
        elif self._is_string:
            self.data_type = "str"

        if self.length is not None and self.length > 1:
            self.is_array = True

        # is dataref a path to an array element?
        if "[" in path:  # sim/some/values[4]
            self.dataref = self.path[: self.path.find("[")]
            self.index = int(self.path[self.path.find("[") + 1 : self.path.find("]")])
            self.is_array = True
            if self.length is None:
                self.length = self.index + 1  # at least that many values
            if self.index >= self.length:
                loggerDataref.error(f"__init__: index {self.index} out of range [0,{self.length-1}]")

    @staticmethod
    def get_dataref_type(path):
        if len(path) > 3 and path[-2:-1] == ":" and path[-1] in "difsb":  # decimal, integer, float, string, byte(s)
            return path[:-2], path[-1]
        return path, "f"

    @staticmethod
    def is_internal_dataref(path: str) -> bool:
        return path.startswith(INTERNAL_DATAREF_PREFIX)

    @staticmethod
    def mk_internal_dataref(path: str) -> str:
        return INTERNAL_DATAREF_PREFIX + path

    def is_string(self) -> bool:
        return self._is_string

    def is_internal(self) -> bool:
        return Dataref.is_internal_dataref(self.path)

    def set_round(self, rounding):
        self._round = rounding

    def set_update_frequency(self, frequency=1):
        if frequency is not None and type(frequency) in [int, float]:
            self.update_frequency = frequency
        else:
            self.update_frequency = 1

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
        elif self.data_type == "str" or self.data_type == "string" or self.is_string():
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

    def updated(self) -> bool:
        # Returns True if updated at least once
        return self._updated > 0

    def round(self, new_value):
        return round(new_value, self._round) if self._round is not None and type(new_value) in [int, float] else new_value

    def update_value(self, new_value, cascade: bool = False) -> bool:
        self._previous_value = self._current_value  # raw
        self._current_value = new_value  # raw
        self.previous_value = self.current_value  # exposed
        if self.is_string():
            self.current_value = new_value
        else:
            self.current_value = self.round(new_value)
        self._updated = self._updated + 1
        self._last_updated = now()
        self.notify_updated()
        if self.has_changed():
            self._changed = self._changed + 1
            self._last_changed = now()
            loggerDataref.log(
                SPAM_LEVEL,
                f"dataref {self.path} updated {self.previous_value} -> {self.current_value}",
            )
            if cascade:
                self.notify()
            return True
        # loggerDataref.error(f"dataref {self.path} updated")
        return False

    def set_expired(self, expire):
        self.expire = expire

    def is_expired(self, when) -> bool:
        if self.expire is None:
            return False
        if self._last_updated is None:
            return True
        return (self._last_updated + timedelta(seconds=self.expire)) < when

    def add_listener(self, obj):
        if not isinstance(obj, DatarefListener):
            loggerDataref.warning(f"{self.dataref} not a listener {obj}")
        if obj not in self.listeners:
            self.listeners.append(obj)
        loggerDataref.debug(f"{self.dataref} added listener ({len(self.listeners)})")

    def notify(self):
        if self.has_changed():
            for dref in self.listeners:
                dref.dataref_changed(self)
                if hasattr(dref, "page") and dref.page is not None:
                    loggerDataref.log(
                        SPAM_LEVEL,
                        f"{self.path}: notified {dref.page.name}/{dref.name}",
                    )
                else:
                    loggerDataref.log(
                        SPAM_LEVEL,
                        f"{self.path}: notified {dref.name} (not on an page)",
                    )
        # else:
        #    loggerDataref.error(f"dataref {self.path} not changed")

    def notify_updated(self):
        for dref in self.listeners:
            dref.dataref_updated(self)
            if hasattr(dref, "page") and dref.page is not None:
                loggerDataref.log(
                    SPAM_LEVEL,
                    f"{self.path}: notified {dref.page.name}/{dref.name} or update",
                )
            else:
                loggerDataref.log(
                    SPAM_LEVEL,
                    f"{self.path}: notified {dref.name} of update (not on an page)",
                )
        # else:
        #    loggerDataref.error(f"dataref {self.path} not changed")


class DatarefListener(ABC):
    # To get notified when a dataref has changed.

    def __init__(self, name: str = "abstract-dataref-listener"):
        self.name = name

    @abstractmethod
    def dataref_changed(self, dataref):
        pass

    def dataref_updated(self, dataref):
        pass


# ########################################
# Simulator
#
class Simulator(ABC):
    """
    Abstract class for execution of operations and collection of data in the simulation software.
    """

    def __init__(self, cockpit):
        self._inited = False
        self.name = type(self).__name__
        self.cockpit = cockpit
        self.running = False
        self.all_datarefs = {}

        self.datarefs_to_monitor = {}  # dataref path and number of objects monitoring

        self.dataref_db_lock = threading.RLock()

        self.roundings = {}  # path: int
        self.dataref_frequencies = {}

        self._startup = True

        self.cockpit.set_logging_level(__name__)

    def set_roundings(self, roundings):
        self.roundings = roundings

    def set_dataref_frequencies(self, dataref_frequencies):
        self.dataref_frequencies = dataref_frequencies

    def set_rounding(self, dataref):
        if dataref.path.find("[") > 0:
            rnd = self.roundings.get(dataref.path)
            if rnd is not None:
                dataref.set_round(rounding=rnd)  # rounds this very priecise dataref
            else:
                idx = dataref.path.find("[")
                base = dataref.path[:idx]
                rnd = self.roundings.get(base + "[*]")  # rounds all datarefs in array, explicit
                if rnd is not None:
                    dataref.set_round(rounding=rnd)  # rounds this very priecise dataref
                # rnd = self.roundings.get(base)        # rounds all datarefs in array
                # if rnd is not None:
                #   dataref.set_round(rounding=rnd)     # rounds this very priecise dataref
        else:
            dataref.set_round(rounding=self.roundings.get(dataref.path))

    def set_frequency(self, dataref):
        if dataref.path.find("[") > 0:
            freq = self.dataref_frequencies.get(dataref.path)
            if freq is not None:
                dataref.set_update_frequency(frequency=freq)  # rounds this very priecise dataref
            else:
                idx = dataref.path.find("[")
                base = dataref.path[:idx]
                freq = self.dataref_frequencies.get(base + "[*]")  # rounds all datarefs in array, explicit
                if freq is not None:
                    dataref.set_update_frequency(frequency=freq)  # rounds this very priecise dataref
                # rnd = self.roundings.get(base)        # rounds all datarefs in array
                # if rnd is not None:
                #   dataref.set_round(rounding=rnd)     # rounds this very priecise dataref
        else:
            dataref.set_update_frequency(frequency=self.dataref_frequencies.get(dataref.path))

    def register(self, dataref):
        if dataref.path not in self.all_datarefs:
            if dataref.exists():
                self.set_rounding(dataref)
                self.set_frequency(dataref)
                self.all_datarefs[dataref.path] = dataref
            else:
                logger.warning(f"invalid dataref {dataref.path}")
        return dataref

    def datetime(self, zulu: bool = False, system: bool = False) -> datetime:
        """Returns the simulator date and time"""
        return datetime.now().astimezone()

    def get_dataref_value(self, dataref, default=None):
        d = self.all_datarefs.get(dataref)
        if d is None:
            logger.warning(f"{dataref} not found")
            return None
        return d.current_value if d.current_value is not None else default

    # ################################
    # Cockpit interface
    #
    def clean_datarefs_to_monitor(self):
        self.datarefs_to_monitor = {}

    def add_datarefs_to_monitor(self, datarefs: dict):
        prnt = []
        for d in datarefs.values():
            if d.path.startswith(INTERNAL_DATAREF_PREFIX):
                logger.debug(f"local dataref {d.path} is not monitored")
                continue
            if d.path not in self.datarefs_to_monitor.keys():
                self.datarefs_to_monitor[d.path] = 1
                prnt.append(d.path)
            else:
                self.datarefs_to_monitor[d.path] = self.datarefs_to_monitor[d.path] + 1
        logger.debug(f"added {prnt}")
        logger.debug(f"currently monitoring {self.datarefs_to_monitor}")

    def remove_datarefs_to_monitor(self, datarefs):
        prnt = []
        for d in datarefs.values():
            if d.path.startswith(INTERNAL_DATAREF_PREFIX):
                logger.debug(f"local dataref {d.path} is not monitored")
                continue
            if d.path in self.datarefs_to_monitor.keys():
                self.datarefs_to_monitor[d.path] = self.datarefs_to_monitor[d.path] - 1
                if self.datarefs_to_monitor[d.path] == 0:
                    prnt.append(d.path)
                    del self.datarefs_to_monitor[d.path]
            else:
                if not self._startup:
                    logger.warning(f"dataref {d.path} not monitored")
        logger.debug(f"removed {prnt}")
        logger.debug(f"currently monitoring {self.datarefs_to_monitor}")

    def remove_all_datarefs(self):
        logger.debug(f"removing..")
        self.all_datarefs = {}
        self.datarefs_to_monitor = {}
        logger.debug(f"..removed")

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


class SimulatorEvent(Event):
    """Simulator event base class.

    Defines required capability to handle event.
    Keeps a timestamp when event was created

    [description]
    """

    def __init__(self, sim: Simulator, autorun: bool = True):
        """Simulator event

        Args:
            action (DECK_ACTIONS): Action produced by this event (~ DeckEvent type)
            deck (Deck): Deck that produced the event
        """
        self.sim = sim
        Event.__init__(self, autorun=autorun)

    def __str__(self):
        return f"{self.sim.name}:{self.timestamp}"


from .collector import (
    MAX_COLLECTION_SIZE,
    DatarefSet,
    DatarefSetListener,
    DatarefSetCollector,
)
