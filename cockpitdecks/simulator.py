# Base classes for interface with the simulation software
#
from __future__ import annotations
import threading
import logging
from datetime import datetime
from typing import List, Any
from abc import ABC, abstractmethod
from enum import Enum

from cockpitdecks import SPAM_LEVEL, DEFAULT_FREQUENCY, CONFIG_KW, now
from cockpitdecks.event import Event
from cockpitdecks.resources.iconfonts import ICON_FONTS  # to detect ${fa:plane} type of non-sim data

loggerSimdata = logging.getLogger("SimulatorData")
# loggerSimdata.setLevel(SPAM_LEVEL)
# loggerSimdata.setLevel(logging.DEBUG)

loggerInstr = logging.getLogger("Instruction")
# loggerInstr.setLevel(SPAM_LEVEL)
loggerInstr.setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)  # To see when simulator_data are updated
# logger.setLevel(logging.DEBUG)


# ########################################
# Dataref
#
# "internal" simulator_data (not exported to X-Plane) start with that prefix
COCKPITDECKS_DATA_PREFIX = "data:"
INTERNAL_STATE_PREFIX = "state:"
BUTTON_VARIABLE_PREFIX = "button:"
PREFIX_SEP = ":"

# https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Regular_expressions/Cheatsheet
# ${ ... }: dollar + anything between curly braces, but not start with state: or button: prefix
# ?: does not return capturing group
PATTERN_DOLCB = "\\${([^\\}]+?)}"  # ${ ... }: dollar + anything between curly braces.
PATTERN_INTSTATE = f"\\${{{INTERNAL_STATE_PREFIX}([^\\}}]+?)}}"
PATTERN_BUTTONVAR = f"\\${{{BUTTON_VARIABLE_PREFIX}([^\\}}]+?)}}"


class SimulatorDataType(Enum):
    INTEGER = "int"
    FLOAT = "float"
    BYTE = "byte"
    STRING = "string"
    ARRAY_INTEGERS = "array_int"
    ARRAY_FLOATS = "array_float"
    ARRAY_BYTES = "array_byte"


# ########################################
# Dataref
#
# A value in the simulator
class SimulatorData(ABC):
    def __init__(self, name: str, data_type: str = "float"):
        self.name = name
        self.data_type = SimulatorDataType(data_type)
        self.physical_unit = None

        # Stats
        self._last_updated = None
        self._last_changed = None
        self._updated = 0  # number of time value updated
        self._changed = 0  # number of time value changed

        # value
        self._round = None
        self._update_frequency = DEFAULT_FREQUENCY  # sent by the simulator that many times per second.
        self._writable = False  # this is a cockpitdecks specific attribute, not an X-Plane meta data

        self._previous_value = None  # raw values
        self._current_value = None
        self.previous_value = None
        self.current_value: Any | None = None
        self.current_array: List[float] = []

        self._sim = None

        self.listeners: List[SimulatorDataListener] = []  # buttons using this simulator_data, will get notified if changes.

    @staticmethod
    def might_be_simulator_data(path: str) -> bool:
        # ${state:button-value} is not a simulator data, BUT ${data:path} is a "local" simulator data
        # At the end, we are not sure it is a dataref, but wea re sure non-datarefs are excluded ;-)
        PREFIX = list(ICON_FONTS.keys()) + [INTERNAL_STATE_PREFIX[:-1], BUTTON_VARIABLE_PREFIX[:-1]]
        for start in PREFIX:
            if path.startswith(start + PREFIX_SEP):
                return False
        return path != CONFIG_KW.FORMULA.value

    @staticmethod
    def is_internal_simulator_data(path: str) -> bool:
        return path.startswith(COCKPITDECKS_DATA_PREFIX)

    @property
    def is_internal(self) -> bool:
        return self.name.startswith(COCKPITDECKS_DATA_PREFIX)

    @property
    def is_string(self) -> bool:
        return self.data_type == SimulatorDataType.STRING

    @property
    def rounding(self):
        return self._round

    @rounding.setter
    def rounding(self, rounding):
        self._round = rounding

    @property
    def update_frequency(self):
        return self._update_frequency

    @update_frequency.setter
    def update_frequency(self, frequency: int | float = DEFAULT_FREQUENCY):
        if frequency is not None and type(frequency) in [int, float]:
            self._update_frequency = frequency
        else:
            self._update_frequency = DEFAULT_FREQUENCY

    @property
    def writable(self) -> bool:
        return self._writable

    @writable.setter
    def writable(self, writable: bool):
        self._writable = writable

    def has_changed(self):
        if self.previous_value is None and self.current_value is None:
            return False
        elif self.previous_value is None and self.current_value is not None:
            return True
        elif self.previous_value is not None and self.current_value is None:
            return True
        return self.current_value != self.previous_value

    def value(self):
        return self.current_value

    def update_value(self, new_value, cascade: bool = False) -> bool:
        # returns whether has changed

        def local_round(new_value):
            return round(new_value, self._round) if self._round is not None and type(new_value) in [int, float] else new_value

        self._previous_value = self._current_value  # raw
        self._current_value = new_value  # raw
        self.previous_value = self.current_value  # exposed
        if self.is_string:
            self.current_value = new_value
        else:
            self.current_value = local_round(new_value)
        self._updated = self._updated + 1
        self._last_updated = now()
        # self.notify_updated()
        if self.has_changed():
            self._changed = self._changed + 1
            self._last_changed = now()
            loggerSimdata.log(
                SPAM_LEVEL,
                f"dataref {self.name} updated {self.previous_value} -> {self.current_value}",
            )
            if cascade:
                self.notify()
            return True
        # loggerSimdata.error(f"dataref {self.name} updated")
        return False

    def add_listener(self, obj):
        if not isinstance(obj, SimulatorDataListener):
            loggerSimdata.warning(f"{self.name} not a listener {obj}")
        if obj not in self.listeners:
            self.listeners.append(obj)
        loggerSimdata.debug(f"{self.name} added listener ({len(self.listeners)})")

    def notify(self):
        for lsnr in self.listeners:
            lsnr.simulator_data_changed(self)
            if hasattr(lsnr, "page") and lsnr.page is not None:
                loggerSimdata.log(
                    SPAM_LEVEL,
                    f"{self.name}: notified {lsnr.page.name}/{lsnr.name}",
                )
            else:
                loggerSimdata.log(
                    SPAM_LEVEL,
                    f"{self.name}: notified {lsnr.name} (not on an page)",
                )

    def save(self):
        pass


class SimulatorDataListener(ABC):
    # To get notified when a simulator data has changed.

    def __init__(self, name: str = "abstract-simulator-data-listener"):
        self.name = name

    @abstractmethod
    def simulator_data_changed(self, data: SimulatorData):
        pass


# "Internal" data, same properties as the simulator data
# but does not get forwarded to the simulator
# Mistakenly sometimes called an internal dataref... (historical)
class CockpitdecksData(SimulatorData):

    def __init__(self, path: str, is_string: bool = False):
        # Data
        if not path.startswith(COCKPITDECKS_DATA_PREFIX):
            path = COCKPITDECKS_DATA_PREFIX + path
        SimulatorData.__init__(self, name=path, data_type="string" if is_string else "float")


# ########################################
# Command
#
class Instruction(ABC):
    """An Instruction is sent to the Simulator to execute an action."""

    def __init__(self, name: str, delay: float = 0.0, condition: str | None = None, button: "Button" | None = None) -> None:
        super().__init__()
        self.name = name

        self.delay = delay
        self.condition = condition

        self._button = button

        self._timer = None

    @abstractmethod
    def _execute(self, simulator: Simulator):
        self.clean_timer()

    @property
    def button(self):
        return self._button

    @button.setter
    def button(self, button):
        self._button = button

    def can_execute(self) -> bool:
        if self.condition is None:
            return True
        if self._button is None:
            loggerInstr.warning(f"instruction {self.name} has condition but no button")
            return True  # no condition
        value = self._button._value.execute_formula(self.condition)
        loggerInstr.debug(f"instruction {self.name}: {self.condition} = {value} ({value != 0})")
        return value != 0

    def clean_timer(self):
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def execute(self, simulator: Simulator):
        if not self.can_execute():
            loggerInstr.debug(f"{self.name} not allowed to run")
            return
        if self._timer is None and self.delay > 0:
            self._timer = threading.Timer(self.delay, self._execute, args=[simulator])
            self._timer.start()
            loggerInstr.debug(f"{self.name} will be executed in {self.delay} secs")
            return
        self._execute(simulator=simulator)


class MacroInstruction(Instruction):
    """
    A Button activation will instruct the simulator software to perform an action.
    A Command is the message that the simulation sofware is expecting to perform that action.
    """

    def __init__(self, name: str, instructions: dict):
        Instruction.__init__(self, name=name)
        self.instructions = instructions
        self._instructions = []
        self.init()

    def __str__(self) -> str:
        return self.name + f"({', '.join([c.name for c in self._instructions])}"

    @property
    def button(self):
        return self._button

    @button.setter
    def button(self, button):
        self._button = button
        for instruction in self._instructions:
            instruction._button = button

    def init(self):
        pass

    def _execute(self, simulator: Simulator):
        for instruction in self._instructions:
            instruction.execute(simulator)


# ########################################
# Simulator
#
class Simulator(ABC):
    """
    Abstract class for execution of operations and collection of data in the simulation software.
    """

    def __init__(self, cockpit, environ):
        self._inited = False
        self._environ = environ
        self.name = type(self).__name__
        self.cockpit = cockpit
        self.running = False

        # This is really the database of all simulator_data
        self.all_simulator_data = {}

        self.simulator_data_to_monitor = {}  # simulator data and number of objects monitoring

        self.roundings = {}  # name: int
        self.simulator_data_frequencies = {}  # name: int

        self._startup = True

        self.cockpit.set_logging_level(__name__)

    @property
    def api_url(self):
        return None

    def set_simulator_data_roundings(self, simulator_data_roundings):
        self.roundings = self.roundings | simulator_data_roundings

    def get_rounding(self, simulator_data_name: str) -> float | None:
        if not simulator_data_name.find("[") > 0:
            return self.roundings.get(simulator_data_name)
        rnd = self.roundings.get(simulator_data_name)
        return (
            rnd if rnd is not None else self.roundings.get(simulator_data_name[: simulator_data_name.find("[")] + "[*]")
        )  # rounds all simulator_data in array ("dref[*]")

    def set_rounding(self, simulator_data):
        if simulator_data.name.find("[") > 0:
            rnd = self.roundings.get(simulator_data.name)
            if rnd is not None:
                simulator_data.rounding = rnd  # rounds this very priecise simulator_data
            else:
                idx = simulator_data.name.find("[")
                base = simulator_data.name[:idx]
                rnd = self.roundings.get(base + "[*]")  # rounds all simulator_data in array, explicit
                if rnd is not None:
                    simulator_data.rounding = rnd  # rounds this very priecise simulator_data
                # rnd = self.roundings.get(base)        # rounds all simulator_data in array
                # if rnd is not None:
                #   simulator_data.rounding = rnd     # rounds this very priecise simulator_data
        else:
            simulator_data.rounding = self.roundings.get(simulator_data.name)

    def set_simulator_data_frequencies(self, simulator_data_frequencies):
        self.simulator_data_frequencies = self.simulator_data_frequencies | simulator_data_frequencies

    def set_frequency(self, simulator_data):
        if simulator_data.name.find("[") > 0:
            freq = self.simulator_data_frequencies.get(simulator_data.name)
            if freq is not None:
                simulator_data.update_frequency = freq  # rounds this very priecise simulator_data
            else:
                idx = simulator_data.name.find("[")
                base = simulator_data.name[:idx]
                freq = self.simulator_data_frequencies.get(base + "[*]")  # rounds all simulator_data in array, explicit
                if freq is not None:
                    simulator_data.update_frequency = freq  # rounds this very priecise simulator_data
                # rnd = self.roundings.get(base)        # rounds all simulator_data in array
                # if rnd is not None:
                #   simulator_data.rounding = rnd     # rounds this very priecise simulator_data
        else:
            simulator_data.update_frequency = self.simulator_data_frequencies.get(simulator_data.name)

    def register(self, simulator_data):
        if simulator_data.name is None:
            logger.warning(f"invalid simulator_data path {simulator_data.name}")
            return None
        if simulator_data.name not in self.all_simulator_data:
            simulator_data._sim = self
            self.set_rounding(simulator_data)
            self.set_frequency(simulator_data)
            self.all_simulator_data[simulator_data.name] = simulator_data
        else:
            logger.debug(f"simulator_data path {simulator_data.name} already registered")
        return simulator_data

    def datetime(self, zulu: bool = False, system: bool = False) -> datetime:
        """Returns the simulator date and time"""
        return datetime.now().astimezone()

    def get_simulator_data_value(self, simulator_data, default=None):
        d = self.all_simulator_data.get(simulator_data)
        if d is None:
            logger.warning(f"{simulator_data} not found")
            return None
        return d.current_value if d.current_value is not None else default

    # ################################
    # Cockpit interface
    #
    def clean_simulator_data_to_monitor(self):
        self.simulator_data_to_monitor = {}

    def add_simulator_data_to_monitor(self, simulator_data: dict):
        prnt = []
        for d in simulator_data.values():
            if d.name.startswith(COCKPITDECKS_DATA_PREFIX):
                logger.debug(f"local simulator_data {d.name} is not monitored")
                continue
            if d.name not in self.simulator_data_to_monitor.keys():
                self.simulator_data_to_monitor[d.name] = 1
                prnt.append(d.name)
            else:
                self.simulator_data_to_monitor[d.name] = self.simulator_data_to_monitor[d.name] + 1
        logger.debug(f"added {prnt}")
        logger.debug(f"currently monitoring {self.simulator_data_to_monitor}")

    def remove_simulator_data_to_monitor(self, simulator_data):
        prnt = []
        for d in simulator_data.values():
            if d.name.startswith(COCKPITDECKS_DATA_PREFIX):
                logger.debug(f"local simulator_data {d.name} is not monitored")
                continue
            if d.name in self.simulator_data_to_monitor.keys():
                self.simulator_data_to_monitor[d.name] = self.simulator_data_to_monitor[d.name] - 1
                if self.simulator_data_to_monitor[d.name] == 0:
                    prnt.append(d.name)
                    del self.simulator_data_to_monitor[d.name]
            else:
                if not self._startup:
                    logger.warning(f"simulator_data {d.name} not monitored")
        logger.debug(f"removed {prnt}")
        logger.debug(f"currently monitoring {self.simulator_data_to_monitor}")

    def remove_all_simulator_data(self):
        logger.debug(f"removing..")
        self.all_simulator_data = {}
        self.simulator_data_to_monitor = {}
        logger.debug(f"..removed")

    def execute(self, instruction: Instruction):
        instruction.execute(self)

    @abstractmethod
    def runs_locally(self) -> bool:
        return False

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def terminate(self):
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

    def info(self):
        return super().info() | {"sim": self.sim.name}

    def enqueue(self):
        if self.sim is not None:
            self.sim.cockpit.event_queue.put(self)
        else:
            logger.warning("no simulator")
