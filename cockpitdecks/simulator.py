# Base classes for interface with the simulation software
#
from __future__ import annotations
import threading
import logging
import base64
import json
from datetime import datetime
from typing import List, Any, Tuple
from abc import ABC, abstractmethod
from random import randint
import requests

from cockpitdecks import SPAM_LEVEL, now, CONFIG_KW, DEFAULT_FREQUENCY
from cockpitdecks.event import Event
from .resources.iconfonts import ICON_FONTS

loggerDataref = logging.getLogger("Dataref")
# loggerDataref.setLevel(SPAM_LEVEL)
# loggerDataref.setLevel(logging.DEBUG)

loggerInstr = logging.getLogger("Instruction")
# loggerInstr.setLevel(SPAM_LEVEL)
loggerInstr.setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)  # To see when dataref are updated
# logger.setLevel(logging.DEBUG)


# ########################################
# Dataref
#
# "internal" datarefs (not exported to X-Plane) start with that prefix
INTERNAL_DATAREF_PREFIX = "data:"
INTERNAL_STATE_PREFIX = "state:"
BUTTON_VARIABLE_PREFIX = "button:"
PREFIX_SEP = ":"

# https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Regular_expressions/Cheatsheet
# ${ ... }: dollar + anything between curly braces, but not start with state: or button: prefix
# ?: does not return capturing group
PATTERN_DOLCB = "\\${([^\\}]+?)}"  # ${ ... }: dollar + anything between curly braces.
PATTERN_INTDREF = f"\\${{{INTERNAL_DATAREF_PREFIX}([^\\}}]+?)}}"
PATTERN_INTSTATE = f"\\${{{INTERNAL_STATE_PREFIX}([^\\}}]+?)}}"
PATTERN_BUTTONVAR = f"\\${{{BUTTON_VARIABLE_PREFIX}([^\\}}]+?)}}"

# REST API model keywords
REST_DATA = "data"
REST_IDENT = "id"


# ########################################
# Dataref
#
# A value in the simulator
class Dataref:
    """
    A Dataref is an internal value of the simulation software made accessible to outside modules,
    plugins, or other software in general.

    From Spring 2024 on, this is no longer inspired from Sandy Barbour and the like in Python 2.
    Most of the original code has been removed, because unused.
    This is a modern implementation, specific to Cockpitdecks. It even use X-Plane 12.1 REST/WebSocket API.
    """

    def __init__(self, path: str, is_string: bool = False):
        # Data
        self.path = path  # some/path/values[6]
        self.is_string = is_string

        self.dataref = path  # some/path/values
        self.index = 0  # 6
        if "[" in path:  # sim/some/values[4]
            self.dataref = self.path[: self.path.find("[")]
            self.index = int(self.path[self.path.find("[") + 1 : self.path.find("]")])

        self._round = None
        self._update_frequency = DEFAULT_FREQUENCY  # sent by the simulator that many times per second.
        self._writable = False  # this is a cockpitdecks specific attribute, not an X-Plane meta data
        self._xpindex = None
        self._req_id = 0

        # Stats
        self._last_updated = None
        self._last_changed = None
        self._updated = 0  # number of time value updated
        self._changed = 0  # number of time value changed

        # value
        self._previous_value = None  # raw values
        self._current_value = None
        self.previous_value = None
        self.current_value: Any | None = None
        self.current_array: List[float] = []

        self._sim = None

        self.listeners: List[DatarefListener] = []  # buttons using this dataref, will get notified if changes.

    @staticmethod
    def get_dataref_type(path) -> Tuple[str, str]:
        if len(path) > 3 and path[-2:-1] == ":" and path[-1] in "difsb":  # decimal, integer, float, string, byte(s)
            return path[:-2], path[-1]
        return path, "f"

    @staticmethod
    def is_internal_dataref(path: str) -> bool:
        return path.startswith(INTERNAL_DATAREF_PREFIX)

    @staticmethod
    def mk_internal_dataref(path: str) -> str:
        return INTERNAL_DATAREF_PREFIX + path

    @staticmethod
    def might_be_dataref(path: str) -> bool:
        # ${state:button-value} is not a dataref, BUT ${data:path} is a "local" dataref
        # Not sure it is a dataref, but sure non-datarefs are excluded ;-)
        PREFIX = list(ICON_FONTS.keys()) + [INTERNAL_STATE_PREFIX[:-1], BUTTON_VARIABLE_PREFIX[:-1]]
        for start in PREFIX:
            if path.startswith(start + PREFIX_SEP):
                return False
        return path != CONFIG_KW.FORMULA.value

    @property
    def is_internal(self) -> bool:
        return Dataref.is_internal_dataref(self.path)

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
            loggerDataref.log(
                SPAM_LEVEL,
                f"dataref {self.path} updated {self.previous_value} -> {self.current_value}",
            )
            if cascade:
                self.notify()
            return True
        # loggerDataref.error(f"dataref {self.path} updated")
        return False

    def add_listener(self, obj):
        if not isinstance(obj, DatarefListener):
            loggerDataref.warning(f"{self.dataref} not a listener {obj}")
        if obj not in self.listeners:
            self.listeners.append(obj)
        loggerDataref.debug(f"{self.dataref} added listener ({len(self.listeners)})")

    def notify(self):
        for lsnr in self.listeners:
            lsnr.dataref_changed(self)
            if hasattr(lsnr, "page") and lsnr.page is not None:
                loggerDataref.log(
                    SPAM_LEVEL,
                    f"{self.path}: notified {lsnr.page.name}/{lsnr.name}",
                )
            else:
                loggerDataref.log(
                    SPAM_LEVEL,
                    f"{self.path}: notified {lsnr.name} (not on an page)",
                )

    @property
    def writable(self) -> bool:
        return self._writable

    @writable.setter
    def writable(self, writable: bool):
        self._writable = writable

    def save(self) -> bool:
        if self._writable:
            if not self.is_internal:
                return self._sim.write_dataref(dataref=self.path, value=self.value())
        else:
            loggerDataref.warning(f"{self.dataref} not writable")
        return False

    # ##############
    # REST API INTERFACE
    #
    # NOT GENERIC ONLY WORKS FOR SCALAR VALUES, NOT ARRAYS
    #
    def get_specs(self, simulator: Simulator) -> dict | None:
        api_url = simulator.api_url
        if api_url is None:
            logger.warning("no api url")
            return None
        payload = {"filter[name]": self.path}
        api_url = f"{api_url}/datarefs"
        response = requests.get(api_url, params=payload)
        resp = response.json()
        if REST_DATA in resp:
            return resp[REST_DATA][0]
        logger.error(resp)
        return None

    def get_index(self, simulator: Simulator) -> int | None:
        if self._xpindex is not None:
            return self._xpindex
        data = self.get_specs(simulator=simulator)
        if data is not None and REST_IDENT in data:
            self._xpindex = int(data[REST_IDENT])
            return self._xpindex
        logger.error(f"could not get dataref specifications for {self.path} ({data})")
        return None

    def get_value(self, simulator: Simulator):
        api_url = simulator.api_url
        if api_url is None:
            logger.warning("no api url")
            return None
        if self._xpindex is None:
            idx = self.get_index(simulator=simulator)
            if idx is None:
                logger.error("could not get XP index")
                return None
        url = f"{api_url}/datarefs/{self._xpindex}/value"
        response = requests.get(url)
        data = response.json()
        if REST_DATA in data:
            if self.is_string:
                if type(data[REST_DATA]) in [str, bytes]:
                    return base64.b64decode(data[REST_DATA])[:-1].decode("ascii")
                else:
                    logger.warning(f"value for {self.path} ({data}) is not a string")
            return data[REST_DATA]
        logger.error(f"could not get value for {self.path} ({data})")
        return None

    def set_value(self, simulator: Simulator):
        api_url = simulator.api_url
        if api_url is None:
            logger.warning("no api url")
            return None
        if self._xpindex is None:
            idx = self.get_index(simulator=simulator)
            if idx is None:
                logger.error("could not get XP index")
                return None
        url = f"{api_url}/datarefs/{self._xpindex}/value"
        value = self.current_value
        if value is not None and (self.is_string):
            value = base64.b64encode(bytes(str(self.current_value), "ascii")).decode("ascii")
        data = {"data": value}
        response = requests.patch(url=url, data=data)
        if response.status_code != 200:
            logger.error(f"could not set value for {self.path} ({data}, {response})")

    def ws_subscribe(self, ws):
        self._req_id = randint(100000, 1000000)
        request = {"req_id": self._req_id, "type": "dataref_subscribe_values", "params": {"datarefs": [{"id": self._xpindex}]}}
        ws.send(json.dumps(request))

    def ws_unsubscribe(self, ws):
        request = {"req_id": self._req_id, "type": "dataref_unsubscribe_values", "params": {"datarefs": [{"id": self._xpindex}]}}
        ws.send(json.dumps(request))

    def ws_callback(self, response) -> bool:
        # gets called by websocket onmessage on receipt.
        # 1. Ignore response with result unless error
        # 2. Get data
        # 3. Cascade if changed
        if "req_id" in response:
            if response.get("req_id") != self._req_id:
                return False
        # do something
        return True

    def ws_update(self, ws):
        request = {"req_id": 1, "type": "dataref_set_values", "params": {"datarefs": [{"id": self._xpindex, "value": self.current_value}]}}
        ws.send(json.dumps(request))

    def auto_collect(self):
        if self.collector is None:
            e = DatarefEvent(sim=self, dataref=self.path, value=self.get_value(), cascade=True)
            self.collector = threading.Timer(self.update_frequency, self.auto_collect)

    def cancel_autocollect(self):
        if self.collector is not None:
            self.collector.cancel()
            self.collector = None


class DatarefListener(ABC):
    # To get notified when a dataref has changed.

    def __init__(self, name: str = "abstract-dataref-listener"):
        self.name = name

    @abstractmethod
    def dataref_changed(self, dataref):
        pass


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


class Instruction(ABC):
    """An Instruction is sent to the Simulator to execute some action.

    [description]
    """

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

    @classmethod
    def new(cls, name, **kwargs):
        for keyw in ["view", "command"]:
            if keyw in kwargs:
                cmdargs = kwargs.get(keyw)
                if type(cmdargs) is str:
                    if kwargs.get("longpress", False):
                        return BeginEndCommand(name=name, path=cmdargs, delay=kwargs.get("delay", 0.0), condition=kwargs.get("condition"))
                    else:
                        return Command(name=name, path=cmdargs, delay=kwargs.get("delay", 0.0), condition=kwargs.get("condition"))
                elif type(cmdargs) in [list, tuple]:
                    return MacroCommand(name=name, commands=cmdargs)
        if "set_dataref" in kwargs:
            cmdargs = kwargs.get("set_dataref")
            if type(cmdargs) is str:
                return SetDataref(
                    name=name,
                    path=cmdargs,
                    value=kwargs.get("value"),
                    formula=kwargs.get("formula"),
                    delay=kwargs.get("delay"),
                    condition=kwargs.get("condition"),
                )
        else:
            loggerInstr.warning(f"Instruction {name}: invalid argument {kwargs}")
        return None

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


class Command(Instruction):
    """
    A Button activation will instruct the simulator software to perform an action.
    A Command is the message that the simulation sofware is expecting to perform that action.
    """

    def __init__(self, path: str | None, name: str | None = None, delay: float = 0.0, condition: str | None = None):
        Instruction.__init__(self, name=name, delay=delay, condition=condition)
        self.path = path  # some/command

    def __str__(self) -> str:
        return self.name if self.name is not None else (self.path if self.path is not None else "no command")

    def is_valid(self) -> bool:
        return self.path is not None and not self.path.lower() in NOT_A_COMMAND

    def _execute(self, simulator: Simulator):
        simulator.execute_command(command=self)
        self.clean_timer()


class BeginEndCommand(Command):
    """
    A Button activation will instruct the simulator software to perform an action.
    A Command is the message that the simulation sofware is expecting to perform that action.
    """

    def __init__(self, path: str | None, name: str | None = None, delay: float = 0.0, condition: str | None = None):
        Command.__init__(self, path=path, name=name, delay=0.0, condition=condition)  # force no delay for commandBegin/End
        self.is_on = False

    def _execute(self, simulator: Simulator):
        if self.is_on:
            simulator.command_end(command=self)
            self.is_on = False
        else:
            simulator.command_begin(command=self)
            self.is_on = True
        self.clean_timer()


class SetDataref(Instruction):
    """
    A Button activation will instruct the simulator software to perform an action.
    A Command is the message that the simulation sofware is expecting to perform that action.
    """

    def __init__(self, path: str, value: any | None = None, formula: str | None = None, delay: float = 0.0, condition: str | None = None):
        Instruction.__init__(self, name=path, delay=delay, condition=condition)
        self.path = path  # some/command
        self.formula = None  # = formula: later, a set-dataref specific formula, different from the button one?
        self._value = value

    def __str__(self) -> str:
        return "set-dataref: " + self.name

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self._value = value

    def compute_value(self):
        if self._button is not None:
            return self._button.value.execute_formula(self.formula)
        loggerInstr.warning(f"SetDataref {name}: no button")
        return None

    def _execute(self, simulator: Simulator):
        if self.formula is not None:
            self._value = self.compute_value()
        simulator.write_dataref(dataref=self.path, value=self.value)


class MacroCommand(Instruction):
    """
    A Button activation will instruct the simulator software to perform an action.
    A Command is the message that the simulation sofware is expecting to perform that action.
    """

    def __init__(self, name: str, commands: dict):
        Instruction.__init__(self, name=name)
        self.commands = commands
        self._commands = []
        self.init()

    def __str__(self) -> str:
        return self.name + f"({', '.join([c.name for c in self._commands])}"

    @property
    def button(self):
        return self._button

    @button.setter
    def button(self, button):
        self._button = button
        for command in self._commands:
            command._button = button

    def init(self):
        self._commands = []
        for c in self.commands:
            if CONFIG_KW.COMMAND.value in c:
                if CONFIG_KW.SET_DATAREF.value in c:
                    loggerInstr.warning(f"Macro command {self.name}: command has both command and set-dataref, ignored")
                    continue
                self._commands.append(
                    Command(path=c.get(CONFIG_KW.COMMAND.value), delay=c.get(CONFIG_KW.DELAY.value, 0.0), condition=c.get(CONFIG_KW.CONDITION.value))
                )
            elif CONFIG_KW.SET_DATAREF.value in c:
                self._commands.append(
                    SetDataref(path=c.get(CONFIG_KW.SET_DATAREF.value), delay=c.get(CONFIG_KW.DELAY.value, 0.0), condition=c.get(CONFIG_KW.CONDITION.value))
                )

    def _execute(self, simulator: Simulator):
        for command in self._commands:
            command.execute(simulator)


# ########################################
# Simulator
#
class Simulator(ABC):
    """
    Abstract class for execution of operations and collection of data in the simulation software.
    """

    DEFAULT_REQ_FREQUENCY = DEFAULT_FREQUENCY

    def __init__(self, cockpit, environ):
        self._inited = False
        self._environ = environ
        self.name = type(self).__name__
        self.cockpit = cockpit
        self.running = False

        # This is really the database of all datarefs
        self.all_datarefs = {}

        self.datarefs_to_monitor = {}  # dataref path and number of objects monitoring

        self.dataref_db_lock = threading.RLock()

        self.roundings = {}  # path: int
        self.dataref_frequencies = {}  # path: int

        self._startup = True

        self.cockpit.set_logging_level(__name__)

    @property
    def api_url(self):
        return None

    def set_roundings(self, roundings):
        self.roundings = self.roundings | roundings

    def get_rounding(self, dataref_path: str) -> float | None:
        if not dataref_path.find("[") > 0:
            return self.roundings.get(dataref_path)
        rnd = self.roundings.get(dataref_path)
        return rnd if rnd is not None else self.roundings.get(dataref_path[: dataref_path.find("[")] + "[*]")  # rounds all datarefs in array ("dref[*]")

    def set_dataref_frequencies(self, dataref_frequencies):
        self.dataref_frequencies = self.dataref_frequencies | dataref_frequencies

    def set_rounding(self, dataref):
        if dataref.path.find("[") > 0:
            rnd = self.roundings.get(dataref.path)
            if rnd is not None:
                dataref.rounding = rnd  # rounds this very priecise dataref
            else:
                idx = dataref.path.find("[")
                base = dataref.path[:idx]
                rnd = self.roundings.get(base + "[*]")  # rounds all datarefs in array, explicit
                if rnd is not None:
                    dataref.rounding = rnd  # rounds this very priecise dataref
                # rnd = self.roundings.get(base)        # rounds all datarefs in array
                # if rnd is not None:
                #   dataref.rounding = rnd     # rounds this very priecise dataref
        else:
            dataref.rounding = self.roundings.get(dataref.path)

    def set_frequency(self, dataref):
        if dataref.path.find("[") > 0:
            freq = self.dataref_frequencies.get(dataref.path)
            if freq is not None:
                dataref.update_frequency = freq  # rounds this very priecise dataref
            else:
                idx = dataref.path.find("[")
                base = dataref.path[:idx]
                freq = self.dataref_frequencies.get(base + "[*]")  # rounds all datarefs in array, explicit
                if freq is not None:
                    dataref.update_frequency = freq  # rounds this very priecise dataref
                # rnd = self.roundings.get(base)        # rounds all datarefs in array
                # if rnd is not None:
                #   dataref.rounding = rnd     # rounds this very priecise dataref
        else:
            dataref.update_frequency = self.dataref_frequencies.get(dataref.path)

    def register(self, dataref):
        if dataref.path is None:
            logger.warning(f"invalid dataref path {dataref.path}")
            return None
        if dataref.path not in self.all_datarefs:
            dataref._sim = self
            self.set_rounding(dataref)
            self.set_frequency(dataref)
            self.all_datarefs[dataref.path] = dataref
        else:
            logger.debug(f"dataref path {dataref.path} already registered")
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
    def runs_locally(self) -> bool:
        return False

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
    def command_once(self, command: Command):
        pass

    @abstractmethod
    def command_begin(self, command: Command):
        pass

    @abstractmethod
    def command_end(self, command: Command):
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


class DatarefEvent(SimulatorEvent):
    """Dataref Update Event"""

    def __init__(self, sim: Simulator, dataref: str, value: float | str, cascade: bool, autorun: bool = True):
        """Dataref Update Event.

        Args:
        """
        self.dataref_path = dataref
        self.value = value
        self.cascade = cascade
        SimulatorEvent.__init__(self, sim=sim, autorun=autorun)

    def __str__(self):
        return f"{self.sim.name}:{self.dataref_path}={self.value}:{self.timestamp}"

    def info(self):
        return super().info() | {"path": self.dataref_path, "value": self.value, "cascade": self.cascade}

    def run(self, just_do_it: bool = False) -> bool:
        if just_do_it:
            if self.sim is None:
                logger.warning("no simulator")
                return False
            dataref = self.sim.all_datarefs.get(self.dataref_path)
            if dataref is None:
                logger.debug(f"dataref {self.dataref_path} not found in database")
                return

            try:
                logger.debug(f"updating {dataref.path}..")
                self.handling()
                dataref.update_value(self.value, cascade=self.cascade)
                self.handled()
                logger.debug(f"..updated")
            except:
                logger.warning(f"..updated with error", exc_info=True)
                return False
        else:
            self.enqueue()
            logger.debug(f"enqueued")
        return True
