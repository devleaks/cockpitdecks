# Base classes for interface with the simulation software
#
from __future__ import annotations
import logging
from enum import Enum
from abc import ABC, abstractmethod

from cockpitdecks import SPAM_LEVEL, DEFAULT_FREQUENCY, CONFIG_KW, now
from cockpitdecks.resources.iconfonts import ICON_FONTS  # to detect ${fa:plane} type of non-sim data

logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)  # To see when simulator_data are updated
# logger.setLevel(logging.DEBUG)


# ########################################
# Data conventions
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


class CockpitdecksDataType(Enum):
    INTEGER = "int"
    FLOAT = "float"
    BYTE = "byte"
    STRING = "string"
    ARRAY_INTEGERS = "array_int"
    ARRAY_FLOATS = "array_float"
    ARRAY_BYTES = "array_byte"


class Data(ABC):
    """An Data is a typed value holder for Cockpitdecks.
    Value is alive, it changes, gets updated, notifies those who depend on it, etc.
    """

    def __init__(self, name: str, data_type: str = "float", physical_unit: str = ""):
        self.name = name
        self.data_type = CockpitdecksDataType(data_type)
        self.physical_unit = physical_unit

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

        self.listeners: List[DataListener] = []  # buttons using this simulator_data, will get notified if changes.

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
        return self.data_type == CockpitdecksDataType.STRING

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
            logger.log(
                SPAM_LEVEL,
                f"dataref {self.name} updated {self.previous_value} -> {self.current_value}",
            )
            if cascade:
                self.notify()
            return True
        # logger.error(f"dataref {self.name} updated")
        return False

    def add_listener(self, obj):
        if not isinstance(obj, DataListener):
            logger.warning(f"{self.name} not a listener {obj}")
        if obj not in self.listeners:
            self.listeners.append(obj)
        logger.debug(f"{self.name} added listener ({len(self.listeners)})")

    def remove_listener(self, obj):
        if not isinstance(obj, DataListener):
            logger.warning(f"{self.name} not a listener {obj}")
        if obj in self.listeners:
            self.listeners.remove(obj)
        logger.debug(f"{self.name} removed listener ({len(self.listeners)})")

    def notify(self):
        for lsnr in self.listeners:
            lsnr.simulator_data_changed(self)
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
        pass


class DataListener(ABC):
    # To get notified when a simulator data has changed.

    def __init__(self, name: str = "abstract-data-listener"):
        self.name = name

    @abstractmethod
    def data_changed(self, data: Data):
        pass


# "Internal" data, same properties as the simulator data
# but does not get forwarded to the simulator
# Mistakenly sometimes called an internal dataref... (historical)
class CockpitdecksData(Data):

    def __init__(self, path: str, is_string: bool = False):
        # Data
        if not path.startswith(COCKPITDECKS_DATA_PREFIX):
            path = COCKPITDECKS_DATA_PREFIX + path
        Data.__init__(self, name=path, data_type="string" if is_string else "float")
