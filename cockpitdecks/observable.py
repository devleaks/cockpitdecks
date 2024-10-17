from __future__ import annotations
import logging
from typing import Set

from cockpitdecks.constant import CONFIG_KW
from cockpitdecks.simulator import Simulator, SimulatorData, MacroInstruction, SimulatorDataListener
from cockpitdecks.value import Value

# from cockpitdecks.deck import Deck

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class Observables:
    """Collection of observables."""

    def __init__(self, config: dict, simulator: Simulator):
        """Deck event

        Args:
            action (DECK_ACTIONS): Action produced by this event (~ DeckEvent type)
            deck (Deck): Deck that produced the event
        """
        self._config = config
        self.sim = simulator
        self.observables = [Observable(config=c, simulator=self.sim) for c in self._config.get(CONFIG_KW.OBSERVABLES.value)]
        self.simulator_data = None


class Observable(SimulatorDataListener):
    """Individual observable.
    Triggered by a formula that returns True or False.
    Executes actions in list.
    """

    def __init__(self, config: dict, simulator: Simulator):
        self._config = config
        self.name = config.get(CONFIG_KW.NAME.value)
        self.mode = config.get(CONFIG_KW.TYPE.value, CONFIG_KW.TRIGGER.value)
        self.sim = simulator
        self._enabled = True
        self._value = Value(name=self.name, config=self._config, provider=simulator)
        self.previous_value = None
        self.current_value = None
        self._actions = MacroInstruction(type(self).__name__, self._config.get(CONFIG_KW.ACTIONS.value))
        self.init()

    @property
    def value(self):
        """
        Gets the current value, but does not provoke a calculation, just returns the current value.
        """
        logger.debug(f"button {self.name}: {self.current_value}")
        return self.current_value

    @value.setter
    def value(self, value):
        if value != self.current_value:
            self.previous_value = self.current_value
            self.current_value = value
            logger.debug(f"button {self.name}: {self.current_value}")

    def has_changed(self) -> bool:
        if self.previous_value is None and self.current_value is None:
            return False
        elif self.previous_value is None and self.current_value is not None:
            return True
        elif self.previous_value is not None and self.current_value is None:
            return True
        return self.current_value != self.previous_value

    @property
    def trigger(self):
        return self._config.get(CONFIG_KW.FORMULA.value)

    def enabled(self):
        self._enabled = True

    def disable(self):
        self._enabled = False

    def simulator_data_changed(self, data: SimulatorData):
        if not self._enabled:
            logger.warning(f"observable {self.name} disabled")
            return
        self.value = self._value.get_value()
        if self.mode == CONFIG_KW.TRIGGER.value:
            if self.value != 0:  # 0=False
                logger.debug(f"observable {self.name} executed (trigger)")
                # self._actions.execute(self.sim)
        if self.mode == CONFIG_KW.ONCHANGE.value:
            if self.has_changed():
                logger.debug(f"observable {self.name} executed (changed)")
                # self._actions.execute(self.sim)

    def init(self):
        # Register datarefs and ask to be notified
        simdata = self._value.get_simulator_data()
        if simdata is not None:
            for s in simdata:
                ref = self.sim.get_dataref(s)
                if ref is not None:
                    ref.add_listener(self)

        logger.debug(f"observable {self.name}: listening to {simdata}")
        logger.debug(f"observable {self.name} inited")
