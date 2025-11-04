"""
Button action and activation abstraction
"""

import logging
from abc import ABC, abstractmethod
from typing import List
from datetime import datetime

from cockpitdecks import ID_SEP, CONFIG_KW, DECK_ACTIONS, DEFAULT_ATTRIBUTE_PREFIX, parse_options, DEPRECATION_LEVEL
from cockpitdecks.event import PushEvent
from cockpitdecks.variable import InternalVariable, ValueProvider, Variable, VariableListener
from cockpitdecks.resources.intvariables import COCKPITDECKS_INTVAR
from .parameters import PARAM_DESCRIPTION, PARAM_DECK

logger = logging.getLogger(__name__)
# from cockpitdecks import SPAM
# logger.setLevel(SPAM_LEVEL)
# logger.setLevel(logging.DEBUG)

# This state attribute is special
# If present, it is written to set-dataref
ACTIVATION_VALUE = "activation_value"


class ActivationBase(ABC):

    ACTIVATION_NAME = "base"

    REQUIRED_DECK_ACTIONS: DECK_ACTIONS | List[DECK_ACTIONS] = DECK_ACTIONS.NONE  # List of deck capabilities required to do the activation
    # One cannot request an activiation from a deck button that does not have the capability of the action
    # requested by the activation.
    PARAMETERS = {}

    @classmethod
    def parameters(cls) -> dict:
        return cls.PARAMETERS

    @classmethod
    def name(cls) -> str:
        return cls.ACTIVATION_NAME

    @classmethod
    def get_required_capability(cls) -> list | tuple:
        r = cls.REQUIRED_DECK_ACTIONS
        return r if type(r) in [list, tuple] else [r]

    @abstractmethod
    def activate(self, event) -> bool:
        return False

    @abstractmethod
    def get_activation_value(self):
        pass


# ##########################################
# ACTIVATION
#
class Activation(ActivationBase, VariableListener):
    """
    Base class for all activation mechanism.
    Can be used for no-operation activation on display-only button.
    """

    ACTIVATION_NAME = "none"
    REQUIRED_DECK_ACTIONS: DECK_ACTIONS | List[DECK_ACTIONS] = DECK_ACTIONS.NONE  # List of deck capabilities required to do the activation
    # One cannot request an activiation from a deck button that does not have the capability of the action
    # requested by the activation.

    # Parameters of base class Activation (name "none") contains global parameters, common to all buttons.
    # They are called the General or Global or Descriptive parameters.
    PARAMETERS = ActivationBase.PARAMETERS | PARAM_DESCRIPTION | PARAM_DECK

    @classmethod
    def parameters(cls) -> dict:
        # See https://stackoverflow.com/questions/1817183/using-super-with-a-class-method
        # To merge parent class + this class
        return cls.PARAMETERS

    @classmethod
    def name(cls) -> str:
        return cls.ACTIVATION_NAME

    @classmethod
    def get_required_capability(cls) -> list | tuple:
        r = cls.REQUIRED_DECK_ACTIONS
        return r if type(r) in [list, tuple] else [r]

    def __init__(self, button: "Button"):
        self._inited = False

        self.button = button
        self.button.deck.cockpit.set_logging_level(__name__)
        ActivationBase.__init__(self)
        VariableListener.__init__(self, name=self.name())
        if type(self.REQUIRED_DECK_ACTIONS) not in [list, tuple]:
            self.REQUIRED_DECK_ACTIONS = [self.REQUIRED_DECK_ACTIONS]

        # Options
        self.options = parse_options(self._config.get(CONFIG_KW.OPTIONS.value))

        # Commands
        self._command = None
        cmdname = ":".join([self.button.get_id(), type(self).__name__])

        # Depecrated
        self.skip_view = False
        self._view = None
        view = self._config.get(CONFIG_KW.VIEW.value)
        if view is not None:  # a "view" is just a command...
            logger.log(DEPRECATION_LEVEL, f"{self.button_name}: {self.name()}: usage of view is deprecated")
            if type(view) is str:
                view = {CONFIG_KW.COMMAND.value: view}
            self._view = self.sim.instruction_factory(name=cmdname + ":view", instruction_block=view)
            self._view.button = self.button  # set button to evalute conditional

        # Vibrate on press, or emit/play sound (mp3 or wav only for web compatibility
        self.vibrate = self.get_attribute("vibrate")
        self.sound = self.get_attribute("sound")

        # Long press option
        self._long_press = None
        long_press = self._config.get(CONFIG_KW.LONG_PRESS.value)
        if long_press is not None:  # a long-press is just a command that gets executed when pressed for a long time
            self._long_press = self.sim.instruction_factory(
                name=cmdname + ":long-press", instruction_block={CONFIG_KW.COMMAND.value: long_press}
            )  # Optional additional command

        # Datarefs
        # Note on set-dataref: The activation will set the dataref value
        # to the value of the activation but it will NOT write it to X-Plane.
        # Therefore, here, it is not a SetDataref instruction that is built,
        # but rather a explicit "on-demand" write when necessary.
        self.activation_requires_modification_set_dataref = False
        self._set_sim_data = None
        set_dataref_path = self._config.get(CONFIG_KW.SET_SIM_VARIABLE.value)
        if set_dataref_path is not None:
            self._set_sim_data = self.button.sim.get_variable(set_dataref_path)
            self._set_sim_data.add_listener(self)
            self._set_sim_data_value = self._config.get(CONFIG_KW.VALUE.value)  # static value for now, could be a Formula! (to do)
        self.activation_requires_modification_set_dataref = True  # always for now

        # Working variables, internal state
        self._last_event = None
        self._activate_start = None

        self.last_activated = 0
        self.duration = 0
        self.pressed = False
        self.initial_value = self._config.get(CONFIG_KW.INITIAL_VALUE.value)
        self._guard_changed = False

        self.init()

    @property
    def _config(self):
        # Activation._config = Button._config
        return self.button._config

    @property
    def sim(self):
        return self.button.sim

    @property
    def cockpit(self):
        return self.button.deck.cockpit

    def init(self):  # ~ABC
        pass

    def get_id(self):
        return ID_SEP.join([self.button.get_id(), type(self).__name__])

    def __str__(self):  # print its status
        return ", ".join([type(self).__name__, f"activation-count: {self.activation_count}"])

    def can_handle(self, event) -> bool:
        if event.action not in self.get_required_capability():
            logger.warning(
                f"button {self.button_name}: {type(self).__name__}: invalid event received {type(event).__name__}, action {event.action}, expected {self.REQUIRED_DECK_ACTIONS}"
            )
            return False
        return True

    @property
    def button_name(self) -> str:
        return self.button.name if self.button is not None else "no button"

    def has_option(self, option):
        # Check whether a button has an option.
        for opt in self.options:
            if opt.split("=")[0].strip() == option:
                return True
        return False

    def option_value(self, option, default=None):
        # Return the value of an option or the supplied default value.
        for opt in self.options:
            opt = opt.split("=")
            name = opt[0].strip()
            if name == option:
                if len(opt) > 1:
                    return opt[1].strip()
                else:  # found just the name, so it may be a boolean, True if present
                    return True
        return default

    def get_attribute(self, attribute: str, default=None, propagate: bool = False, silence: bool = True):
        # Is there such an attribute directly in the button defintion?
        if attribute.startswith(DEFAULT_ATTRIBUTE_PREFIX):
            logger.warning(f"button {self.button_name}: activation fetched default attribute {attribute}")

        value = self._config.get(attribute)
        if value is not None:  # found!
            if silence:
                logger.debug(f"button {self.button_name} activation returning {attribute}={value}")
            else:
                logger.info(f"button {self.button_name} activation returning {attribute}={value}")
            return value

        if propagate:  # we just look at the button. level, not above.
            if not silence:
                logger.info(f"button {self.button_name} activation propagate to button for {attribute}")
            return self.button.get_attribute(attribute, default=default, propagate=propagate, silence=silence)

        if not silence:
            logger.warning(f"button {self.button_name}: activation attribute not found {attribute}, returning default ({default})")

        return default

    def inc(self, name: str, amount: float = 1.0, cascade: bool = True):
        self.button.sim.inc_internal_variable(name=ID_SEP.join([self.get_id(), name]), amount=amount, cascade=False)

    def is_guarded(self):
        # Check this before activating in subclasses if necessary
        # because calling super().activate() may lift the guard.
        # So this keeps a track whether the guard was on or not BEFORE calling super().activate().
        #
        # 1. call super().activate()
        # 2. check this (local) is_guarded() before doing your things
        # (button.is_guarded() may have changed! if super().activate() was called.)
        #
        if self._guard_changed:
            return True
        return self.button.is_guarded()

    def done(self):
        if self._activate_start is not None:
            self._activation_completed = self._activation_completed + 1
            self.inc(COCKPITDECKS_INTVAR.ACTIVATION_COMPLETED.value)

            duration = datetime.now() - self._activate_start
            self._total_duration = self._total_duration + duration
            self.inc(COCKPITDECKS_INTVAR.ACTIVATION_DURATION.value, duration)

    def is_pressed(self):
        return self.pressed

    def long_pressed(self, duration: float = 2) -> bool:
        return self.duration > duration

    def has_beginend_command(self) -> bool:
        if hasattr(self, "_command"):
            cmd = getattr(self, "_command")
            if cmd is not None:
                return type(cmd).__name__ == "BeginEndCommand"
        return False

    def has_long_press(self) -> bool:
        return self._long_press is not None and self._long_press.is_valid()

    def get_variables(self) -> set:
        if self._set_sim_data is not None:
            return {self._set_sim_data.name}
        return set()

    def variable_changed(self, data: Variable):
        logger.debug(f"variable {data.name} changed, unhandled by activation")
        pass

    def long_press(self, event):
        logger.debug(">" * 40 + " long-press")
        self._long_press.execute()

    def is_valid(self) -> bool:
        if self.button is None:
            logger.warning(f"{type(self).__name__} has no button")
            return False
        return True

    # ############################
    # Main external API procedures
    #
    @property
    def activation_count(self):
        path = ID_SEP.join([self.get_id(), COCKPITDECKS_INTVAR.ACTIVATION_COUNT.value])
        dref = self.button.sim.get_internal_variable(path)
        value = dref.value
        return 0 if value is None else value

    def activate(self, event) -> bool:
        """
        Function that is executed when a button is activated (pressed, released, turned, etc.).
        Default is to tally number of times this button was pressed. It should have been released as many times :-D.
        **** No command gets executed here **** except if there is an associated view with the button.
        It removes guard if it was present and closed.
        """
        if not self._inited:
            self.init()
        self._last_event = event
        self._activate_start = datetime.now()

        # Stats keeping
        s = str(type(event).__name__)
        self.inc(ID_SEP.join([s, "activations"]))

        # Special handling of some events
        if type(event) is not PushEvent:
            return True  # finished normally

        if event.pressed:
            self.pressed = True
            self.skip_view = True  # we only trigger the view on release
            self.inc(COCKPITDECKS_INTVAR.ACTIVATION_COUNT.value)

            now = datetime.now().timestamp()
            self.last_activated = now
            self._fast = now - self.last_activated  # time between previous activation and this one

            logger.debug(f"button {self.button_name}: {type(self).__name__} activated")

            # Guard handling
            if self.button.is_guarded():
                return False

            if self.vibrate is not None and hasattr(self.button.deck, "_vibrate"):
                self.button.deck._vibrate(self.vibrate)

            if self.sound is not None and hasattr(self.button.deck, "play_sound"):
                self.button.deck.play_sound(self.sound)

        else:
            self.pressed = False
            self.duration = datetime.now().timestamp() - self.last_activated
            self.inc(COCKPITDECKS_INTVAR.ACTIVATION_RELEASE.value)

            # Guard handling
            self._guard_changed = False
            if self.button.is_guarded() and self.long_pressed():
                self.button.set_guard_off()
                logger.debug(f"button {self.button_name}: {type(self).__name__}: guard removed")
                self._guard_changed = True
                return True

            if self.button.has_guard() and not self.button.is_guarded() and self.long_pressed():
                self.button.set_guard_on()
                logger.debug(f"button {self.button_name}: {type(self).__name__}: guard replaced")
                self._guard_changed = True
                return True

            # Long press handling
            if self.has_long_press() and self.long_pressed():
                self.long_press(event)
                logger.debug(f"button {self.button_name}: {type(self).__name__}: long pressed")
                return True

        logger.debug(f"{type(self).__name__} activated ({event}, {self.activation_count})")
        return True

    def set_dataref(self):
        # Writes the "raw" activation value to set-dataref as produced by the activation
        if self._set_sim_data is None:
            return
        if self._set_sim_data_value is not None:  # set to static value
            self._set_sim_data.update_value(new_value=self._set_sim_data_value, cascade=True)
            logger.debug(f"button {self.button_name}: {type(self).__name__} set-dataref {self._set_sim_data.name} to static value {self._set_sim_data_value}")
            return
        value = self.get_activation_value()
        if value is None:
            logger.debug(f"button {self.button_name}: {type(self).__name__} activation value is none")
            return
        if type(value) is bool:
            value = 1 if value else 0
        self._set_sim_data.update_value(new_value=value, cascade=True)
        logger.debug(f"button {self.button_name}: {type(self).__name__} set-dataref {self._set_sim_data.name} to activation value {value}")

    def view(self):
        if self._view is not None:
            if self.skip_view:
                logger.debug(f"button {self.button_name}: skipping view {self._view}")
                return
            self._view.execute()

    def handle(self, event):
        # Handle event, perform activation
        result = self.activate(event)
        if result:  # terminated without error
            if self.activation_requires_modification_set_dataref:
                self.set_dataref()
            else:
                logger.debug(f"button {self.button_name}: {type(self).__name__} activation does not set-dataref ({event})")
                self.activation_requires_modification_set_dataref = True  # reset it
            # Optionally affect cockpit view to concentrate on event consequences
            if self.skip_view:
                self.skip_view = False
                logger.debug(f"button {self.button_name}: {type(self).__name__} view skipped")
            else:
                self.view()
                logger.debug(f"button {self.button_name}: {type(self).__name__} view activated")

    def inspect(self, what: str | None = None):
        if what is not None and "activation" not in what:
            return
        logger.info(f"{type(self).__name__}:")
        logger.info(f"{self.is_valid()}")
        logger.info(f"{self._view}")
        logger.info(f"{self.initial_value}")

        logger.info(f"{self._last_event}")

        logger.info(f"{self.activation_count}")
        logger.info(f"{self.last_activated}")
        logger.info(f"{self.duration}")
        logger.info(f"{self.pressed}")

    def get_activation_count(self) -> int:
        return int(self.activation_count)

    def get_activation_value(self):
        return self.activation_count

    def get_state_variables(self) -> dict:
        base = InternalVariable(name=self.get_id()).name
        vardb = self.button.cockpit.variable_database.database
        drefs = {d.name.split(ID_SEP)[-1]: d.value for d in filter(lambda d: d.name.startswith(base), vardb.values())}
        a = {
            "activation_type": type(self).__name__,
            "last_activated": self.last_activated,
            "last_activated_dt": datetime.fromtimestamp(self.last_activated).isoformat(),
            "initial_value": self.initial_value,
            "set-dataref": self._set_sim_data.name if self._set_sim_data is not None else None,
            ACTIVATION_VALUE: self.get_activation_value(),
        }
        return a | drefs

    def get_rescaled_value(self, range_min: float, range_max: float, steps: int | None = None):
        return self.button._value.get_rescaled_value(range_min=range_min, range_max=range_max, steps=steps)

    def describe(self) -> str:
        """
        Describe what the button does in plain English
        """
        return "\n".join(["The button does nothing."])


class ActivationValueProvider(ABC, ValueProvider):
    def __init__(self, name: str, activation: Activation):
        ValueProvider.__init__(self, name=name, provider=activation)

    @abstractmethod
    def get_activation_value(self):
        pass
