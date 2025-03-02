from __future__ import annotations
import logging

from cockpitdecks.constant import CONFIG_KW, ID_SEP
from cockpitdecks.simulator import Simulator, SimulatorVariable, SimulatorVariableListener
from cockpitdecks.instruction import MacroInstruction
from cockpitdecks.value import Value

# from cockpitdecks.deck import Deck

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class Observables:
    """Collection of observables from global configuration"""

    def __init__(self, config: dict, simulator: Simulator):
        """Deck event

        Args:
            action (DECK_ACTIONS): Action produced by this event (~ DeckEvent type)
            deck (Deck): Deck that produced the event
        """
        self._config = config
        self.sim = simulator
        self.observables = [Observable(config=c, simulator=self.sim) for c in self._config.get(CONFIG_KW.OBSERVABLES.value)]

    def get_events(self) -> set:
        ret = set()
        for o in self.observables:
            ret = ret | o.get_events()
        return ret

    def get_variables(self) -> set:
        ret = set()
        for o in self.observables:
            ret = ret | o.get_variables()
        return ret

    def get_string_variables(self) -> set:
        ret = set()
        for o in self.observables:
            ret = ret | o.get_string_variables()
        return ret

    def enable(self, name):
        ok = False
        for o in self.observables:
            if o.name == name:
                o.enable()
                ok = True
        if not ok:
            logger.warning(f"observable {name} not found")

    def disable(self, name):
        ok = False
        for o in self.observables:
            if o.name == name:
                o.disable()
                ok = True
        if not ok:
            logger.warning(f"observable {name} not found")

    def get_observable(self, name) -> Observable | None:
        for o in self.observables:
            if o.name == name:
                return o
        return None


class Observable(SimulatorVariableListener):
    """An Observable is a Value that is monitored for changes.
       When the data changes, associated Instructions are performed (in sequence).
    Executes actions in list.
    """

    def __init__(self, config: dict, simulator: Simulator):
        self._config = config
        self.name = config.get(CONFIG_KW.NAME.value, type(self).__name__)
        self.mode = config.get(CONFIG_KW.TYPE.value, CONFIG_KW.TRIGGER.value)
        self.sim = simulator
        self._enabled = config.get(CONFIG_KW.ENABLED.value, False)
        # Create a data "internal:observable:name" is enabled or disabled
        self._enabled_data_name = ID_SEP.join([CONFIG_KW.OBSERVABLE.value, self.name])
        self._enabled_data = self.sim.get_internal_variable(self._enabled_data_name)
        self._enabled_data.update_value(new_value=0)
        self._events = set(config.get(CONFIG_KW.EVENTS.value, set()))
        self._value = Value(name=self.name, config=self._config, provider=simulator)
        self._actions = MacroInstruction(
            name=self.name,
            performer=simulator,
            factory=simulator.cockpit,
            instructions=self._config.get(CONFIG_KW.ACTIONS.value, {}),
        )
        self.init()

    @property
    def value(self):
        """Gets the current value, but does not provoke a calculation, just returns the current value."""
        logger.debug(f"observable {self.name}: {self._value.value()}")
        return self._value.value()

    @value.setter
    def value(self, value):
        logger.debug(f"observable {self.name}: set value to {value}")
        self._value.update_value(new_value=value, cascade=True)

    def has_changed(self) -> bool:
        return self._value.has_changed()

    @property
    def trigger(self):
        return self._config.get(CONFIG_KW.FORMULA.value)

    def enable(self):
        self._enabled = True
        self._enabled_data.update_value(new_value=1, cascade=True)
        logger.info(f"observable {self.name} enabled")

    def disable(self):
        self._enabled = False
        self._enabled_data.update_value(new_value=0, cascade=True)
        logger.info(f"observable {self.name} disabled")

    def init(self):
        # Register simulator variables and ask to be notified
        variables = self.get_string_variables()
        if variables is not None:
            for s in variables:
                ref = self.sim.get_variable(s, is_string=True)
                if ref is not None:
                    ref.add_listener(self)
        logger.debug(f"observable {self.name}: listening to strings variables {variables}")

        variables = self.get_variables()
        v = []
        if variables is not None:
            for s in variables:
                ref = self.sim.get_variable(s)
                if ref is not None:
                    v.append(ref.name)
                    ref.add_listener(self)
                else:
                    logger.warning(f"could not get variable {s}")
        logger.debug(f"observable {self.name}: listening to variables {v}")
        # logger.debug(f"observable {self.name} inited")

    def get_events(self) -> set:
        return self._events

    def get_variables(self) -> set:
        return self._value.get_variables()

    def get_string_variables(self) -> set:
        return self._value.get_string_variables()

    def simulator_variable_changed(self, data: SimulatorVariable):
        # if not self._enabled:
        #     logger.warning(f"observable {self.name} disabled")
        #     return
        self.value = self._value.get_value()
        if self.mode == CONFIG_KW.TRIGGER.value:
            if self.value != 0:  # 0=False
                logger.debug(f"observable {self.name} executing (conditional trigger)..")
                if self._enabled:
                    self._actions.execute()
                else:
                    logger.info(f"observable {self.name} not enabled")
                logger.debug(f"..observable {self.name} executed")
            else:
                logger.debug(f"observable {self.name} condition is false ({self.value})")
        if self.mode == CONFIG_KW.ONCHANGE.value:
            if self.has_changed():
                logger.debug(f"observable {self.name} executing (value changed)..")
                if self._enabled:
                    self._actions.execute()
                else:
                    logger.info(f"observable {self.name} not enabled")
                logger.debug(f"..observable {self.name} executed")
            else:
                logger.debug(f"observable {self.name} value unchanged ({self.value})")
