# Base classes for interface with the simulation software
#
from __future__ import annotations
import threading
import logging
from datetime import datetime
from typing import List, Any
from abc import ABC, abstractmethod
from enum import Enum

from cockpitdecks.event import Event
from cockpitdecks.data import Data, DataListener, COCKPITDECKS_DATA_PREFIX
from cockpitdecks.instruction import Instruction
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
class Simulator(ABC):
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
    def instruction_factory(self, name, **kwargs):
        pass

    @abstractmethod
    def replay_event_factory(self, name: str, value):
        pass

    @abstractmethod
    def simulator_data_factory(self, name: str, data_type: str = "float", physical_unit: str = "") -> SimulatorData:
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

    def _execute(self):
        logger.warning(f"Abstract method cannot execute instruction {self.name}")


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
