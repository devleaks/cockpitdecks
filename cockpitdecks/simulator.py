# Base classes for interface with the simulation software
#
from __future__ import annotations
import logging

from datetime import datetime
from typing import Any, List
from abc import ABC, abstractmethod

from cockpitdecks import __version__
from cockpitdecks.event import Event
from cockpitdecks.strvar import Formula
from cockpitdecks.variable import (
    InternalVariable,
    InternalVariableType,
    ValueProvider,
    Variable,
    VariableFactory,
    VariableListener,
)
from cockpitdecks.instruction import InstructionFactory, Instruction, NoOperation, InstructionPerformer
from cockpitdecks.activity import Activity, ActivityListener

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
class Simulator(ABC, InstructionFactory, InstructionPerformer, VariableFactory, ValueProvider):
    """
    Abstract class for execution of operations and collection of data in the simulation software.
    """

    name = "SimulatorABC"

    def __init__(self, cockpit, environ):
        self._inited = False
        self._environ = environ
        self._observables: "Observables" | None = None
        self.name = type(self).__name__
        self.cockpit = cockpit

        self.running = False
        self._startup = True

        self.roundings = {}  # name: int
        self.frequencies = {}  # name: int
        self.physics = {}  # name: physical_unit

        # Internal properties
        self.simulator_variable_to_monitor = {}  # simulator data and number of objects monitoring
        self.simulator_event_to_monitor = {}  # simulator event and number of objects monitoring

        self.cockpit.set_logging_level(__name__)

    def get_id(self):
        return self.name

    # @property
    # def api_url(self) -> str | None:
    #     return None

    def get_version(self) -> list:
        return [f"{type(self).__name__} {__version__}"]

    def get_variables(self) -> set:
        return set()

    def get_activities(self) -> set:
        return set()

    # Simulator variable pre-processing
    def set_simulator_variable_roundings(self, simulator_variable_roundings: dict):
        self.roundings = self.roundings | simulator_variable_roundings

    def set_simulator_variable_frequencies(self, simulator_variable_frequencies: dict):
        self.frequencies = self.frequencies | simulator_variable_frequencies

    def set_simulator_variable_physics(self, simulator_variable_physics: dict):
        self.physics = self.physics | simulator_variable_physics

    def get_rounding(self, simulator_variable_name: str) -> float | None:
        # 1. plain path: sim/some/values[4]
        rnd = self.roundings.get(simulator_variable_name)
        if rnd is not None:
            return rnd
        # 2. for arrays, all element can use same rounding
        if "[" in simulator_variable_name:
            root_name = simulator_variable_name[: simulator_variable_name.find("[")]  # sim/some/values
            rnd = self.roundings.get(root_name)
            if rnd is not None:
                return rnd
            root_name = root_name + "[*]"  # sim/some/values[*]
            rnd = self.roundings.get(root_name)
            if rnd is not None:
                return rnd
        return None

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

    def variable_factory(self, name: str, is_string: bool = False, creator: str | None = None) -> Variable:
        # here is the place to inject a physical type if any, may be from a list
        # like for roundings and frequencies?
        # dataref-physical:
        #     sim/cockpit/autopilot/heading: degrees
        #     sim/weather/region/wind_altitude_msl_m[*]: meter
        #     sim/weather/region/wind_direction_degt[*]: degree
        #     sim/weather/region/wind_speed_msc[*]: meter/second
        # ...
        physical_unit = self.physics.get(name)
        variable = SimulatorVariable(name=name, simulator=self, data_type="string" if is_string else "float", physical_unit=physical_unit)
        self.set_rounding(variable)
        self.set_frequency(variable)
        if creator is not None:
            variable._creator = creator
        return variable

    def instruction_factory(self, name: str, instruction_block: dict) -> SimulatorInstruction:
        raise NotImplementedError

    def register(self, variable: Variable) -> Variable:
        """Registers a SimulatorVariable to be monitored by Cockpitdecks.

        Args:
            variable (Variable): Variable to register

        Returns:
            Variable: Registered variable
        """
        if variable.name is None:
            logger.warning(f"invalid variable name {variable.name}")
            return None
        if not self.cockpit.variable_database.exists(variable.name):
            variable.simulator = self
            self.set_rounding(variable)
            self.set_frequency(variable)
            self.cockpit.variable_database.register(variable)
        else:
            logger.debug(f"variable name {variable.name} already registered")
        return variable

    def get_variable(self, name: str, is_string: bool = False) -> InternalVariable | SimulatorVariable:
        """Returns data or create a new one, internal if path requires it

        Important note: is_string has precedence over whatever type has the variable.
        If is_string is true, and the variable is not of type string, it is forced to type string.
        This is (probably) due to a first request to create the variable without being able to determine its data type.
        Then later, another request to create the variable happens with the proper requested type, so we adjust it.
        Parent objects always know what data type their variable is. (float is default, string is explicit.)
        """
        stars = 4
        if self.cockpit.variable_database.exists(name):
            t = self.cockpit.variable_database.get(name)
            if is_string and t.is_string != is_string:
                logger.warning(f"variable {name} has type {t.data_type} vs. is_string={is_string} (create={t._creator}), forced to string" + " *" * stars)
                t.data_type = InternalVariableType.STRING
            return t
        if Variable.is_internal_variable(path=name):
            t = self.cockpit.variable_database.register(variable=self.cockpit.variable_factory(name=name, is_string=is_string, creator=self.name))
            if is_string and t.is_string != is_string:
                logger.warning(f"variable {name} has type {t.data_type} vs. is_string={is_string} (create={t._creator}), forced to string" + " *" * stars)
                t.data_type = InternalVariableType.STRING
            return t
        t = self.cockpit.variable_database.register(variable=self.variable_factory(name=name, is_string=is_string, creator=self.name))
        if is_string and t.is_string != is_string:
            logger.warning(f"variable {name} has type {t.data_type} vs. is_string={is_string} (create={t._creator}), forced to string" + " *" * stars)
            t.data_type = InternalVariableType.STRING
        return t

    def get_simulator_variable_value(self, simulator_variable: SimulatorVariable, default=None) -> Any | None:
        """Gets the value of a SimulatorVariable monitored by Cockpitdecks
        Args:
            simulator_variable (SimulatorVariable): Variable to get the value from.
            default (Any): DEfault value if variable value is None.

        Returns:
            [type]: [description]
        """
        return self.cockpit.variable_database.value_of(name=simulator_variable, default=default)

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
        curr = data.value
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
    def activity_factory(self, name: str, creator: str = None) -> Activity:
        """Returns data or create a new internal variable"""
        activity = SimulatorActivity(simulator=self, name=name)
        if creator is not None:
            activity._creator = creator
        return activity

    @abstractmethod
    def replay_event_factory(self, name: str, value):
        """Recreates an Event from data included in the value.

        Args:
            name (str): Name of event to replay
            value (Any): value of event to replay
        """
        pass

    # ################################
    # Cockpit interface
    #
    #
    # Variables
    def clean_simulator_variable_to_monitor(self):
        """Removes all data from Simulator monitoring."""
        self.simulator_variable_to_monitor = {}

    def add_simulator_variables_to_monitor(self, simulator_variables: dict, reason: str = None):
        """Adds supplied data to Simulator monitoring."""
        prnt = []
        for d in simulator_variables.values():
            if Variable.is_internal_variable(d.name):
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
            if Variable.is_internal_variable(d.name):
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
        self.clean_simulator_variable_to_monitor()
        logger.debug("..removed")

    #
    # Observables
    # @property
    # def observables(self) -> list:
    #     # This is the collection of "permanent" observables (coded)
    #     # and simulator observables (in <simulator base>/resources/observables.yaml)
    #     return []
    @property
    def observables(self) -> list:
        # This is the collection of "permanent" observables (coded)
        # and simulator observables (in <simulator base>/resources/observables.yaml)
        if self._observables is not None:
            if hasattr(self._observables, "observables"):
                return self._observables.observables
            elif type(self._observables) is list:
                return self._observables
            else:
                logger.warning(f"observables: {type(self._observables)} unknown")
        return []

    def load_observables(self):
        if self._observables is not None:
            return
        fn = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", RESOURCES_FOLDER, OBSERVABLES_FILE))
        if os.path.exists(fn):
            config = {}
            with open(fn, "r") as fp:
                config = yaml.load(fp)
            self._observables = Observables(config=config, simulator=self)
            logger.info(f"loaded {len(self._observables.observables)} simulator observables")
        else:
            logger.info("no simulator observables")

    #
    # Events
    def clean_simulator_event_to_monitor(self):
        """Removes all data from Simulator monitoring."""
        self.simulator_event_to_monitor = {}

    def add_simulator_events_to_monitor(self, simulator_events: set, reason: str = None):
        """Adds supplied data to Simulator monitoring."""
        prnt = []
        for d in simulator_events:
            if d not in self.simulator_event_to_monitor.keys():
                self.simulator_event_to_monitor[d] = 1
                prnt.append(d)
            else:
                self.simulator_event_to_monitor[d] = self.simulator_event_to_monitor[d] + 1
        logger.debug(f"added {prnt}")
        logger.debug(f"currently monitoring {self.simulator_event_to_monitor}")

    def remove_simulator_events_to_monitor(self, simulator_events: set, reason: str = None):
        """Removes supplied data from Simulator monitoring."""
        prnt = []
        for d in simulator_events:
            if d in self.simulator_event_to_monitor:
                self.simulator_event_to_monitor[d] = self.simulator_event_to_monitor[d] - 1
                if self.simulator_event_to_monitor[d] == 0:
                    prnt.append(d)
                    del self.simulator_event_to_monitor[d]
            else:
                if not self._startup:
                    logger.warning(f"simulator_event {d} not monitored")
        logger.debug(f"removed {prnt}")
        logger.debug(f"currently monitoring {self.simulator_event_to_monitor}")

    def remove_all_simulator_event(self):
        """Removes all data from Simulator."""
        logger.debug("removing..")
        self.clean_simulator_event_to_monitor()
        logger.debug("..removed")

    #
    # Instructions
    # def execute(self, instruction: Instruction):
    #     """Executes a SimulatorInstruction"""
    #     instruction.execute(self)

    # def execute_instruction(self, instruction: Instruction):
    #     """Executes a SimulatorInstruction"""
    #     instruction.execute(self)

    @abstractmethod
    def aircraft_changed(self):
        pass

    @abstractmethod
    def is_night(self) -> bool:
        """Returns whether simulator is night time"""
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

    @property
    def connected(self):
        return False

    def instruction_factory(self, name: str, instruction_block: dict) -> SimulatorInstruction:
        return NoOperation(name=name)  # this is not a SimulatorInstruction, but an instruction, ubt it is OK

    def add_simulator_variables_to_monitor(self, simulator_variables: dict, reason: str | None = None):
        logger.warning("NoSimulator monitors no data")

    def remove_simulator_variables_to_monitor(self, simulator_variables: dict, reason: str | None = None):
        logger.warning("NoSimulator monitors no data")

    def replay_event_factory(self, name: str, value):
        pass

    def is_night(self) -> bool:
        return False

    def connect(self, reload_cache: bool = False):
        logger.info("simulator connected")

    def aircraft_changed(self):
        pass

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

    def __init__(self, name: str, simulator: Simulator, data_type: str = "float", physical_unit: str = ""):
        Variable.__init__(self, name=name, data_type=data_type, physical_unit=physical_unit)
        self.simulator = simulator

    # def __init__(self, name: str, is_string: bool = False):
    #     Variable.__init__(self, name=name, data_type="string" if is_string else "float")


class SimulatorVariableListener(VariableListener):
    # To get notified when a simulator data has changed.

    def __init__(self, name: str = "abstract-simulator-data-listener"):
        VariableListener.__init__(self, name=name)

    def variable_changed(self, data: Variable):
        if isinstance(data, SimulatorVariable) or (isinstance(data, Formula) and data._has_sim_vars):  # could be a formula that has sim vars.
            self.simulator_variable_changed(data=data)
        else:
            logger.warning(f"non simulator variable {data.name} for listener {self.vl_name} ({type(data)}), ignored")

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
        Instruction.__init__(self, name=name, performer=simulator, delay=delay, condition=condition)
        self.simulator = simulator

    def _check_condition(self) -> bool:
        # condition checked in each individual instruction
        if self.condition is None:
            return True
        return self._condition.value != 0

    def _execute(self):
        raise NotImplementedError(f"Please implement SimulatorInstruction._execute method ({self.name})")


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
                logger.warning(f"..updated with error ({self.name}={self.value} ({self.cascade}))", exc_info=True)
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


# ########################################
# SimulatorActivity
#
# Something happens in the simulator and it sent to Cockpitdecks for handling.
# If someont registerd to that 'activity', it gets notified it happened.
class SimulatorActivity(Activity):
    """An activity is something that happened in the simulator."""

    def __init__(self, simulator: Simulator, name: str, value: Any | None = None):
        Activity.__init__(self, name=name, value=value)
        self.sim = Simulator


class SimulatorActivityListener(ActivityListener):
    # To get notified when a simulator data has changed.

    def __init__(self, name: str = "abstract-simulator-activity-listener"):
        ActivityListener.__init__(self, name=name)

    def activity_received(self, activity: Activity):
        # Forward to precise, typed simulator_activity_received()
        if isinstance(activity, SimulatorActivity):
            self.simulator_activity_received(activity=activity)
        else:
            logger.warning(f"non simulator activity for listener ({activity.name}, {type(activity)}), ignored")

    @abstractmethod
    def simulator_activity_received(self, activity: SimulatorActivity):
        raise NotImplementedError
