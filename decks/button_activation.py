"""
Button action and activation abstraction
"""
import logging
import yaml
from datetime import datetime

from .color import is_integer

logger = logging.getLogger("Activation")
# logger.setLevel(logging.DEBUG)


# ##########################################
# ACTIVATION
#
class Activation:
    """
    Base class for all activation mechanism.
    Can be used for no-operation activation on display-only button.
    """
    def __init__(self, config: dict, button: "Button"):
        self._config = config
        self.button = button

        # Options

        # Guard
        self.guarded = False
        self.guard = config.get("guard")
        if self.guard is not None:
            self.guard_type = config.get("guard-type", "plain")
            self.guarded = config.get("guard-status", False)

        # Commands
        self._view = config.get("view")  # Optional additional command, usually to set a view
                                        # but could be anything.
        # Working variables
        self._first_value_not_saved = True
        self._first_value = None    # first value the button will get
        self._last_state = None

        self.activation_count = 0
        self.activations_count = {}
        self.last_activated = None
        self.pressed = False
        self.initial_value = config.get("initial-value")

        self.previous_value = None
        self.current_value = None

        if self.initial_value is not None:
            self.current_value = self.initial_value
            self._first_value = self.initial_value
            self._first_value_not_saved = False
            logger.debug(f"activate: button {self.button.name}: set initial value")

    def activate(self, state):
        """
        Function that is executed when a button is pressed (state=True) or released (state=False) on the Stream Deck device.
        Default is to tally number of times this button was pressed. It should have been released as many times :-D.
        **** No command gets executed here **** except if there is an associated view with the button.
        Also, removes guard if it was present. @todo: close guard
        """
        self._last_state = state
        s = str(state)
        if s in self.activations_count:
            self.activations_count[s] = self.activations_count[s] + 1
        else:
            self.activations_count[s] = 1
        if state:
            self.activation_count = self.activation_count + 1
            self.last_activated = datetime.now().timestamp()
            logger.debug(f"activate: button {self.button.name} activated")

            if self.guarded:            # just open it
                self.guarded = False
                logger.debug(f"activate: button {self.button.name}: guard removed")
                return

            # not guarded, or guard open
            self.pressed = True
            if self.button.has_option("counter"):
                self.set_current_value(self.activation_count)
        else:
            self.pressed = False
        # logger.debug(f"activate: {type(self).__name__} activated ({state}, {self.activation_count})")

    def __str__(self):  # print its status
        return ", ".join((type(self).__name__,
                         f"activation-count: {self.activation_count}",
                         f"current: {self.current_value}",
                         f"previous: {self.previous_value}"))

    def is_pressed(self):
        return self.pressed

    def inspect(self):
        logger.info(f"{self.button.name}:{type(self).__name__}:")
        logger.info(f"is_valid: {self.is_valid()}")
        logger.info(f"view: {self._view}")
        logger.info(f"_first_value_not_saved: {self._first_value_not_saved}")
        logger.info(f"first value: {self._first_value}")
        logger.info(f"initial value: {self.initial_value}")

        logger.info(f"last state: {self._last_state}")

        logger.info(f"activation_count: {self.activation_count}")
        logger.info(f"activations_count: {self.activations_count}")
        logger.info(f"last_activated: {self.last_activated}")
        logger.info(f"pressed: {self.pressed}")

        logger.info(f"previous_value: {self.previous_value}")
        logger.info(f"current_value: {self.current_value}")

    def set_current_value(self, value):
        if self._first_value_not_saved:  # never used, we initialize it
            if self.initial_value is not None:
                self.current_value = self.initial_value
            self._first_value = value
            self._first_value_not_saved = False
        self.previous_value = self.current_value
        self.current_value = value

    def get_current_value(self):
        logger.debug(f"get_current_value: {self.current_value}")
        return self.current_value

    def is_valid(self):
        if self.button is None:
            logger.warning(f"is_valid: activation {type(self).__name__} has no button")
            return False
        return True

    def get_status(self):
        return None

    def view(self):
        if self._view is not None and self.is_valid():
            self.button.xp.commandOnce(self._view)


#
# ###############################
# COCKPITDECKS FUNCTIONS
#
#
class LoadPage(Activation):
    """
    Defines a Page change activation.
    """
    def __init__(self, config: dict, button: "Button"):
        Activation.__init__(self, config=config, button=button)

        # Commands
        self.page = config.get("page", "back")  # default is to go to previously loaded page, if any
        self.remote_deck = config.get("deck")

    def is_valid(self):
        if self.page is None:
            logger.warning(f"is_valid: activation {type(self).__name__} has no page")
            return False
        return super().is_valid()

    def activate(self, state: bool):
        super().activate(state)
        if self.remote_deck is not None and self.remote_deck not in self.deck.cockpit.cockpit.keys():
            logger.warning(f"activate: {type(self).__name__}: deck not found {self.remote_deck}")
            self.remote_deck = None
        if state:
            deck = self.button.deck
            if self.remote_deck is not None and self.remote_deck in self.button.deck.cockpit.cockpit.keys():
                deck = self.button.deck.cockpit.cockpit[self.remote_deck]

            if self.page == "back" or self.page in deck.pages.keys():
                logger.debug(f"activate: {type(self).__name__} change page to {self.page}")
                new_name = deck.change_page(self.page)
                if new_name is not None and self.page != "back":
                    self.set_current_value(new_name)
            else:
                logger.warning(f"activate: {type(self).__name__}: page not found {self.page}")


class Reload(Activation):
    """
    Reloads all decks.
    """
    def __init__(self, config: dict, button: "Button"):
        Activation.__init__(self, config=config, button=button)

    def activate(self, state):
        if state:
            print("Reload activate")
            if self.is_valid():
                self.button.deck.cockpit.reload_decks()


class Inspect(Activation):
    """
    Inspect all decks.
    """
    def __init__(self, config: dict, button: "Button"):
        Activation.__init__(self, config=config, button=button)

    def activate(self, state):
        if state:
            if self.is_valid():
                self.button.deck.cockpit.inspect()


class Stop(Activation):
    """
    Stops all decks.
    """
    def __init__(self, config: dict, button: "Button"):
        Activation.__init__(self, config=config, button=button)

    def activate(self, state):
        if state:
            if self.is_valid():
                self.button.deck.cockpit.stop()

#
# ###############################
# PUSH-BUTTON TYPE ACTIVATION
#
#
class Push(Activation):
    """
    Defines a Push activation.
    The supplied command is executed each time a button is pressed.
    """
    def __init__(self, config: dict, button: "Button"):
        Activation.__init__(self, config=config, button=button)

        # Commands
        self.command = config.get("command")

        # Working variables
        self.pressed = False  # True while the button is pressed, False when released

    def __str__(self):  # print its status
        return super() + "\n" + ", ".join((f"command: {self.command}",
                f"is_valid: {self.is_valid()}"))


    def is_on(self):
        return self.activation_count % 2 == 1

    def is_off(self):
        return self.activation_count % 2 == 0

    def is_valid(self):
        if self.command is None:
            logger.warning(f"is_valid: activation {type(self).__name__} has no command")
            return False
        return super().is_valid()

    def activate(self, state):
        super().activate(state)
        if self.is_valid():
            if state:
                self.button.xp.commandOnce(self.command)
                self.view()
        else:
            logger.warning(f"activate: button {self.button.name} is invalid")


class Longpress(Push):
    """
    Execute beginCommand while the key is pressed and endCommand when the key is released.
    """
    def __init__(self, config: dict, button: "Button"):

        Push.__init__(self, config=config, button=button)

    def activate(self, state):
        super().activate(state)
        if self.is_valid():
            if state:
                self.button.xp.commandBegin(self.command)
            else:
                self.button.xp.commandEnd(self.command)
                self.view()  # on release only


class OnOff(Activation):
    """
    Defines a Push Dual activation.
    Two commands are executed alternatively.
    On or Off status is determined by the number of time a button is pressed
    """
    def __init__(self, config: dict, button: "Button"):
        Activation.__init__(self, config=config, button=button)

        # Commands
        self.commands = config.get("commands", [])

    def __str__(self):  # print its status
        return super() + "\n" + ", ".join((f"commands: {self.commands}",
                f"is_off: {self.is_off()}"),
                f"is_valid: {self.is_valid()}")

    def is_on(self):
        return self.activation_count % 2 == 1

    def is_off(self):
        return self.activation_count % 2 == 0

    def is_valid(self):
        if len(self.commands) < 2:
            logger.error(f"is_valid: button {type(self).__name__} must have at least two command")
            return False
        return super().is_valid()

    def get_current_value(self):
        return self.activation_count % 2

    def activate(self, state):
        super().activate(state)
        if state:
            if self.is_valid():
                if self.is_off():
                    self.button.xp.commandOnce(self.commands[0])
                else:
                    self.button.xp.commandOnce(self.commands[1])
                self.view()
            else:
                logger.warning(f"activate: button {self.button.name} is invalid")


class UpDown(Activation):
    """
    Defines a button activation for a button that runs back and forth
    between 2 values like -2 1 0 1 2, or 0 1 2 3 4 3 2 1 0.
    Two commands are executed, one when the value increases,
    another one when the value decreases.
    """
    def __init__(self, config: dict, button: "Button"):
        Activation.__init__(self, config=config, button=button)

        # Commands
        self.commands = config.get("commands")

        # Internal status
        self.stops = None
        stops = self.button.option_value("stops", 1)
        if stops is not None:
            self.stops = int(stops)
        self.bounce_arr = self.make_bounce_array(self.stops)  # convenient
        self.start_value = None
        self.go_up = True

        if self.initial_value is not None and is_integer(self.initial_value):
            if self.initial_value < 0:
                self.initial_value = abs(self.initial_value)
                self.go_up = False # reverse direction

    def __str__(self):  # print its status
        return super() + "\n" + ", ".join((f"commands: {self.commands}",
                f"stops: {self.stops}"),
                f"is_valid: {self.is_valid()}")

    def is_valid(self):
        if self.commands is None or len(self.commands) < 2:
            logger.error(f"is_valid: button {self.button.name} must have at least 2 commands")
            return False
        if self.stops is None or self.stops == 0:
            logger.error(f"is_valid: button {self.button.name} must have a number of stops")
            return False
        return True

    def activate(self, state: bool):
        super().activate(state)
        # We need to do something if button does not start in status 0. @todo
        # if self.start_value is None:
        #     if self.current_value is not None:
        #         self.start_value = int(self.current_value)
        #     else:
        #         self.start_value = 0
        if state:
            if self._first_value_not_saved:
                if self.initial_value is None:
                    self._first_value = 0
                    self.current_value = 0
                else:
                    self._first_value = int(self.initial_value)
                    self.current_value = int(self.initial_value)
                self._first_value_not_saved = False

            self.current_value = self.bounce_arr[(self._first_value + self.activation_count) % len(self.bounce_arr)]
            # logger.debug(f"activate: counter={self.start_value + self.activation_count} = start={self.start_value} + press={self.activation_count} curr={self.current_value} last={self.bounce_idx} value={value} arr={self.bounce_arr} dir={value > self.bounce_idx}")
            if self.is_valid():
                if self.go_up:
                    self.button.xp.commandOnce(self.commands[0])  # up
                    if self.current_value == (len(self.bounce_arr) - 1):
                        self.go_up = False
                else:
                    self.button.xp.commandOnce(self.commands[1])  # down
                    if self.current_value == 0:
                        self.go_up = True
            else:
                logger.warning(f"activate: button {self.button.name} is invalid")

    def make_bounce_array(self, stops: int):
        # Builds an array like 0-1-2-3-2-1-0 for a 4 stops button.
        if stops > 1:
            af = list(range(stops - 1))
            ab = af.copy()
            ab.reverse()
            return af + [stops-1] + ab[:-1]
        return [0]

#
# ###############################
# ENCODER TYPE ACTIVATION
#
#
""" Note: By vocabulary convention:
An Encoder has a stepped movement, and an action is triggered after each step.
A Know has a continuous value from a minimum value to a maximum value, very much like a slider.
An Encoder with a step value of 1 is more or less a variant of Knob.
"""

class Encoder(Activation):
    """
    Defines a know with stepped value.
    One command is executed when the encoder is turned clockwise one step (state = 2),
    another command is executed the encoder is turned counter-clockwise one step (state = 3).
    """
    def __init__(self, config: dict, button: "Button"):
        Activation.__init__(self, config=config, button=button)

        # Commands
        self.commands = config.get("commands")

        # Internal status
        self._turns = 0
        self._cw = 0
        self._ccw = 0

    def is_valid(self):
        if self.commands is None or len(self.commands) < 2:
            logger.error(f"is_valid: {type(self).__name__} must have at least 2 commands")
            return False
        return super().is_valid()

    def activate(self, state):
        super().activate()
        if state == 2:  # rotate left
            self.button.xp.commandOnce(self.commands[0])
            self._turns = self._turns + 1
            self._cw = self._cw + 1
        elif state == 3:  # rotate right
            self.button.xp.commandOnce(self.commands[1])
            self._turns = self._turns - 1
            self._ccw = self._ccw + 1
        else:
            logger.warning(f"activate: {type(self).__name__} invalid state {state}")

    def get_status(self):
        a = super().get_status()
        if a is not None:
            a = {}
        return a | {
            "cw": self._cw,
            "ccw": self._ccw,
            "turns": self._turns
        }


class EncoderPush(Push):
    """
    Defines a encoder with stepped value coupled to a Push button.
    First command is executed when encoder is pushed.

    Without dual option:
    Second command is executed when the encoder is turned clockwise one step (state = 2),
    Third command is executed the encoder is turned counter-clockwise one step (state = 3).

    With longpush option:
    Command 0: Executed when turned clockwise and not pushed
    Command 1: Executed when turned counter-clockwise and not pushed
    Command 2: Executed when turned clockwise and pushed simultaneously
    Command 3: Executed when turned counter-clockwise and pushed simultaneously
    """
    def __init__(self, config: dict, button: "Button"):
        Push.__init__(self, config=config, button=button)

        # Commands
        self.commands = config.get("commands")
        if len(self.commands) > 0:
            self.command = self.commands[0]
        else:
            logger.error(f"is_valid: button {type(self).__name__} must have at least one command")

        # Internal status
        self._turns = 0
        self._cw = 0
        self._ccw = 0

    def is_valid(self):
        if self.has_option("longpush") and len(self.commands) != 4:
            logger.warning(f"is_valid: button {self.name} must have 4 commands for dual mode")
            return False
        elif not self.has_option("longpush") and len(self.commands) != 3:
            logger.warning(f"is_valid: button {self.name} must have 3 commands")
            return False
        return True  # super().is_valid()

    def activate(self, state):
        if state < 2:
            super().activate(state)
        elif state == 2:  # rotate clockwise
            if self.button.has_option("longpush"):
                if self.is_pressed():
                    self.button.xp.commandOnce(self.commands[0])
                    self._turns = self._turns + 1
                    self._cw = self._cw + 1
                else:
                    self.button.xp.commandOnce(self.commands[2])
                    self._turns = self._turns - 1
                    self._ccw = self._ccw + 1
            else:
                self.button.xp.commandOnce(self.commands[1])
        elif state == 3:  # rotate counter-clockwise
            if self.button.has_option("longpush"):
                if self.is_pressed():
                    self.button.xp.commandOnce(self.commands[1])
                    self._turns = self._turns + 1
                    self._cw = self._cw + 1
                else:
                    self.button.xp.commandOnce(self.commands[3])
                    self._turns = self._turns - 1
                    self._ccw = self._ccw + 1
            else:
                self.button.xp.commandOnce(self.commands[2])
        else:
            logger.warning(f"activate: button {self.name} invalid state {state}")


class EncoderOnOff(OnOff):
    """
    Defines a encoder with stepped value coupled to a OnOff button.
    First command is executed when button is Off and pressed.
    Second command is executed when button is On and pressed.
    Without dual option:
    Third command is execute when encoder is turned clockwise one step (state = 2).
    Fourth command is executed the encoder is turned counter-clockwise one step (state = 3).

    With dual option:
    Third command: Executed when turned clockwise and ON
    Fourth command: Executed when turned counter-clockwise and ON
    Fifth command: Executed when turned clockwise and OFF
    Sixth command: Executed when turned counter-clockwise and OFF
    """
    def __init__(self, config: dict, button: "Button"):
        OnOff.__init__(self, config=config, button=button)

        # Internal status
        self._turns = 0
        self._cw = 0
        self._ccw = 0

    def is_valid(self):
        if self.button.has_option("dual") and len(self.commands) != 6:
            logger.warning(f"is_valid: button {self.button.name} must have 6 commands for dual mode")
            return False
        elif not self.button.has_option("dual") and len(self.commands) != 4:
            logger.warning(f"is_valid: button {self.button.name} must have 4 commands")
            return False
        return True  # super().is_valid()

    def activate(self, state):
        if self.is_valid():
            if state < 2:
                super().activate(state)
            elif state == 2:  # rotate clockwise
                if self.is_on():
                    if self.button.has_option("dual"):
                        self.button.xp.commandOnce(self.commands[2])
                    else:
                        self.button.xp.commandOnce(self.commands[2])
                    self._turns = self._turns + 1
                    self._cw = self._cw + 1
                else:
                    if self.button.has_option("dual"):
                        self.button.xp.commandOnce(self.commands[4])
                    else:
                        self.button.xp.commandOnce(self.commands[2])
                    self._turns = self._turns - 1
                    self._ccw = self._ccw + 1
                self.view()
            elif state == 3:  # rotate counter-clockwise
                if self.is_on():
                    if self.button.has_option("dual"):
                        self.button.xp.commandOnce(self.commands[3])
                    else:
                        self.button.xp.commandOnce(self.commands[3])
                    self._turns = self._turns + 1
                    self._cw = self._cw + 1
                else:
                    if self.button.has_option("dual"):
                        self.button.xp.commandOnce(self.commands[5])
                    else:
                        self.button.xp.commandOnce(self.commands[3])
                    self._turns = self._turns - 1
                    self._ccw = self._ccw + 1
                self.view()
            else:
                logger.warning(f"activate: button {self.button.name} invalid state {state}")


class EncoderValue(Activation):
    """
    Activation that maintains an internal value and optionally write that value to a dataref
    """
    def __init__(self, config: dict, button: "Button"):
        Activation.__init__(self, config=config, button=button)

        self.step = float(config.get("step"))
        self.stepxl = float(config.get("stepxl"))
        self.value_min = float(config.get("value-min"))
        self.value_max = float(config.get("value-max"))
        self.writable_dataref = config.get("set-dataref")

        # Internal status
        self._turns = 0
        self._cw = 0
        self._ccw = 0

    def activate(self, state):
        super().activate(state)
        ok = False
        x = self.get_current_value()
        if x is None:
            x = 0
        if state == 2:  # rotate left
            x = x + self.step
            ok = True
            self._turns = self._turns + 1
            self._cw = self._cw + 1
        elif state == 3:  # rotate right
            x = x - self.step
            ok = True
            self._turns = self._turns - 1
            self._ccw = self._ccw + 1
        else:
            logger.warning(f"activate: {type(self).__name__} invalid state {state}")

        if ok:
            self.set_current_value(x)
            if self.writable_dataref is not None:
                self.button.xp.WriteDataRef(dataref=self.writable_dataref, value=vs, vtype='float')

#
# ###############################
# CURSOR TYPE ACTIVATION
#
#
class Slider(Activation):  # Cursor?
    """
    A Encoder that can turn left/right.
    """
    def __init__(self, config: dict, button: "Button"):
        Activation.__init__(self, config=config, button=button)

    def activate(self, state):
        super().activate(state)
        logger.info(f"activate: button {self.button.name} has no action (value={state})")

#
# ###############################
# SWIPE TYPE ACTIVATION (2D SURFACE)
#
#
class Swipe(Activation):
    """
    A Encoder that can turn left/right.
    """
    def __init__(self, config: dict, button: "Button"):
        Activation.__init__(self, config=config, button=button)

    def activate(self, state):
        super().activate(state)
        logger.info(f"activate: button {self.button.name} has no action (value={state})")


#
# ###############################
# ACTIVATIONS
#
#
ACTIVATIONS = {
    "none": Activation,
    "page": LoadPage,
    "reload": Reload,
    "inspect": Inspect,
    "stop": Stop,
    "push": Push,
    "longpress": Longpress,
    "onoff": OnOff,
    "updown": UpDown,
    "encoder": Encoder,
    "encoder-push": EncoderPush,
    "encoder-onoff": EncoderOnOff,
    "knob": EncoderValue,
    "slider": Slider,
    "cursor": Slider,
    "swipe": Swipe
}

