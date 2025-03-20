# Base classes for variables, either internal or from the simulator
#
from __future__ import annotations
import logging
from enum import Enum
from abc import ABC, abstractmethod
from typing import Dict, Any


from cockpitdecks import SPAM_LEVEL, DEFAULT_FREQUENCY, CONFIG_KW, now, yaml
from cockpitdecks.resources.iconfonts import ICON_FONTS  # to detect ${fa:plane} type of non-sim data

logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)  # To see when simulator_variable are updated
# logger.setLevel(logging.DEBUG)


# ########################################
# Variable conventions
#
# "internal" simulator_variable (not exported to X-Plane) start with that prefix
PREFIX_SEP = ":"
INTERNAL_VARIABLE_PREFIX = "data" + PREFIX_SEP
INTERNAL_STATE_PREFIX = "state" + PREFIX_SEP
BUTTON_PREFIX = "button" + PREFIX_SEP

# https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Regular_expressions/Cheatsheet
# ${ ... }: dollar + anything between curly braces, but not start with state: or button: prefix
# ?: does not return capturing group
PATTERN_DOLCB = "\\${([^\\}]+?)}"  # ${ ... }: dollar + anything between curly braces.
PATTERN_INTVAR = f"\\${{{INTERNAL_VARIABLE_PREFIX}([^\\}}]+?)}}"
PATTERN_INTSTATE = f"\\${{{INTERNAL_STATE_PREFIX}([^\\}}]+?)}}"
PATTERN_BUTTONVAR = f"\\${{{BUTTON_PREFIX}([^\\}}]+?)}}"


class InternalVariableType(Enum):
    INTEGER = "int"
    FLOAT = "float"
    BYTE = "byte"
    STRING = "string"
    ARRAY_INTEGERS = "array_int"
    ARRAY_FLOATS = "array_float"
    ARRAY_BYTES = "array_byte"


class Variable(ABC):
    """An Variable is a typed value holder for Cockpitdecks.
    All data are kept inside the Simulator:
       - Simulator Variable
       - Internal Variable
    This eases data mangement, all data is at the same place.
    The value of a data is "alive", it changes, gets updated, notifies those who depend on it, etc.
    """

    def __init__(self, name: str, data_type: str = "float", physical_unit: str = ""):
        self.name = name
        self.data_type = InternalVariableType(data_type)
        self.physical_unit = physical_unit

        # Stats
        self._creator = None
        self._last_updated = None
        self._last_changed = None
        self._updated = 0  # number of time value updated
        self._changed = 0  # number of time value changed

        # value
        self._round = None
        self._update_frequency = DEFAULT_FREQUENCY  # sent by the simulator that many times per second.
        self._writable = False  # this is a cockpitdecks specific attribute, not an X-Plane meta data
        self._format = None

        self._previous_value: Any | None = None  # raw values
        self._current_value: Any | None = None
        self.previous_value: Any | None = None  # rounded and/or formatted value
        self.current_value: Any | None = None
        self.current_array: List[float] = []

        self.listeners: List[VariableListener] = []  # buttons using this simulator_variable, will get notified if changes.

    def __str__(self) -> str:
        return str(self.name)

    # ################################
    # Variable name control and generation
    #
    @staticmethod
    def is_icon(path: str) -> bool:
        return len([font for font in ICON_FONTS if path.startswith(font + ":")]) > 0

    @staticmethod
    def is_internal_variable(path: str) -> bool:
        return path.startswith(INTERNAL_VARIABLE_PREFIX)

    @staticmethod
    def internal_variable_name(path: str) -> str:
        if not Variable.is_internal_variable(path):  # prevent duplicate prepend
            return INTERNAL_VARIABLE_PREFIX + path
        return path  # already startswith INTERNAL_VARIABLE_PREFIX

    @staticmethod
    def internal_variable_root_name(path: str) -> str:
        if Variable.is_internal_variable(path):  # prevent duplicate prepend
            return path[len(INTERNAL_VARIABLE_PREFIX) :]
        return path  # already root name

    @staticmethod
    def is_state_variable(path: str) -> bool:
        return path.startswith(INTERNAL_STATE_PREFIX)

    @staticmethod
    def state_variable_name(path: str) -> str:
        if not Variable.is_state_variable(path):  # prevent duplicate prepend
            return INTERNAL_STATE_PREFIX + path
        return path  # already startswith INTERNAL_STATE_PREFIX

    @staticmethod
    def state_variable_root_name(path: str) -> str:
        if Variable.is_state_variable(path):  # prevent duplicate prepend
            return path[len(INTERNAL_STATE_PREFIX) :]
        return path  # already root name

    @staticmethod
    def may_be_non_internal_variable(path: str) -> bool:
        # ${state:button-value} is not a simulator data, BUT ${data:path} is a "local" simulator data
        # At the end, we are not sure it is a dataref, but we are sure non-datarefs are excluded ;-)
        if Variable.is_internal_variable(path):
            return False
        if Variable.is_state_variable(path):
            return False
        icon_prefixes = [c + PREFIX_SEP for c in ICON_FONTS.keys()]
        PREFIXES = icon_prefixes + [INTERNAL_STATE_PREFIX, BUTTON_PREFIX]
        for start in PREFIXES:
            if path.startswith(start):
                return False
        return path != CONFIG_KW.FORMULA.value and "/" in path and len(path) > 7  # !!  a string for an annunciator is ON/R (4 chars)

    # ################################
    # Deduced behavior
    #
    @property
    def is_internal(self) -> bool:
        return Variable.is_internal_variable(self.name)

    @property
    def is_string(self) -> bool:
        return self.data_type == InternalVariableType.STRING

    # ################################
    # Value control
    #
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

    @property
    def has_value(self) -> bool:
        return self._updated > 0 or self._changed > 0

    def has_changed(self):
        if self.previous_value is None and self.current_value is None:
            return False
        elif self.previous_value is None and self.current_value is not None:
            return True
        elif self.previous_value is not None and self.current_value is None:
            return True
        return self.current_value != self.previous_value

    @property
    def value(self):
        return self.current_value

    @value.setter
    def value(self, value):
        self.current_value = value

    def update_value(self, new_value, cascade: bool = False) -> bool:
        # returns whether has changed
        def local_round(val):
            return round(val, self._round) if self._round is not None and type(val) in [int, float] else val

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
            logger.log(
                SPAM_LEVEL,
                f"variable {self.name} updated {self.previous_value} -> {self.current_value}",
            )
            if cascade:
                self.notify()
            return True
        # logger.error(f"variable {self.name} updated")
        return False

    def value_formatted(self):
        """Format value if format is supplied
        Returns:
            formatted value
        """
        value = self.current_value
        if self._format is not None:
            if type(value) in [int, float]:  # probably formula is a constant value
                value_str = self._format.format(value)
                logger.debug(f"{self.name}: returning formatted {self._format}:  {value_str}.")
                return value_str
            else:
                logger.warning(f"{self.name}: has format string '{self._format}' but value is not a number '{value}'")
        value_str = str(value)
        logger.debug(f"{self.name}: received {value} ({type(value).__name__}), returns as string: '{value_str}'")
        return value_str

    # ################################
    # Listeners
    #
    def add_listener(self, obj):
        if not isinstance(obj, VariableListener):
            logger.warning(f"{self.name} not a listener {obj}")
        if obj not in self.listeners:
            self.listeners.append(obj)
        logger.debug(f"{self.name} added listener ({len(self.listeners)})")

    def remove_listener(self, obj):
        if not isinstance(obj, VariableListener):
            logger.warning(f"{self.name} not a listener {obj}")
        if obj in self.listeners:
            self.listeners.remove(obj)
        logger.debug(f"{self.name} removed listener ({len(self.listeners)})")

    def notify(self):
        for lsnr in self.listeners:
            lsnr.variable_changed(self)
            if hasattr(lsnr, "page") and lsnr.page is not None:
                logger.log(
                    SPAM_LEVEL,
                    f"{self.name}: notified {lsnr.page.name}/{lsnr.name}",
                )
            else:
                logger.log(
                    SPAM_LEVEL,
                    f"{self.name}: notified {lsnr.name} (not on an page)",
                )

    def save(self):
        # raise NotImplementedError
        # logger.warning(f"{self.name} nothing to save")
        pass


class VariableListener(ABC):
    """A VariableListener is an entity that is interested in being notified
    when a data changes.
    """

    def __init__(self, name: str = "abstract-data-listener"):
        self.vl_name = name

    @abstractmethod
    def variable_changed(self, data: Variable):
        raise NotImplementedError


class VariableFactory:
    """A VariableFactory has a function to generate variable for its own use."""

    @abstractmethod
    def variable_factory(self, name: str, is_string: bool = False, creator: str = None) -> Variable:
        raise NotImplementedError


class InternalVariable(Variable):
    """A InternalVariable is a data internal to Cockpitdecks.
    It is used internally, but it can be used by Value.
    """

    def __init__(self, name: str, is_string: bool = False):
        if not Variable.is_internal_variable(name):
            name = Variable.internal_variable_name(name)
        Variable.__init__(self, name=name, data_type="string" if is_string else "float")


class ValueProvider:
    """Any value: Either a variable value (internal, simulator)
    but also button, activation or internal state value.
    """

    def __init__(self, name: str, provider):
        self._provider = provider


class InternalVariableValueProvider(ABC, ValueProvider):
    def __init__(self, name: str, cockpit: Cockpit):
        ValueProvider.__init__(self, name=name, provider=cockpit)

    @abstractmethod
    def get_internal_variable_value(self, name: str):
        pass


class VariableDatabase:
    """Container for all variables.

    In the past, it was stored into the simulator.
    It is now stored in the Cockpit and caontains both Simulator and Internal variables.

    """

    def __init__(self) -> None:
        self.database: Dict[str, Variable] = {}

    def register(self, variable: Variable) -> Variable:
        if variable.name is None:
            logger.warning(f"invalid variable name {variable.name}, not stored")
            return variable
        if Variable.is_state_variable(variable.name):
            logger.warning(f"invalid variable name {variable.name}, this is a state, not stored")
            return variable
        if variable.name not in self.database:
            self.database[variable.name] = variable
        else:
            logger.debug(f"variable {variable.name} already registered")
        return variable

    def exists(self, name: str) -> bool:
        return name in self.database

    def get(self, name: str) -> Variable | None:
        if not self.exists(name):
            logger.debug(f"variable {name} not found")
        return self.database.get(name)

    def value_of(self, name: str, default: Any = None) -> Any | None:
        v = self.get(name)
        if v is None:
            logger.warning(f"{name} not found")
            return None
        return v.current_value if v.current_value is not None else default

    def show_all(self, word: str = None):
        for k in self.database:
            if word is None or word in k:
                logger.debug(f"{k} = {self.value_of(k)}")

    def remove_all_simulator_variables(self):
        to_delete = []
        for d in self.database:
            if Variable.may_be_non_internal_variable(d):  # type(variable) is Dataref
                to_delete.append(d)
        for d in to_delete:
            self.database.pop(d)

    def dump(self, filename: str = "variable-database-dump.yaml"):
        drefs = {d.name: d.value for d in self.database.values()}  #  if d.is_internal
        with open(filename, "w") as fp:
            yaml.dump(drefs, fp)
            logger.debug(f"simulator data values saved in {filename} file")
