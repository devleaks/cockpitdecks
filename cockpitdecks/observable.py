from __future__ import annotations
import logging
import threading
from abc import ABC, abstractmethod

from cockpitdecks.constant import CONFIG_KW, ID_SEP
from cockpitdecks.simulator import Simulator, SimulatorVariable, SimulatorVariableListener
from cockpitdecks.simulator import SimulatorActivity, SimulatorActivityListener
from cockpitdecks.instruction import MacroInstruction
from cockpitdecks.value import Value


logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


class Observables:
    """Collection of observables from global configuration"""

    def __init__(self, config: dict, simulator: Simulator):
        """Variable observable

        Take action if variable has changed
        """
        self._config = config
        self.sim = simulator
        self.observables = [Observable.new(config=c, simulator=self.sim) for c in self._config.get(CONFIG_KW.OBSERVABLES.value)]

    def __str__(self) -> str:
        return ", ".join([o._name for o in self.observables])

    def get_activities(self) -> set:
        ret = set()
        for o in self.observables:
            ret = ret | o.get_activities()
        return ret

    def get_variables(self) -> set:
        ret = set()
        for o in self.observables:
            ret = ret | o.get_variables()
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

    def get_observables(self) -> list:
        return self.observables

    def get_observable(self, name) -> Observable | None:
        for o in self.observables:
            if o._name == name:
                return o
        return None

    def unload(self):
        for o in self.observables:
            o.disable()
            o.remove_listener()
        logger.debug("observables unloaded")

    def terminate(self):
        for o in self.observables:
            o.terminate()
        logger.debug("observables terminated")


class Observable:
    """An Observable is a Value that is monitored for changes.
       When the data changes, associated Instructions are performed (in sequence).
    Executes actions in list.
    """

    OBSERVABLE_NAME = "observable-base"

    @classmethod
    def name(cls) -> str:
        return cls.OBSERVABLE_NAME

    def __init__(self, config: dict, simulator: Simulator):
        self._name: str = config.get(CONFIG_KW.NAME.value, type(self).__name__)
        self._config = config
        self.mode = config.get(CONFIG_KW.TYPE.value, CONFIG_KW.TRIGGER.value)
        self.sim = simulator
        self._show_set_value = False
        self._enabled = config.get(CONFIG_KW.ENABLED.value, False)
        # Create a data "internal:observable:name" is enabled or disabled
        self._enabled_data_name = ID_SEP.join([CONFIG_KW.OBSERVABLE.value, self._name])
        self._enabled_data = self.sim.get_internal_variable(self._enabled_data_name)
        self._enabled_data.update_value(new_value=0)
        self._value = Value(name=self._name, config=self._config, provider=simulator)
        self._actions = MacroInstruction(
            name=self._name,
            performer=simulator,
            factory=simulator.cockpit,
            instructions=self._config.get(CONFIG_KW.ACTIONS.value, {}),
        )
        self.init()

    @staticmethod
    def new(config: dict, simulator: Simulator) -> Observable | None:
        # Factory
        which = config.get("type")
        if which == CONFIG_KW.TRIGGER.value:
            return ConditionalObservable(config=config, simulator=simulator)
        if which == CONFIG_KW.ONCHANGE.value:
            return OnChangeObservable(config=config, simulator=simulator)
        if which == CONFIG_KW.REPEAT.value:
            return TimedObservable(config=config, simulator=simulator)
        if which == CONFIG_KW.EVENT.value:
            return ActivityObservable(config=config, simulator=simulator)
        logger.warning(f"invalid observable type {which}, not created")
        return None

    @staticmethod
    def is_internal(name: None) -> bool:
        test = Observable.name() if name is None else name
        return test.endswith("base") or test.endswith("internal")

    @property
    def value(self):
        """Gets the current value, but does not provoke a calculation, just returns the current value."""
        if self._show_set_value:
            logger.debug(f"observable {self._name}: {self._value.value}")
        return self._value.value

    @value.setter
    def value(self, value):
        if self._show_set_value:
            logger.debug(f"observable {self._name}: set value to {value}")
        self._value.update_value(new_value=value, cascade=True)

    def has_changed(self) -> bool:
        return self._value.has_changed()

    @property
    def trigger(self):
        return self._config.get(CONFIG_KW.FORMULA.value)

    def enable(self):
        self._enabled = True
        self._enabled_data.update_value(new_value=1, cascade=True)
        logger.info(f"observable {self._name} enabled")

    def disable(self):
        self._enabled = False
        self._enabled_data.update_value(new_value=0, cascade=True)
        logger.info(f"observable {self._name} disabled")

    def init(self):
        # Register simulator variables and ask to be notified
        variables = self.get_variables()
        v = set()
        if variables is not None:
            for s in variables:
                ref = self.sim.get_variable(s)
                if ref is not None:
                    v.add(ref.name)
                    ref.add_listener(self)
                else:
                    logger.warning(f"could not get variable {s}")
        if len(v) == 0:
            logger.debug(f"observable {self._name}: listening to no variable")
        else:
            logger.debug(f"observable {self._name}: listening to variables {v}")
        # logger.debug(f"observable {self._name} inited")

    def remove_listener(self):
        variables = self.get_variables()
        if variables is not None:
            for s in variables:
                ref = self.sim.get_variable(s)
                if ref is not None:
                    ref.remove_listener(self)
                else:
                    logger.warning(f"could not get variable {s}")
        logger.debug(f"observable {self._name}: listening to no variable")

    def get_activities(self) -> set:
        return set()

    def get_variables(self) -> set:
        return self._value.get_variables()

    def describe(self) -> str:
        return ". ".join(["to do"])

    def terminate(self):
        self.disable()
        self.remove_listener()


class ConditionalObservable(Observable, SimulatorVariableListener):

    OBSERVABLE_NAME = "observable-conditional-base"

    def __init__(self, config: dict, simulator: Simulator):
        Observable.__init__(self, config=config, simulator=simulator)
        SimulatorVariableListener.__init__(self, name=self._name)

    def simulator_variable_changed(self, data: SimulatorVariable):
        # if not self._enabled:
        #     logger.warning(f"observable {self._name} disabled")
        #     return
        if not self._enabled:
            logger.warning(f"observable {self._name} disabled")
            return
        self.value = self._value.value
        if self.value != 0:  # 0=False
            logger.debug(f"observable {self._name} executing (conditional trigger)..")
            self._actions.execute()
            logger.debug(f"..observable {self._name} executed")
        else:
            logger.debug(f"observable {self._name} condition is false ({self.value})")


class ActivityObservable(Observable, SimulatorActivityListener):

    OBSERVABLE_NAME = "observable-activity-base"

    def __init__(self, config: dict, simulator: Simulator):
        Observable.__init__(self, config=config, simulator=simulator)
        SimulatorActivityListener.__init__(self, name=self._name)
        self._activities = set()
        activity = config.get(CONFIG_KW.ACTIVITY.value)
        if activity is not None:
            self._activities = self._activities | {activity}
        activities = config.get(CONFIG_KW.ACTIVITIES.value)
        if activities is not None:
            self._activities = self._activities | set(activities)
        if len(self._activities) == 0:
            logger.warning(f"observable {self._name} of type activity has no activity")
        else:
            logger.debug(f"observable {self._name}: listening to activities {self._activities}")

    def get_activities(self) -> set:
        return self._activities

    def simulator_activity_received(self, activity: SimulatorActivity):
        if activity.name not in self.get_activities():
            return  # not for me, should never happen
        logger.info(f"activity received {activity}")


class OnChangeObservable(Observable, SimulatorVariableListener):

    OBSERVABLE_NAME = "observable-onchange-base"

    def __init__(self, config: dict, simulator: Simulator):
        Observable.__init__(self, config=config, simulator=simulator)
        SimulatorVariableListener.__init__(self, name=self._name)

    def simulator_variable_changed(self, data: SimulatorVariable):
        if not self._enabled:
            logger.warning(f"observable {self._name} disabled")
            return
        self.value = self._value.value
        if self.has_changed():
            logger.debug(f"observable {self._name} executing (value changed)..")
            self._actions.execute()
            logger.debug(f"..observable {self._name} executed")
        else:
            logger.debug(f"observable {self._name} value unchanged ({self.value})")


class TimedObservable(Observable, SimulatorVariableListener):

    OBSERVABLE_NAME = "observable-timed-base"

    def __init__(self, config: dict, simulator: Simulator):
        self.delay = config.get(CONFIG_KW.DELAY.value, 1)
        self.repeat = config.get(CONFIG_KW.REPEAT.value, 1)
        self._timer: threading.Timer | None = None
        self._show_set_value = False
        self._should_run = True
        Observable.__init__(self, config=config, simulator=simulator)
        SimulatorVariableListener.__init__(self, name=self._name)

    def init(self):
        super().init()
        self.start()

    def simulator_variable_changed(self, data: SimulatorVariable):
        # we do nothing on var change, we use our timer
        pass

    @property
    def should_run(self) -> bool:
        return self._should_run

    def enable(self):
        super().enable()
        self.start()

    def disable(self):
        super().disable()
        self.stop()

    def start(self):
        if self._timer is None and self.delay > 0:
            self._timer = threading.Timer(self.delay, self._execute_and_repeat)
            self._timer.start()
            logger.debug(f"{self.name} will be first executed in {self.delay} secs")

    def stop(self):
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
            logger.debug(f"{self._name} timer cancelled")

    def terminate(self):
        super().terminate()
        self.stop()
        logger.debug(f"{self._name} terminated")


    def _execute_and_repeat(self):
        self.stop()
        if not self._enabled:
            logger.warning(f"observable {self._name} disabled")
            return
        logger.debug(f"observable {self._name} executing (timed repeat)..")
        self._actions.execute()
        logger.debug(f"..observable {self._name} executed")
        if self.should_run:
            self._timer = threading.Timer(self.repeat, self._execute_and_repeat)
            self._timer.start()
            logger.debug(f"{self._name} will execute again in {self.repeat} secs")
        return True
