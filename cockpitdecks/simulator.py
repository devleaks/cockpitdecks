# Base classes for interface with the simulation software
#
from __future__ import annotations
import threading
import logging
import re

from datetime import datetime
from typing import List, Any
from abc import ABC, abstractmethod
from enum import Enum

from cockpitdecks import CONFIG_KW, __version__
from cockpitdecks.event import Event
from cockpitdecks.data import Data, DataListener, COCKPITDECKS_DATA_PREFIX, PATTERN_DOLCB
from cockpitdecks.instruction import InstructionProvider, Instruction
from cockpitdecks.resources.rpc import RPC
from cockpitdecks.resources.iconfonts import ICON_FONTS  # to detect ${fa:plane} type of non-sim data

loggerSimdata = logging.getLogger("SimulatorData")
# loggerSimdata.setLevel(SPAM_LEVEL)
# loggerSimdata.setLevel(logging.DEBUG)

loggerInstr = logging.getLogger("Instruction")
# loggerInstr.setLevel(SPAM_LEVEL)
# loggerInstr.setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)  # To see when simulator_data are updated
# logger.setLevel(logging.DEBUG)


# ########################################
# Simulator
#
class SimulatorDataProvider:

    def simulator_data_factory(self, name: str, data_type: str = "float", physical_unit: str = "") -> SimulatorData:
        raise NotImplementedError("Please implement SimulatorDataProvider.simulator_data_factory method")


class Simulator(ABC, InstructionProvider, SimulatorDataProvider):
    """
    Abstract class for execution of operations and collection of data in the simulation software.
    """

    name = "SimulatorABC"

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
    def api_url(self) -> str | None:
        return None

    def get_version(self) -> list:
        return [f"{type(self).__name__} {__version__}"]

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
    # Factories
    #
    @abstractmethod
    def replay_event_factory(self, name: str, value):
        pass

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


# ########################################
# SimulatorData
#
# A value in the simulator
class SimulatorData(Data):
    def __init__(self, name: str, data_type: str = "float", physical_unit: str = ""):
        Data.__init__(self, name=name, data_type=data_type, physical_unit=physical_unit)


class SimulatorDataListener(DataListener):
    # To get notified when a simulator data has changed.

    def __init__(self, name: str = "abstract-simulator-data-listener"):
        DataListener.__init__(self, name=name)

    def data_changed(self, data: Data):
        if isinstance(data, SimulatorData):
            return self.simulator_data_changed(data=data)
        logger.warning(f"invalid data type for listener {type(data)}")
        return None

    @abstractmethod
    def simulator_data_changed(self, data: SimulatorData):
        pass


# ########################################
# SimulatorInstruction
#
# A instruction sent to the simulator
class SimulatorInstruction(Instruction):
    """
    An Instruction to be submitted to and performed by the simulator:
    """

    def __init__(self, name: str, simulator: Simulator, delay: float = 0.0, condition: str | None = None) -> None:
        Instruction.__init__(self, name=name, delay=delay, condition=condition)
        self._simulator = simulator

    @property
    def simulator(self):
        return self._simulator

    @simulator.setter
    def cockpit(self, simulator):
        self._simulator = simulator

    def get_simulator_data_value(self, simulator_data, default=None):
        return self._simulator.get_simulator_data_value(simulator_data=simulator_data, default=default)

    def substitute_dataref_values(self, message: str | int | float, default: str = "0.0", formatting=None):
        """
        Replaces ${dataref} with value of dataref in labels and execution formula.
        @todo: should take into account dataref value type (Dataref.xp_data_type or Dataref.data_type).
        """
        if type(message) is int or type(message) is float:  # probably formula is a constant value
            value_str = message
            if formatting is not None:
                if formatting is not None:
                    value_str = formatting.format(message)
                    logger.debug(f"value {self.name}:received int or float, returning as is.")
                else:
                    value_str = str(message)
                    logger.debug(f"value {self.name}:received int or float, returning formatted {formatting}.")
            return value_str

        dataref_names = re.findall(PATTERN_DOLCB, message)

        if len(dataref_names) == 0:
            logger.debug(f"value {self.name}:no dataref to substitute.")
            return message

        if formatting is not None:
            if type(formatting) is list:
                if len(dataref_names) != len(formatting):
                    logger.warning(
                        f"value {self.name}:number of datarefs {len(dataref_names)} not equal to the number of format {len(formatting)}, cannot proceed."
                    )
                    return message
            elif type(formatting) is not str:
                logger.warning(f"value {self.name}:single format is not a string, cannot proceed.")
                return message

        retmsg = message
        cnt = 0
        for dataref_name in dataref_names:
            value = self.get_simulator_data_value(simulator_data=dataref_name)
            value_str = ""
            if formatting is not None and value is not None:
                if type(formatting) is list:
                    value_str = formatting[cnt].format(value)
                elif formatting is not None and type(formatting) is str:
                    value_str = formatting.format(value)
            else:
                value_str = str(value) if value is not None else str(default)  # default gets converted in float sometimes!
            retmsg = retmsg.replace(f"${{{dataref_name}}}", value_str)
            logger.debug(f"substitute_dataref_values {dataref_name} = {value_str}{' (default)' if value is not None else ''}")
            cnt = cnt + 1

        more = re.findall(PATTERN_DOLCB, retmsg)  # XXXHERE
        if len(more) > 0:
            logger.warning(f"value {self.name}:unsubstituted dataref values {more}")

        return retmsg

    def _check_condition(self) -> bool:
        # condition checked in each individual instruction
        if self.condition is None:
            return True
        expr = self.substitute_dataref_values(message=self.condition)
        logger.debug(f"value {self.name}: {self.condition} => {expr}")
        r = RPC(expr)
        value = r.calculate()
        logger.debug(f"execute_formula: value {self.name}: {self.condition} => {expr} => {value}")
        return value != 0

    def _execute(self):
        raise NotImplementedError(f"Please implement SimulatorInstruction._execute method ({self.name})")


class SimulatorMacroInstruction(SimulatorInstruction):
    """A Macro Instruction is a collection of individual Instruction.
    Each instruction comes with its condition for execution and delay since activation.
    (Could have been called Instructions (plural form))
    """

    def __init__(self, name: str, simulator: Simulator, instructions: dict):
        SimulatorInstruction.__init__(self, name=name, simulator=simulator)
        self.instructions = instructions
        self._instructions = []
        self.init()

    def __str__(self) -> str:
        return self.name + f" ({', '.join([c.name for c in self._instructions])}"

    def init(self):
        total_delay = 0
        for c in self.instructions:
            total_delay = total_delay + c.get(CONFIG_KW.DELAY.value, 0)
            if total_delay > 0:
                c[CONFIG_KW.DELAY.value] = total_delay
            ci = self._simulator.instruction_factory(
                name=c.get(CONFIG_KW.NAME.value),
                command=c.get(CONFIG_KW.COMMAND.value),
                delay=c.get(CONFIG_KW.DELAY.value),
                condition=c.get(CONFIG_KW.CONDITION.value),
            )
            self._instructions.append(ci)

    def _execute(self):
        for instruction in self._instructions:
            instruction.execute()


# ########################################
# SimulatorEvent
#
# An event from the simulator to Cockpitdecks. With love.
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
