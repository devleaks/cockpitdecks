"""
Button action and activation abstraction
"""
import logging
import yaml
from datetime import datetime

from .color import is_integer

logger = logging.getLogger("Activation")
# logger.setLevel(logging.DEBUG)

BACKPAGE = "back"


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
        self.last_activated = 0
        self.pressed = False
        self.initial_value = config.get("initial-value")

        self.previous_value = None
        self.current_value = None

        if self.initial_value is not None:
            self.current_value = self.initial_value
            self._first_value = self.initial_value
            self._first_value_not_saved = False
            logger.debug(f"activate: button {self.button.name}: initial value set: {self.initial_value}")

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
        return ", ".join([type(self).__name__,
                         f"activation-count: {self.activation_count}",
                         f"current: {self.current_value}",
                         f"previous: {self.previous_value}"])

    def is_pressed(self):
        return self.pressed

    def inspect(self, what: str = None):
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
            self._first_value = value
            self._first_value_not_saved = False
        self.previous_value = self.current_value
        self.current_value = value
        logger.debug(f"set_current_value: {self.current_value}")

    def get_current_value(self):
        logger.debug(f"get_current_value: {self.current_value}")
        return self.current_value

    def is_valid(self):
        if self.button is None:
            logger.warning(f"is_valid: activation {type(self).__name__} has no button")
            return False
        return True

    def get_status(self):
        return {
            "activation_type": type(self).__name__,
            "activation_count": self.activation_count,
            "last_activated": self.last_activated,
            "last_activated_dt": datetime.fromtimestamp(self.last_activated).isoformat(),
            "initial_value": self.initial_value,
            "previous_value": self.previous_value,
            "current_value": self.current_value,
            "guarded": self.guarded
        }

    def view(self):
        if self._view is not None and self.is_valid():
            self.button.xp.commandOnce(self._view)

    def describe(self):
        """
        Describe what the button does in plain English
        """
        return "\n\r".join([
            f"This button does nothing. This is the default 'none' behavior."
        ])


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
        self.page = config.get("page", BACKPAGE)  # default is to go to previously loaded page, if any
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

            if self.page == BACKPAGE or self.page in deck.pages.keys():
                logger.debug(f"activate: {type(self).__name__} change page to {self.page}")
                new_name = deck.change_page(self.page)
                if new_name is not None and self.page != BACKPAGE:
                    self.set_current_value(new_name)
            else:
                logger.warning(f"activate: {type(self).__name__}: page not found {self.page}")

    def describe(self):
        """
        Describe what the button does in plain English
        """
        deck = f"deck {self.remote_deck}" if self.remote_deck is not None else "the current deck"
        return "\n\r".join([
            f"This button loads page {self.page} on {deck}."
        ])


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

    def describe(self):
        """
        Describe what the button does in plain English
        """
        return "\n\r".join([
            f"This button reloads all decks and tries to reload the page that was displayed."
        ])


class Inspect(Activation):
    """
    Inspect all decks.
    """
    def __init__(self, config: dict, button: "Button"):
        Activation.__init__(self, config=config, button=button)

        self.what = config.get("what", "status")

    def activate(self, state):
        if state:
            if self.is_valid():
                self.button.deck.cockpit.inspect(self.what)

    def get_status(self):
        s = super().get_status()
        if s is None:
            s = {}
        s = s | {
            "what": self.what
        }
        return s

    def describe(self):
        """
        Describe what the button does in plain English
        """
        return "\n\r".join([
            f"This button displays '{self.what}' information about each cockpit, deck, page and/or button."
        ])


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

    def describe(self):
        """
        Describe what the button does in plain English
        """
        return "\n\r".join([
            f"This button stops Cockpitdecks and terminates gracefully."
        ])

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
        return super() + "\n" + ", ".join([
                f"command: {self.command}",
                f"is_valid: {self.is_valid()}"
        ])

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

    def describe(self):
        """
        Describe what the button does in plain English
        """
        return "\n\r".join([
            f"This button executes {self.command} when it is activated (pressed).",
            f"This button does nothing when it is de-activated (released)."
        ])


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

    def describe(self):
        """
        Describe what the button does in plain English
        """
        return "\n\r".join([
            f"This button begins command {self.command} when it is activated (pressed).",
            f"This button ends command {self.command} when it is de-activated (released).",
            f"(Begin and end command is a special terminology (phase of execution of a command) of X-Plane.)"
        ])


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
        return super() + "\n" + ", ".join([f"commands: {self.commands}",
                        f"is_off: {self.is_off()}",
                        f"is_valid: {self.is_valid()}"])

    def is_valid(self):
        if len(self.commands) < 2:
            logger.error(f"is_valid: button {type(self).__name__} must have at least two command")
            return False
        return super().is_valid()

    def get_current_value(self):
        parent = self.button.get_current_value()
        if parent is not None:
            return 0 if parent == 0 else 1
        else:
            return self.activation_count % 2

    def is_on(self):
        return self.get_current_value() == 1

    def is_off(self):
        return self.get_current_value() == 0

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

    def get_status(self):
        s = super().get_status()
        if s is None:
            s = {}
        s = s | {
            "on": self.is_on()
        }
        return s

    def describe(self):
        """
        Describe what the button does in plain English
        """
        a = [
            f"This button executes command {self.commands[0]} when its current value is OFF (0).",
            f"This button executes command {self.commands[1]} when its current value is ON (not 0).",
            f"This button does nothing when it is de-activated (released)."
        ]
        if False:
            a.append(f"This button gets its curent value from its button value (dataref, or formula).")
        else:
            a.append(f"This button gets its curent value from an internal counter that increases by 1 each time it is pressed.")
            a.append(f"The current value is {self.current_value} (={'ON' if self.is_on() else 'OFF'}).")
        return "\n\r".join(a)


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
        stops = config.get("stops", 2)
        if stops is not None:
            self.stops = int(stops)
        self.bounce_arr = self.make_bounce_array(self.stops)  # convenient
        self.go_up = True

        # We redo initial value setting...
        if self.initial_value is not None and is_integer(self.initial_value):
            value = abs(self.initial_value)
            if value > self.stops - 1:
                logger.warning(f"__init__: button {self.button.name} initial value {value} too large. Set to {self.stops - 1}.")
                value = self.stops - 1
            if self.initial_value < 0:
                self.go_up = False # reverse direction
            self.initial_value = value
            self.current_value = value

    def __str__(self):  # print its status
        return super() + "\n" + ", ".join([f"commands: {self.commands}",
                        f"stops: {self.stops}",
                        f"is_valid: {self.is_valid()}"])

    def is_valid(self):
        if self.commands is None or len(self.commands) < 2:
            logger.error(f"is_valid: button {self.button.name} must have at least 2 commands")
            return False
        if self.stops is None or self.stops == 0:
            logger.error(f"is_valid: button {self.button.name} must have a number of stops")
            return False
        return True

    def get_current_value(self):
        parent = self.button.get_current_value()
        if parent is not None:
            return parent
        else:
            return self.bounce_arr[(self._first_value + self.activation_count) % len(self.bounce_arr)]

    def activate(self, state: bool):
        super().activate(state)
        # We need to do something if button does not start in status 0. @todo
        # if self.start_value is None:
        #     if self.current_value is not None:
        #         self.start_value = int(self.current_value)
        #     else:
        #         self.start_value = 0
        if self.is_valid():
            if state:
                if self._first_value_not_saved:
                    if self.initial_value is None:
                        self._first_value = 0
                        self.current_value = 0
                    else:
                        self._first_value = int(self.initial_value)
                        self.current_value = int(self.initial_value)
                    self._first_value_not_saved = False

                self.current_value = self.get_current_value()
                nextval = int(self.current_value + 1 if self.go_up else self.current_value - 1)
                if self.go_up:
                    self.button.xp.commandOnce(self.commands[0])  # up
                    if nextval == (self.stops - 1):
                        self.go_up = False
                else:
                    self.button.xp.commandOnce(self.commands[1])  # down
                    if nextval == 0:
                        self.go_up = True
        else:
            logger.warning(f"activate: button {self.button.name} is invalid")

    def make_bounce_array(self, stops: int):
        # Builds an array like 0-1-2-3-2-1-0 for a 4 stops button.
        # @todo: can bounce 0-1-2-1-0-1-2... or not 0-1-2-0-1-2-0...
        if stops > 1:
            af = list(range(stops - 1))
            ab = af.copy()
            ab.reverse()
            return af + [stops-1] + ab[:-1]
        return [0]

    def get_status(self):
        s = super().get_status()
        if s is None:
            s = {}
        s = s | {
            "stops": self.stops,
            "go_up": self.go_up
        }
        return s

    def describe(self):
        """
        Describe what the button does in plain English
        """
        return "\n\r".join([
            f"This button executes command {self.commands[0]} when it increases its current value.",
            f"This button executes command {self.commands[1]} when it decreases its current value.",
            f"This button does nothing when it is de-activated (released).",
            f"This button gets its curent value from an internal counter that increases or decreases by 1 each time it is pressed.",
            f"The current value is {self.current_value}. Value will {'increase' if self.go_up else 'decrease'}"])

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
        if a is None:
            a = {}
        return a | {
            "cw": self._cw,
            "ccw": self._ccw,
            "turns": self._turns
        }

    def describe(self):
        """
        Describe what the button does in plain English
        """
        return "\n\r".join([
            f"This encoder executes command {self.commands[0]} when it is turned clockwise.",
            f"This encoder executes command {self.commands[1]} when it is turned counter-clockwise."
        ])


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

        self.longpush = self.button.has_option("longpush")

        # Internal status
        self._turns = 0
        self._cw = 0
        self._ccw = 0

    def is_valid(self):
        if self.longpush and len(self.commands) != 4:
            logger.warning(f"is_valid: button {self.button.name} must have 4 commands for longpush mode")
            return False
        elif not self.longpush and len(self.commands) != 3:
            logger.warning(f"is_valid: button {self.button.name} must have 3 commands")
            return False
        return True  # super().is_valid()

    def activate(self, state):
        if state < 2:
            super().activate(state)
        elif state == 2:  # rotate clockwise
            if self.longpush:
                if self.is_pressed():
                    self.button.xp.commandOnce(self.commands[2])
                    self._turns = self._turns + 1
                    self._cw = self._cw + 1
                else:
                    self.button.xp.commandOnce(self.commands[0])
                    self._turns = self._turns - 1
                    self._ccw = self._ccw + 1
            else:
                self.button.xp.commandOnce(self.commands[1])
        elif state == 3:  # rotate counter-clockwise
            if self.longpush:
                if self.is_pressed():
                    self.button.xp.commandOnce(self.commands[3])
                    self._turns = self._turns + 1
                    self._cw = self._cw + 1
                else:
                    self.button.xp.commandOnce(self.commands[1])
                    self._turns = self._turns - 1
                    self._ccw = self._ccw + 1
            else:
                self.button.xp.commandOnce(self.commands[2])
        else:
            logger.warning(f"activate: button {self.button.name} invalid state {state}")

    def get_status(self):
        a = super().get_status()
        if a is None:
            a = {}
        return a | {
            "cw": self._cw,
            "ccw": self._ccw,
            "turns": self._turns
        }

    def describe(self):
        """
        Describe what the button does in plain English
        """
        if self.longpush:
            return "\n\r".join([
                f"This encoder has longpush option.",
                f"This encoder executes command {self.commands[0]} when it is not pressed and turned clockwise.",
                f"This encoder executes command {self.commands[1]} when it is not pressed and turned counter-clockwise.",
                f"This encoder executes command {self.commands[2]} when it is pressed and turned clockwise.",
                f"This encoder executes command {self.commands[3]} when it is pressed and turned counter-clockwise.",
            ])
        else:
            return "\n\r".join([
                f"This encoder does not have longpush option.",
                f"This encoder executes command {self.commands[0]} when it is pressed.",
                f"This encoder does not execute any command when it is released.",
                f"This encoder executes command {self.commands[1]} when it is turned clockwise.",
                f"This encoder executes command {self.commands[2]} when it is turned counter-clockwise."
            ])


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


        self.dual = self.button.has_option("dual")

        # Internal status
        self._turns = 0
        self._cw = 0
        self._ccw = 0

    def is_valid(self):
        if self.dual and len(self.commands) != 6:
            logger.warning(f"is_valid: button {self.button.name} must have 6 commands for dual mode")
            return False
        elif not self.dual and len(self.commands) != 4:
            logger.warning(f"is_valid: button {self.button.name} must have 4 commands")
            return False
        return True  # super().is_valid()

    def activate(self, state):
        if self.is_valid():
            if state < 2:
                super().activate(state)
            elif state == 2:  # rotate clockwise
                if self.is_on():
                    if self.dual:
                        self.button.xp.commandOnce(self.commands[2])
                    else:
                        self.button.xp.commandOnce(self.commands[2])
                    self._turns = self._turns + 1
                    self._cw = self._cw + 1
                else:
                    if self.dual:
                        self.button.xp.commandOnce(self.commands[4])
                    else:
                        self.button.xp.commandOnce(self.commands[2])
                    self._turns = self._turns - 1
                    self._ccw = self._ccw + 1
                self.view()
            elif state == 3:  # rotate counter-clockwise
                if self.is_on():
                    if self.dual:
                        self.button.xp.commandOnce(self.commands[3])
                    else:
                        self.button.xp.commandOnce(self.commands[3])
                    self._turns = self._turns + 1
                    self._cw = self._cw + 1
                else:
                    if self.dual:
                        self.button.xp.commandOnce(self.commands[5])
                    else:
                        self.button.xp.commandOnce(self.commands[3])
                    self._turns = self._turns - 1
                    self._ccw = self._ccw + 1
                self.view()
            else:
                logger.warning(f"activate: button {self.button.name} invalid state {state}")

    def get_status(self):
        a = super().get_status()
        if a is None:
            a = {}
        return a | {
            "cw": self._cw,
            "ccw": self._ccw,
            "turns": self._turns
        }

    def describe(self):
        """
        Describe what the button does in plain English
        """
        if self.dual:
            return "\n\r".join([
                f"This encoder has dual option.",
                f"This encoder executes command {self.commands[0]} when it is pressed and OFF.",
                f"This encoder executes command {self.commands[1]} when it is pressed and ON.",
                f"This encoder does not execute any command when it is released.",
                f"This encoder executes command {self.commands[2]} when it is OFF and turned clockwise.",
                f"This encoder executes command {self.commands[3]} when it is OFF and turned counter-clockwise.",
                f"This encoder executes command {self.commands[4]} when it is ON and turned clockwise.",
                f"This encoder executes command {self.commands[5]} when it is ON and turned counter-clockwise.",
            ])
        else:
            return "\n\r".join([
                f"This encoder does not have dual option.",
                f"This encoder executes command {self.commands[0]} when it is pressed and OFF.",
                f"This encoder executes command {self.commands[1]} when it is pressed and ON.",
                f"This encoder does not execute any command when it is released.",
                f"This encoder executes command {self.commands[2]} when it is turned clockwise.",
                f"This encoder executes command {self.commands[3]} when it is turned counter-clockwise."
            ])


class EncoderValue(Activation):
    """
    Activation that maintains an internal value and optionally write that value to a dataref
    """
    def __init__(self, config: dict, button: "Button"):
        Activation.__init__(self, config=config, button=button)

        self.step = float(config.get("step", 1))
        self.stepxl = float(config.get("stepxl", 10))
        self.value_min = float(config.get("value-min", 0))
        self.value_max = float(config.get("value-max", 100))
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
                self.button.xp.WriteDataRef(dataref=self.writable_dataref, value=float(x), vtype='float')

    def get_status(self):
        a = super().get_status()
        if a is None:
            a = {}
        return a | {
            "step": self.step,
            "stepxl": self.stepxl,
            "value_min": self.value_min,
            "value_max": self.value_max,
            "writable_dataref": self.set_dataref,
            "cw": self._cw,
            "ccw": self._ccw,
            "turns": self._turns
        }

    def describe(self):
        """
        Describe what the button does in plain English
        """
        a = [
            f"This encoder increases a value by {self.step} when it is turned clockwise.",
            f"This encoder decreases a value by {self.step} when it is turned counter-clockwise.",
            f"The value remains in the range [{self.value_min}-{self.value_max}]."
        ]
        if self.writable_dataref is not None:
            a.append(f"The value is written in dataref {self.writable_dataref}.")
        return "\n\r".join(a)


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

        self.value_min = float(config.get("value-min", 0))
        self.value_max = float(config.get("value-max", 100))
        self.writable_dataref = config.get("set-dataref")

    def activate(self, state):
        super().activate(state)
        logger.info(f"activate: button {self.button.name} has no action (value={state})")

    def describe(self):
        """
        Describe what the button does in plain English
        """
        a = [
            f"This slider produces a value between [{self.value_min}-{self.value_max}].",
            f"The raw value from slider is modified by formula {self.button.formula}."
        ]
        if self.writable_dataref is not None:
            a.append(f"The value is written in dataref {self.writable_dataref}.")
        return "\n\r".join(a)


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

    def describe(self):
        """
        Describe what the button does in plain English
        """
        return "\n\r".join([
            f"This surface is used to monitor swipes of a finger over the surface.",
            f"There currently is no handling of this type of activation."
        ])


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

