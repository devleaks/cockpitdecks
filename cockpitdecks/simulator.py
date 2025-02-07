# Base classes for interface with the simulation software
#
from __future__ import annotations
import logging

from datetime import datetime
from typing import Any
from abc import ABC, abstractmethod

from cockpitdecks import CONFIG_KW, __version__
from cockpitdecks.event import Event
from cockpitdecks.variable import Variable, VariableFactory, ValueProvider, VariableListener, InternalVariable, INTERNAL_DATA_PREFIX, InternalVariableType
from cockpitdecks.instruction import InstructionFactory, Instruction, NoOperation

loggerSimdata = logging.getLogger("SimulatorVariable")
# loggerSimdata.setLevel(SPAM_LEVEL)
# loggerSimdata.setLevel(logging.DEBUG)

loggerInstr = logging.getLogger("Instruction")
# loggerInstr.setLevel(SPAM_LEVEL)
# loggerInstr.setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)  # To see when simulator_variable are updated
# logger.setLevel(logging.DEBUG)


# ########################################
# Simulator
#
class Simulator(ABC, InstructionFactory, VariableFactory):
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

        self.providers = []  # list of simulator providers to collect variables from

        self.simulator_variable_to_monitor = {}  # simulator data and number of objects monitoring

        self.roundings = {}  # name: int
        self.frequencies = {}  # name: int
        self.physics = {}  # name: physical_unit

        self._startup = True

        self.cockpit.set_logging_level(__name__)
        self.register_permanently_monitored_simulator_variables_provider(provider=self)

    def get_id(self):
        return self.name

    @property
    def api_url(self) -> str | None:
        return None

    def get_version(self) -> list:
        return [f"{type(self).__name__} {__version__}"]

    def get_variables(self) -> set:
        return set()

    # Simulator variable pre-processing
    def set_simulator_variable_roundings(self, simulator_variable_roundings: dict):
        self.roundings = self.roundings | simulator_variable_roundings

    def set_simulator_variable_frequencies(self, simulator_variable_frequencies: dict):
        self.frequencies = self.frequencies | simulator_variable_frequencies

    def set_simulator_variable_physics(self, simulator_variable_physics: dict):
        self.physics = self.physics | simulator_variable_physics

    def get_rounding(self, simulator_variable_name: str) -> float | None:
        if not simulator_variable_name.find("[") > 0:
            return self.roundings.get(simulator_variable_name)
        rnd = self.roundings.get(simulator_variable_name)
        return (
            rnd if rnd is not None else self.roundings.get(simulator_variable_name[: simulator_variable_name.find("[")] + "[*]")
        )  # rounds all simulator_variable in array ("dref[*]")

    def set_rounding(self, simulator_variable: SimulatorVariable):
        if simulator_variable.name.find("[") > 0:
            rnd = self.roundings.get(simulator_variable.name)
            if rnd is not None:
                simulator_variable.rounding = rnd  # rounds this very priecise simulator_variable
            else:
                idx = simulator_variable.name.find("[")
                base = simulator_variable.name[:idx]
                rnd = self.roundings.get(base + "[*]")  # rounds all simulator_variable in array, explicit
                if rnd is not None:
                    simulator_variable.rounding = rnd  # rounds this very priecise simulator_variable
                # rnd = self.roundings.get(base)        # rounds all simulator_variable in array
                # if rnd is not None:
                #   simulator_variable.rounding = rnd     # rounds this very priecise simulator_variable
        else:
            simulator_variable.rounding = self.roundings.get(simulator_variable.name)

    def set_frequency(self, simulator_variable: SimulatorVariable):
        if simulator_variable.name.find("[") > 0:
            freq = self.frequencies.get(simulator_variable.name)
            if freq is not None:
                simulator_variable.update_frequency = freq  # rounds this very priecise simulator_variable
            else:
                idx = simulator_variable.name.find("[")
                base = simulator_variable.name[:idx]
                freq = self.frequencies.get(base + "[*]")  # rounds all simulator_variable in array, explicit
                if freq is not None:
                    simulator_variable.update_frequency = freq  # rounds this very priecise simulator_variable
                # rnd = self.roundings.get(base)        # rounds all simulator_variable in array
                # if rnd is not None:
                #   simulator_variable.rounding = rnd     # rounds this very priecise simulator_variable
        else:
            simulator_variable.update_frequency = self.frequencies.get(simulator_variable.name)

    def set_physics(self, variable: Variable):
        if variable.name.find("[") > 0:
            unit = self.physics.get(variable.name)
            if unit is not None:
                variable.physical_unit = unit
            else:
                idx = variable.name.find("[")
                base = variable.name[:idx]
                unit = self.physics.get(base + "[*]")
                if unit is not None:
                    variable.physical_unit = unit
        else:
            variable.physical_unit = self.physics.get(variable.name, "")

    # ################################
    # Simulator variables
    #
    def datetime(self, zulu: bool = False, system: bool = False) -> datetime:
        """Returns the current simulator date and time"""
        return datetime.now().astimezone()

    def register_permanently_monitored_simulator_variables_provider(self, provider):
        if provider not in self.providers:
            self.providers.append(provider)

    def get_permanently_monitored_simulator_variables(self) -> dict:
        dtdrefs = {}
        for provider in self.providers:
            cnt = 0
            for d in provider.get_variables():
                if d in dtdrefs:
                    logger.info(f"{d} already added")
                    continue
                if d.startswith(CONFIG_KW.STRING_PREFIX.value):
                    d = d.replace(CONFIG_KW.STRING_PREFIX.value, "")
                    dtdrefs[d] = self.get_variable(d, is_string=True)
                else:
                    dtdrefs[d] = self.get_variable(d)
                dtdrefs[d].add_listener(provider)
                cnt = cnt + 1
            logger.info(f"adding {cnt} permanent variables from {provider.name}")
        return dtdrefs

    def variable_factory(self, name: str, is_string: bool = False) -> Variable:
        # here is the place to inject a physical type if any, may be from a list
        # like for roundings and frequencies?
        # dataref-physical:
        #     sim/cockpit/autopilot/heading: degrees
        #     sim/weather/region/wind_altitude_msl_m[*]: meter
        #     sim/weather/region/wind_direction_degt[*]: degree
        #     sim/weather/region/wind_speed_msc[*]: meter/second
        # ...
        physical_unit = self.physics.get(name)
        variable = SimulatorVariable(name=name, data_type="string" if is_string else "float", physical_unit=physical_unit)
        variable._sim = self
        return variable

    def register(self, variable: Variable) -> Variable:
        """Registers a SimulatorVariable to be monitored by Cockpitdecks.

        Args:
            simulator_variable ([type]): [description]

        Returns:
            [type]: [description]
        """
        if variable.name is None:
            logger.warning(f"invalid variable name {variable.name}")
            return None
        if not self.cockpit.variable_database.exists(variable.name):
            variable._sim = self
            self.set_rounding(variable)
            self.set_frequency(variable)
            self.cockpit.variable_database.register(variable)
        else:
            logger.debug(f"variable name {variable.name} already registered")
        return variable

    def get_variable(self, name: str, is_string: bool = False) -> InternalVariable | SimulatorVariable:
        """Returns data or create a new one, internal if path requires it"""
        if self.cockpit.variable_database.exists(name):
            t = self.cockpit.variable_database.get(name)
            if t.is_string != is_string:
                logger.warning(f"variable {name} has wrong type {t.data_type} vs. is_string={is_string}")
                if is_string:
                    t.data_type = InternalVariableType.STRING
                    logger.warning(f"variable {name} type forced to string" + " *" * 10)
            return t
        if Variable.is_internal_variable(path=name):
            t = self.cockpit.variable_database.register(variable=self.cockpit.variable_factory(name=name, is_string=is_string))
            if t.is_string != is_string:
                logger.warning(f"variable {name} has wrong type {t.data_type} vs. is_string={is_string}")
                if is_string:
                    t.data_type = InternalVariableType.STRING
                    logger.warning(f"variable {name} type forced to string" + " *" * 10)
            return t
        t = self.cockpit.variable_database.register(variable=self.variable_factory(name=name, is_string=is_string))
        if t.is_string != is_string:
            logger.warning(f"variable {name} has wrong type {t.data_type} vs. is_string={is_string}")
            if is_string:
                t.data_type = InternalVariableType.STRING
                logger.warning(f"variable {name} type forced to string" + " *" * 10)
        return t

    def get_simulator_variable_value(self, simulator_variable, default=None) -> Any | None:
        """Gets the value of a SimulatorVariable monitored by Cockpitdecks
        Args:
            simulator_variable ([type]): [description]
            default ([type]): [description] (default: `None`)

        Returns:
            [type]: [description]
        """
        return self.cockpit.variable_database.value(name=simulator_variable, default=default)

    def get_internal_variable(self, name: str, is_string: bool = False) -> Variable:
        """Returns the InternalVariable or creates it if it is the first time it is accessed.
        Args:
            name (str): [description]
            is_string (bool): [description] (default: `False`)

        Returns:
            [type]: [description]
        """
        return self.get_variable(name=Variable.internal_variable_name(name), is_string=is_string)

    def set_internal_variable(self, name: str, value: float, cascade: bool):
        """Sets the value of an InternalVariable. If the data does not exist, it is created first."""
        if not Variable.is_internal_variable(path=name):
            name = Variable.internal_variable_name(path=name)
        data = self.get_variable(name=name)
        data.update_value(new_value=value, cascade=cascade)

    def inc_internal_variable(self, name: str, amount: float, cascade: bool = False):
        """Incretement an InternalVariable
        Args:
            name (str): [description]
            amount (float): [description]
            cascade (bool): [description] (default: `False`)
        """
        data = self.get_internal_variable(name=name)
        curr = data.value()
        if curr is None:
            curr = 0
        newvalue = curr + amount
        self.set_internal_variable(name=name, value=newvalue, cascade=cascade)

    def inc(self, path: str, amount: float = 1.0, cascade: bool = False):
        """Increment a SimulatorVariable

        Args:
            path (str): [description]
            amount (float): [description] (default: `1.0`)
            cascade (bool): [description] (default: `False`)
        """
        # shortcut alias
        self.inc_internal_variable(name=path, amount=amount, cascade=cascade)

    # ################################
    # Factories
    #
    @abstractmethod
    def replay_event_factory(self, name: str, value):
        """Recreates an Event from data included in the value.

        Args:
            name (str): [description]
            value ([type]): [description]
        """
        pass

    # ################################
    # Cockpit interface
    #
    def clean_simulator_variable_to_monitor(self):
        """Removes all data from Simulator monitoring."""
        self.simulator_variable_to_monitor = {}

    def add_simulator_variables_to_monitor(self, simulator_variables: dict, reason: str = None):
        """Adds supplied data to Simulator monitoring."""
        prnt = []
        for d in simulator_variables.values():
            if d.name.startswith(INTERNAL_DATA_PREFIX):
                logger.debug(f"local simulator_variable {d.name} is not monitored")
                continue
            if d.name not in self.simulator_variable_to_monitor.keys():
                self.simulator_variable_to_monitor[d.name] = 1
                prnt.append(d.name)
            else:
                self.simulator_variable_to_monitor[d.name] = self.simulator_variable_to_monitor[d.name] + 1
        logger.debug(f"added {prnt}")
        logger.debug(f"currently monitoring {self.simulator_variable_to_monitor}")

    def remove_simulator_variables_to_monitor(self, simulator_variables: dict, reason: str = None):
        """Removes supplied data from Simulator monitoring."""
        prnt = []
        for d in simulator_variables.values():
            if d.name.startswith(INTERNAL_DATA_PREFIX):
                logger.debug(f"local simulator_variable {d.name} is not monitored")
                continue
            if d.name in self.simulator_variable_to_monitor.keys():
                self.simulator_variable_to_monitor[d.name] = self.simulator_variable_to_monitor[d.name] - 1
                if self.simulator_variable_to_monitor[d.name] == 0:
                    prnt.append(d.name)
                    del self.simulator_variable_to_monitor[d.name]
            else:
                if not self._startup:
                    logger.warning(f"simulator_variable {d.name} not monitored")
        logger.debug(f"removed {prnt}")
        logger.debug(f"currently monitoring {self.simulator_variable_to_monitor}")

    def remove_all_simulator_variable(self):
        """Removes all data from Simulator."""
        logger.debug("removing..")
        self.cockpit.variable_database.remove_all_simulator_variables()
        self.simulator_variable_to_monitor = {}
        logger.debug("..removed")

    def execute(self, instruction: Instruction):
        """Executes a SimulatorInstruction"""
        instruction.execute(self)

    @abstractmethod
    def runs_locally(self) -> bool:
        """Returns whether Cockpitdecks runs on the same computer as the Simulator software"""
        return False

    @abstractmethod
    def start(self):
        """Starts Cockpitdecks Simulator class, that is start data monitoring and instruction
        execution if instructed to do so.
        """
        pass

    @abstractmethod
    def terminate(self):
        """Terminates Cockpitdecks Simulator class, stop monitoring SimulatorVariable and stop issuing
        instructionsto the simulator..
        """
        pass


class NoSimulator(Simulator):
    """Dummy place holder Simulator class for demonstration purposes"""

    name = "NoSimulator"

    def __init__(self, cockpit, environ):
        Simulator.__init__(self, cockpit, environ)

    def instruction_factory(self, **kwargs) -> Instruction:
        # logger.warning("NoSimulator executes no instruction")
        logger.debug(f"({kwargs})")
        return NoOperation(kwargs=kwargs)

    def add_simulator_variables_to_monitor(self, simulator_variables: dict, reason: str | None = None):
        logger.warning("NoSimulator monitors no data")

    def remove_simulator_variables_to_monitor(self, simulator_variables: dict, reason: str | None = None):
        logger.warning("NoSimulator monitors no data")

    def replay_event_factory(self, name: str, value):
        pass

    def runs_locally(self) -> bool:
        return True

    def connect(self):
        logger.info("simulator connected")

    def start(self):
        logger.info("simulator started")

    def terminate(self):
        logger.info("simulator terminated")


# ########################################
# SimulatorVariable
#
# A value in the simulator
class SimulatorVariable(Variable):
    """A specialised variable to monitor in the simulator"""

    def __init__(self, name: str, data_type: str = "float", physical_unit: str = ""):
        Variable.__init__(self, name=name, data_type=data_type, physical_unit=physical_unit)

    # def __init__(self, name: str, is_string: bool = False):
    #     Variable.__init__(self, name=name, data_type="string" if is_string else "float")


class SimulatorVariableListener(VariableListener):
    # To get notified when a simulator data has changed.

    def __init__(self, name: str = "abstract-simulator-data-listener"):
        VariableListener.__init__(self, name=name)

    def variable_changed(self, data: Variable):
        if isinstance(data, SimulatorVariable):
            self.simulator_variable_changed(data=data)
        else:
            logger.warning(f"non simulator variable for listener ({data.name}, {type(data)}), ignored")

    @abstractmethod
    def simulator_variable_changed(self, data: SimulatorVariable):
        raise NotImplementedError


# ########################################
# SimulatorInstruction
#
# A instruction sent to the simulator
class SimulatorInstruction(Instruction):
    """
    An Instruction to be submitted to and performed by the simulator:
    """

    def __init__(self, name: str, simulator: Simulator, delay: float = 0.0, condition: str | None = None) -> None:
        Instruction.__init__(self, name=name, delay=delay, condition=condition, performer=simulator)
        self._simulator = simulator

    @property
    def simulator(self):
        return self._simulator

    @simulator.setter
    def cockpit(self, simulator):
        self._simulator = simulator

    def _check_condition(self) -> bool:
        # condition checked in each individual instruction
        if self.condition is None:
            return True
        return self._condition.value() != 0

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
                delay=c.get(CONFIG_KW.DELAY.value, 0),  # !! very important to add default value to delay
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
            sim (Simulator): Simulator that produced the event
            autorun (bool): Whether to run the event
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


class SimulatorVariableEvent(SimulatorEvent):
    """Data Update Event"""

    def __init__(self, sim: Simulator, name: str, value: float | str, cascade: bool, autorun: bool = True):
        """Dataref Update Event.

        Args:
        """
        self.name = name
        self.value = value
        self.cascade = cascade
        SimulatorEvent.__init__(self, sim=sim, autorun=autorun)

    def __str__(self):
        return f"{self.sim.name}:{self.name}={self.value}:{self.timestamp}"

    def info(self):
        return super().info() | {"path": self.name, "value": self.value, "cascade": self.cascade}

    def run(self, just_do_it: bool = False) -> bool:
        if just_do_it:
            if self.sim is None:
                logger.warning("no simulator")
                return False
            data = self.cockpit.variable_database.get(self.name)
            if data is None:
                logger.debug(f"dataref {self.name} not found in database")
                return False
            try:
                logger.debug(f"updating {data.name}..")
                self.handling()
                data.update_value(self.value, cascade=self.cascade)
                self.handled()
                logger.debug(f"..updated")
            except:
                logger.warning(f"..updated with error", exc_info=True)
                return False
        else:
            self.enqueue()
            logger.debug(f"enqueued")
        return True


class SimulatorVariableValueProvider(ABC, ValueProvider):
    def __init__(self, name: str, simulator: Simulator):
        ValueProvider.__init__(self, name=name, provider=simulator)

    @abstractmethod
    def get_simulator_variable_value(self, simulator_variable, default=None):
        pass
