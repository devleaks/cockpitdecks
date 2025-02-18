"""
Button action and activation abstraction
"""

import logging
from abc import ABC, abstractmethod
from typing import List
from datetime import datetime

from cockpitdecks.constant import ID_SEP
from cockpitdecks.event import PushEvent
from cockpitdecks.variable import InternalVariable, ValueProvider
from cockpitdecks import CONFIG_KW, DECK_ACTIONS, DEFAULT_ATTRIBUTE_PREFIX, parse_options
from cockpitdecks.resources.intvariables import COCKPITDECKS_INTVAR

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
class Activation:
    """
    Base class for all activation mechanism.
    Can be used for no-operation activation on display-only button.
    """

    ACTIVATION_NAME = "none"
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

    def __init__(self, button: "Button"):
        self.button = button
        self._inited = False

        self.button.deck.cockpit.set_logging_level(__name__)

        # Options

        # Commands
        self._command = None
        self._view = None
        self.skip_view = False

        cmdname = ":".join([self.button.get_id(), type(self).__name__])

        view = self._config.get(CONFIG_KW.VIEW.value)
        if view is not None:
            self._view = self.sim.instruction_factory(name=cmdname + ":view", instruction_block={"view": view})
            self._view.button = self.button  # set button to evalute conditional

        # Vibrate on press
        self.vibrate = self.get_attribute("vibrate")
        self.sound = self.get_attribute("sound")

        # but could be anything.
        self._long_press = None
        long_press = self._config.get("long-press")
        if long_press is not None:
            self._long_press = self.sim.instruction_factory(
                name=cmdname + ":long-press", instruction_block={"long_press": long_press}
            )  # Optional additional command

        # Datarefs
        # Note on set-dataref: The activation will set the dataref value
        # to the value of the activatiuon but it will NOT write it to X-Plane
        # Therefore, here, it is not a Instruction SetDataref that is built,
        # but rather a explicit write when necessary.
        self._writable_dataref = None
        set_dataref_path = self._config.get(CONFIG_KW.SET_SIM_VARIABLE.value)
        if set_dataref_path is not None:
            self._writable_dataref = self.button.sim.get_variable(set_dataref_path)
            self._writable_dataref.writable = True
        self.activation_requires_modification_set_dataref = True

        # Working variables, internal state
        self._last_event = None
        self._activate_start = None

        self.last_activated = 0
        self.duration = 0
        self.pressed = False
        self.initial_value = self._config.get(CONFIG_KW.INITIAL_VALUE.value)
        self._guard_changed = False

        self.options = parse_options(self._config.get(CONFIG_KW.OPTIONS.value))

        if type(self.REQUIRED_DECK_ACTIONS) not in [list, tuple]:
            self.REQUIRED_DECK_ACTIONS = [self.REQUIRED_DECK_ACTIONS]

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
                f"button {self.button_name()}: {type(self).__name__}: invalid event received {type(event).__name__}, action {event.action}, expected {self.REQUIRED_DECK_ACTIONS}"
            )
            return False
        return True

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
            logger.warning(f"button {self.button_name()}: activation fetched default attribute {attribute}")

        value = self._config.get(attribute)
        if value is not None:  # found!
            if silence:
                logger.debug(f"button {self.button_name()} activation returning {attribute}={value}")
            else:
                logger.info(f"button {self.button_name()} activation returning {attribute}={value}")
            return value

        if propagate:  # we just look at the button. level, not above.
            if not silence:
                logger.info(f"button {self.button_name()} activation propagate to button for {attribute}")
            return self.button.get_attribute(attribute, default=default, propagate=propagate, silence=silence)

        if not silence:
            logger.warning(f"button {self.button_name()}: activation attribute not found {attribute}, returning default ({default})")

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
        if self._writable_dataref is not None:
            return {self._writable_dataref.name}
        return set()

    def get_string_variables(self) -> set:
        return set()

    def long_press(self, event):
        logger.debug(">" * 40 + " long_press")
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
        value = dref.value()
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

            logger.debug(f"button {self.button_name()}: {type(self).__name__} activated")

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
                logger.debug(f"button {self.button_name()}: {type(self).__name__}: guard removed")
                self._guard_changed = True
                return True

            if self.button.has_guard() and not self.button.is_guarded() and self.long_pressed():
                self.button.set_guard_on()
                logger.debug(f"button {self.button_name()}: {type(self).__name__}: guard replaced")
                self._guard_changed = True
                return True

            # Long press handling
            if self.has_long_press() and self.long_pressed():
                self.long_press(event)
                logger.debug(f"button {self.button_name()}: {type(self).__name__}: long pressed")
                return True

        logger.debug(f"{type(self).__name__} activated ({event}, {self.activation_count})")
        return True

    def set_dataref(self):
        # Writes the "raw" activation value to set-dataref as produced by the activation
        if self._writable_dataref is None:
            return
        value = self.get_activation_value()
        if value is None:
            logger.debug(f"button {self.button_name()}: {type(self).__name__} activation value is none")
            return
        if type(value) is bool:
            value = 1 if value else 0
        self._writable_dataref.update_value(new_value=value, cascade=True)
        logger.debug(f"button {self.button_name()}: {type(self).__name__} set-dataref {self._writable_dataref.name} to activation value {value}")

    def view(self):
        if self._view is not None:
            if self.skip_view:
                logger.debug(f"button {self.button_name()}: skipping view {self._view}")
                return
            self._view.execute()

    def handle(self, event):
        # Handle event, perform activation
        result = self.activate(event)
        if result:  # terminated without error
            if self.activation_requires_modification_set_dataref:
                self.set_dataref()
            else:
                logger.debug(f"button {self.button_name()}: {type(self).__name__} activation does not set-dataref ({event})")
                self.activation_requires_modification_set_dataref = True  # reset it
            # Optionally affect cockpit view to concentrate on event consequences
            if self.skip_view:
                self.skip_view = False
                logger.debug(f"button {self.button_name()}: {type(self).__name__} view skipped")
            else:
                self.view()
                logger.debug(f"button {self.button_name()}: {type(self).__name__} view activated")

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

    def get_activation_value(self):
        return self.activation_count

    def get_state_variables(self) -> dict:
        base = InternalVariable(name=self.get_id()).name
        vardb = self.button.cockpit.variable_database.database
        drefs = {d.name.split(ID_SEP)[-1]: d.value() for d in filter(lambda d: d.name.startswith(base), vardb.values())}
        a = {
            "activation_type": type(self).__name__,
            "last_activated": self.last_activated,
            "last_activated_dt": datetime.fromtimestamp(self.last_activated).isoformat(),
            "initial_value": self.initial_value,
            "writable_dataref": self._writable_dataref.name if self._writable_dataref is not None else None,
            ACTIVATION_VALUE: self.get_activation_value(),
        }
        return a | drefs

    def get_rescaled_value(self, range_min: float, range_max: float, steps: int | None = None):
        return self.button._value.get_rescaled_value(range_min=range_min, range_max=range_max, steps=steps)

    def describe(self) -> str:
        """
        Describe what the button does in plain English
        """
        return "\n\r".join([f"The button does nothing."])


class ActivationValueProvider(ABC, ValueProvider):
    def __init__(self, name: str, activation: Activation):
        ValueProvider.__init__(self, name=name, provider=activation)

    @abstractmethod
    def get_activation_value(self):
        pass
