"""
Button action and activation abstraction
"""
import logging
import threading

from datetime import datetime

#from .constant import SPAM
from .color import is_integer

logger = logging.getLogger("Activation")
# logger.setLevel(SPAM)
# logger.setLevel(logging.DEBUG)

BACKPAGE_KEYWORD = "back"


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
        self._has_no_value = False
        self._inited = False
        # Options

        # Commands
        self._view = config.get("view")  # Optional additional command, usually to set a view
                                         # but could be anything.
        # Datarefs
        self.writable_dataref = config.get("set-dataref")

        # Working variables, internal state
        self._last_state = None

        self.activation_count = 0
        self.activations_count = {}
        self.last_activated = 0
        self.duration = 0
        self.pressed = False
        self.initial_value = config.get("initial-value")

        self.init()

    def init(self):  # ~ABC
        pass

    def button_name(self):
        return self.button.name if self.button is not None else 'no button'

    def activate(self, state):
        """
        Function that is executed when a button is activated (pressed, released, turned, etc.).
        Default is to tally number of times this button was pressed. It should have been released as many times :-D.
        **** No command gets executed here **** except if there is an associated view with the button.
        It removes guard if it was present and closed.
        """
        if not self._inited:
            self.init()
        self._last_state = state
        s = str(state)
        if s in self.activations_count:
            self.activations_count[s] = self.activations_count[s] + 1
        else:
            self.activations_count[s] = 1
        if state:
            self.activation_count = self.activation_count + 1
            self.last_activated = datetime.now().timestamp()
            logger.debug(f"activate: button {self.button_name()}: {type(self).__name__} activated")
            self.pressed = True

            # Guard handling
            if self.button.is_guarded():
                self._write_dataref(self.button.guarded, 1) # just open it
                logger.debug(f"activate: button {self.button_name()}: {type(self).__name__}: guard removed")
                return
        else:
            self.pressed = False
            self.duration = datetime.now().timestamp() - self.last_activated
            # Guard handling
            if self.button.guard is not None and not self.button.is_guarded() and self.duration > 2:
                self._write_dataref(self.button.guarded, 0) # close it
                logger.debug(f"activate: button {self.button_name()}: {type(self).__name__}: guard replaced")
                return

        # logger.debug(f"activate: {type(self).__name__} activated ({state}, {self.activation_count})")

    def get_datarefs(self) -> list:
        if self.writable_dataref is not None:
            return [ self.writable_dataref ]
        return []

    def _write_dataref(self, dataref, value: float):
        """
        Currently called in OnOff, UpDown and EncoderValue.
        Should be the last call in activate() if activation succeeded.
        """
        if dataref is not None:
            self.button.xp.WriteDataRef(dataref=dataref, value=value, vtype='float')
            logger.debug(f"write_dataref: button {self.button_name()}: {type(self).__name__} dataref {dataref} set to {value}")
        else:
            logger.debug(f"write_dataref: button {self.button_name()}: {type(self).__name__} has no set-dataref")

    def write_dataref(self, value: float):
        """
        Currently called in OnOff, UpDown and EncoderValue.
        Should be the last call in activate() if activation succeeded.
        """
        self._write_dataref(self.writable_dataref, value)

    def __str__(self):  # print its status
        return ", ".join([type(self).__name__,
                         f"activation-count: {self.activation_count}"])

    def view(self):
        if self._view is not None:
            self.button.xp.commandOnce(self._view)

    def is_pressed(self):
        return self.pressed

    def is_valid(self):
        if self.button is None:
            logger.warning(f"is_valid: {type(self).__name__} has no button")
            return False
        return True

    def inspect(self, what: str = None):
        logger.info(f"{self.button_name()}:{type(self).__name__}:")
        logger.info(f"is_valid: {self.is_valid()}")
        logger.info(f"view: {self._view}")
        logger.info(f"initial value: {self.initial_value}")

        logger.info(f"last state: {self._last_state}")

        logger.info(f"activation_count: {self.activation_count}")
        logger.info(f"activations_count: {self.activations_count}")
        logger.info(f"last_activated: {self.last_activated}")
        logger.info(f"last_activation_duration: {self.duration}")
        logger.info(f"pressed: {self.pressed}")

    def get_status(self):
        return {
            "activation_type": type(self).__name__,
            "activation_count": self.activation_count,
            "current_value": self.activation_count,     # !
            "all_activations": self.activations_count,
            "last_activated": self.last_activated,
            "last_activated_dt": datetime.fromtimestamp(self.last_activated).isoformat(),
            "initial_value": self.initial_value,
            "writable_dataref": self.writable_dataref
        }

    def describe(self):
        """
        Describe what the button does in plain English
        """
        return "\n\r".join([
            f"The button does nothing."
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
        self._has_no_value = True

        # Commands
        self.page = config.get("page", BACKPAGE_KEYWORD)  # default is to go to previously loaded page, if any
        self.remote_deck = config.get("deck")

    def is_valid(self):
        if self.page is None:
            logger.warning(f"is_valid: button {self.button_name()}: {type(self).__name__} has no page")
            return False
        return super().is_valid()

    def activate(self, state: bool):
        super().activate(state)
        decks = self.button.deck.cockpit.cockpit
        if self.remote_deck is not None and self.remote_deck not in decks.keys():
            logger.warning(f"activate: {type(self).__name__}: deck not found {self.remote_deck}")
            self.remote_deck = None
        if state:
            deck = self.button.deck
            if self.remote_deck is not None and self.remote_deck in decks.keys():
                deck = decks[self.remote_deck]

            if self.page == BACKPAGE_KEYWORD or self.page in deck.pages.keys():
                logger.debug(f"activate: {type(self).__name__} change page to {self.page}")
                new_name = deck.change_page(self.page)
            else:
                logger.warning(f"activate: {type(self).__name__}: page not found {self.page}")

    def describe(self):
        """
        Describe what the button does in plain English
        """
        deck = f"deck {self.remote_deck}" if self.remote_deck is not None else "the current deck"
        return "\n\r".join([
            f"The button loads page {self.page} on {deck}."
        ])


class Reload(Activation):
    """
    Reloads all decks.
    """
    def __init__(self, config: dict, button: "Button"):
        Activation.__init__(self, config=config, button=button)
        self._has_no_value = True

    def activate(self, state):
        if state:
            self.button.deck.cockpit.reload_decks()

    def describe(self):
        """
        Describe what the button does in plain English
        """
        return "\n\r".join([
            f"The button reloads all decks and tries to reload the page that was displayed."
        ])


class Inspect(Activation):
    """
    Inspect all decks.
    """
    def __init__(self, config: dict, button: "Button"):
        Activation.__init__(self, config=config, button=button)
        self._has_no_value = True

        self.what = config.get("what", "status")

    def activate(self, state):
        if state:
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
            f"The button displays '{self.what}' information about each cockpit, deck, page and/or button."
        ])


class Stop(Activation):
    """
    Stops all decks.
    """
    def __init__(self, config: dict, button: "Button"):
        Activation.__init__(self, config=config, button=button)
        self._has_no_value = True

    def activate(self, state):
        if state:
            self.button.deck.cockpit.stop()

    def describe(self):
        """
        Describe what the button does in plain English
        """
        return "\n\r".join([
            f"The button stops Cockpitdecks and terminates gracefully."
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

    # Default values
    AUTO_REPEAT_DELAY = 1     # seconds
    AUTO_REPEAT_SPEED = 0.2   # seconds

    def __init__(self, config: dict, button: "Button"):
        Activation.__init__(self, config=config, button=button)

        # Commands
        self.command = config.get("command")

        # Working variables
        self.pressed = False  # True while the button is pressed, False when released

        # Auto-repeat
        self.auto_repeat = self.button.has_option("auto-repeat")
        self.auto_repeat_delay = Push.AUTO_REPEAT_DELAY
        self.auto_repeat_speed = Push.AUTO_REPEAT_SPEED
        self.exit = None
        self.set_auto_repeat()

        self.onoff_current_value = None
        self.initial_value = config.get("initial-value")
        if self.initial_value is not None:
            if type(self.initial_value) == bool:
                self.onoff_current_value = self.initial_value
            else:
                self.onoff_current_value = self.initial_value != 0

    def __str__(self):  # print its status
        return super() + "\n" + ", ".join([
                f"command: {self.command}",
                f"is_valid: {self.is_valid()}"
        ])

    def set_auto_repeat(self):
        if not self.auto_repeat:
            return

        value = self.button.option_value("auto-repeat")
        if type(value) == bool:  # options: auto-repeat; uses default
            return
        elif "/" in str(value):  # options: auto-repeat=1/0.2; set both
            arr = value.split("/")
            if len(arr) > 1:
                self.auto_repeat_delay = float(arr[0])
                if self.auto_repeat_delay <= 0:
                    self.auto_repeat_delay = Push.AUTO_REPEAT_DELAY
                self.auto_repeat_speed = float(arr[1])
                if self.auto_repeat_speed <= 0:
                    self.auto_repeat_speed = Push.AUTO_REPEAT_SPEED
            elif len(arr) > 0:
                self.auto_repeat_speed = float(arr[0])
                if self.auto_repeat_speed <= 0:
                    self.auto_repeat_speed = Push.AUTO_REPEAT_SPEED
        else:  # options: auto-repeat=1; set speed only, default delay
            self.auto_repeat_speed = float(value)
            if self.auto_repeat_speed <= 0:
                self.auto_repeat_speed = Push.AUTO_REPEAT_SPEED
        logger.debug(f"set_auto_repeat: {self.auto_repeat_delay}, {self.auto_repeat_speed}")

    def is_on(self):
        value = self.button.get_current_value()
        if value is not None:
            if type(value) in [dict, tuple]:  # gets its value from internal state
                self.onoff_current_value = not self.onoff_current_value if self.onoff_current_value is not None else False
            elif type(value) == bool: # expect bool or number... (no check for number)
                    self.onoff_current_value = value
            else:
                self.onoff_current_value = self.initial_value != 0  # @todo: fails if not number...
            logger.debug(f"is_on: button {self.button_name()} is {self.onoff_current_value}")
        else:
            self.onoff_current_value = self.activation_count % 2 == 1
            logger.debug(f"is_on: button {self.button_name()} is {self.onoff_current_value} from internal state")

        return self.onoff_current_value

    def is_off(self):
        return not self.is_on()

    def is_valid(self):
        if self.command is None:
            logger.warning(f"is_valid: button {self.button_name()}: {type(self).__name__} has no command")
            return False
        return super().is_valid()

    def activate(self, state):
        super().activate(state)
        if state:
            self.button.xp.commandOnce(self.command)
            if self.auto_repeat and self.exit is None:
                self.auto_repeat_start()
            else:
                self.view()
        else:
            if self.auto_repeat:
                self.auto_repeat_stop()

    def describe(self):
        """
        Describe what the button does in plain English
        """
        return "\n\r".join([
            f"The button executes {self.command} when it is activated (pressed).",
            f"The button does nothing when it is de-activated (released)."
        ])

    # Auto repeat
    def auto_repeat_loop(self):
        self.exit.wait(self.auto_repeat_delay)
        while not self.exit.is_set():
            self.activate(self.pressed)
            self.exit.wait(self.auto_repeat_speed)
        logger.debug(f"auto_repeat: exited")

    def auto_repeat_start(self):
        """
        Starts auto_repeat
        """
        if self.exit is None:
            self.exit = threading.Event()
            self.thread = threading.Thread(target=self.auto_repeat_loop)
            self.thread.name = f"Activation::auto_repeat({self.button_name()})"
            self.thread.start()
        else:
            logger.warning(f"auto_repeat_start: button {self.button_name()}: already started")

    def auto_repeat_stop(self):
        """
        Stops auto_repeat
        """
        if self.exit is not None:
            self.exit.set()
            self.thread.join(timeout=2*self.auto_repeat_speed)
            if self.thread.is_alive():
                logger.warning(f"auto_repeat_stop: ..thread may hang..")
            else:
                self.exit = None
        else:
            logger.debug(f"auto_repeat_stop: button {self.button_name()}: already stopped")


class Longpress(Push):
    """
    Execute beginCommand while the key is pressed and endCommand when the key is released.
    """
    def __init__(self, config: dict, button: "Button"):

        Push.__init__(self, config=config, button=button)

    def activate(self, state):
        super().activate(state)
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
            f"The button begins command {self.command} when it is activated (pressed).",
            f"The button ends command {self.command} when it is de-activated (released).",
            f"(Begin and end command is a special terminology (phase of execution of a command) of X-Plane.)"
        ])


class OnOff(Activation):
    """
    Defines a On / Off push activation: Two commands are executed alternatively.
    On or Off status is determined by the number of time a button is pressed.
    """
    def __init__(self, config: dict, button: "Button"):

        # Commands
        self.commands = config.get("commands", [])

        # Internal variables
        self.onoff_current_value = None  # bool on or off, true = on
        self.initial_value = config.get("initial-value")

        Activation.__init__(self, config=config, button=button)


    def init(self):
        if self._inited:
            return
        value = self.button.get_current_value()
        if value is not None:
            if type(value) in [dict, tuple]:  # dataref, gets its value from internal state
                self.onoff_current_value = not self.onoff_current_value if self.onoff_current_value is not None else False
            else:
                self.onoff_current_value = value
            logger.debug(f"init: button {self.button_name()} initialized on/off at {self.onoff_current_value}")
        elif self.initial_value is not None:
            if type(self.initial_value) == bool: # expect bool or number... (no check for number)
                self.onoff_current_value = self.initial_value
            else:
                self.onoff_current_value = self.initial_value != 0
            logger.debug(f"init: button {self.button_name()} initialized on/off at {self.onoff_current_value} from initial-value")
        if self.onoff_current_value is not None:
            self._inited = True
        # self.onoff_current_value can still be None here...

    def __str__(self):  # print its status
        return super() + "\n" + ", ".join([f"commands: {self.commands}",
                        f"is_off: {self.is_off()}",
                        f"is_valid: {self.is_valid()}"])

    def num_commands(self) -> int:
        return len(self.commands) if self.commands is not None else 0

    def is_valid(self):
        if self.num_commands() > 0:
            if self.num_commands() < 2:
                logger.error(f"is_valid: button {self.button_name()}: {type(self).__name__} must have at least two commands")
                return False
        elif self.writable_dataref is None:
            logger.error(f"is_valid: button {self.button_name()}: {type(self).__name__} must have at least two commands or a dataref to write to")
            return False
        return super().is_valid()

    def is_on(self):
        value = self.button.get_current_value()
        if value is not None:
            if type(value) in [dict, tuple]:  # gets its value from internal state
                self.onoff_current_value = not self.onoff_current_value if self.onoff_current_value is not None else False
            elif type(value) == bool: # expect bool or number... (no check for number)
                    self.onoff_current_value = value
            else:
                self.onoff_current_value = value != 0  # @todo: fails if not number...
            logger.debug(f"is_on: button {self.button_name()} is {self.onoff_current_value}")
        else:
            self.onoff_current_value = self.activation_count % 2 == 1
            logger.debug(f"is_on: button {self.button_name()} is {self.onoff_current_value} from internal state")
        return self.onoff_current_value

    def is_off(self):
        return not self.is_on()

    def activate(self, state):
        super().activate(state)
        if state:
            if self.num_commands() > 1:
                if self.is_off():
                    self.button.xp.commandOnce(self.commands[0])
                else:
                    self.button.xp.commandOnce(self.commands[1])
            # Update current value and write dataref if present
            self.onoff_current_value = not self.onoff_current_value
            self.write_dataref(self.onoff_current_value)
            self.view()

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
        a = []
        if self.commands is not None and len(self.commands) > 1:
            a = a + [
                f"The button executes command {self.commands[0]} when its current value is OFF (0).",
                f"The button executes command {self.commands[1]} when its current value is ON (not 0).",
            ]
        a.append(f"The button does nothing when it is de-activated (released).")
        if self.writable_dataref is not None:
            a.append(f"The button writes its value in dataref {self.writable_dataref}.")

        if self.button.has_external_value():
            a.append(f"The button gets its current value from its button value (dataref, or formula).")
        else:
            a.append(f"The button gets its current value from an internal counter that increases by 1 each time it is pressed.")

        a.append(f"The current value is {'ON' if self.is_on() else 'OFF'}.")
        return "\n\r".join(a)


class UpDown(Activation):
    """
    Defines a button activation for a button that runs back and forth
    between 2 values like -2 1 0 1 2, or 0 1 2 3 4 3 2 1 0.
    Two commands are executed, one when the value increases,
    another one when the value decreases.
    """
    def __init__(self, config: dict, button: "Button"):
        # Commands
        self.commands = config.get("commands")

        # Internal status
        self.stops = None
        stops = config.get("stops", 2)
        if stops is not None:
            self.stops = int(stops)
        self.go_up = True
        self.stop_current_value = None

        Activation.__init__(self, config=config, button=button)

    def init(self):
        if self._inited:
            return
        value = self.button.get_current_value()
        if value is not None:
            self.stop_current_value = value
            if self.stop_current_value >= (self.stops - 1):
                self.stop_current_value = self.stops - 1
                self.go_up = False
            elif self.stop_current_value <= 0:
                self.stop_current_value = 0
                self.go_up = True
            logger.debug(f"init: button {self.button_name()} initialized stop at {self.stop_current_value}")
        elif self.initial_value is not None:
            if is_integer(self.initial_value):
                value = abs(self.initial_value)
                if value > self.stops - 1:
                    logger.warning(f"__init__: button {self.button_name()} initial value {value} too large. Set to {self.stops - 1}.")
                    value = self.stops - 1
                if self.initial_value < 0:
                    self.go_up = False # reverse direction
                self.initial_value = value
                self.stop_current_value = value
            logger.debug(f"init: button {self.button_name()} initialized stop at {self.stop_current_value} from initial-value")
        if self.stop_current_value is not None:
            self._inited = True

    def __str__(self):  # print its status
        return super() + "\n" + ", ".join([f"commands: {self.commands}",
                        f"stops: {self.stops}",
                        f"is_valid: {self.is_valid()}"])

    def num_commands(self):
        return len(self.commands) if self.commands is not None else 0

    def is_valid(self):
        if self.num_commands() > 0:
            if self.num_commands() < 2:
                logger.error(f"is_valid: button {self.button_name()}: {type(self).__name__} must have at least 2 commands")
                return False
        elif self.writable_dataref is None:
            logger.error(f"is_valid: button {self.button_name()}: {type(self).__name__} must have at least two commands or a dataref to write to")
            return False
        if self.stops is None or self.stops == 0:
            logger.error(f"is_valid: button {self.button_name()}: {type(self).__name__} must have a number of stops")
            return False
        return super().is_valid()

    def activate(self, state: bool):
        super().activate(state)
        if state:
            currval = self.stop_current_value
            if currval is None:
                currval = 0
                self.go_up = True
            nextval = int(currval + 1 if self.go_up else currval - 1)
            logger.debug(f"activate: {currval}, {nextval}, {self.go_up}")
            if self.go_up:
                if self.num_commands() > 0:
                    self.button.xp.commandOnce(self.commands[0])  # up
                if nextval >= (self.stops - 1):
                    nextval = self.stops - 1
                    self.go_up = False
            else:
                if self.num_commands() > 1:
                    self.button.xp.commandOnce(self.commands[1])  # down
                if nextval <= 0:
                    nextval = 0
                    self.go_up = True
            # Update current value and write dataref if present
            self.stop_current_value = nextval
            self.write_dataref(nextval)

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
        a = []
        if self.commands is not None and len(self.commands) > 1:
            a.append(f"The button executes command {self.commands[0]} when it increases its current value.")
            a.append(f"The button executes command {self.commands[1]} when it decreases its current value.")
        a.append(f"The button does nothing when it is de-activated (released).")
        if self.writable_dataref is not None:
            a.append(f"The button writes its value in dataref {self.writable_dataref}.")
        a.append(f"The button gets its curent value from an internal counter that increases or decreases by 1 each time it is pressed.")
        a.append(f"The current value is {self.stop_current_value}. Value will {'increase' if self.go_up else 'decrease'}")
        return "\n\r".join(a)

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

    def num_commands(self):
        return len(self.commands) if self.commands is not None else 0

    def is_valid(self):
        if self.num_commands() < 2:
            logger.error(f"is_valid: button {self.button_name()}: {type(self).__name__} must have at least 2 commands")
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
            logger.warning(f"activate: button {self.button_name()}: {type(self).__name__} invalid state {state}")

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
            logger.error(f"is_valid: button {self.button_name()}: {type(self).__name__} must have at least one command")

        self.longpush = self.button.has_option("longpush")

        # Internal status
        self._turns = 0
        self._cw = 0
        self._ccw = 0

    def num_commands(self):
        return len(self.commands) if self.commands is not None else 0

    def is_valid(self):
        if self.longpush and self.num_commands() != 4:
            logger.warning(f"is_valid: button {self.button_name()}: {type(self).__name__} must have 4 commands for longpush mode")
            return False
        elif not self.longpush and self.num_commands() != 3:
            logger.warning(f"is_valid: button {self.button_name()}: {type(self).__name__} must have 3 commands")
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
            logger.warning(f"activate: button {self.button_name()}: {type(self).__name__} invalid state {state}")

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

    def num_commands(self):
        return len(self.commands) if self.commands is not None else 0

    def is_valid(self):
        if self.dual and self.num_commands() != 6:
            logger.warning(f"is_valid: button {self.button_name()}: {type(self).__name__} must have 6 commands for dual mode")
            return False
        elif not self.dual and self.num_commands() != 4:
            logger.warning(f"is_valid: button {self.button_name()}: {type(self).__name__} must have 4 commands")
            return False
        return True  # super().is_valid()

    def activate(self, state):
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


class EncoderValue(OnOff):
    """
    Activation that maintains an internal value and optionally write that value to a dataref
    """
    def __init__(self, config: dict, button: "Button"):

        self.step = float(config.get("step", 1))
        self.stepxl = float(config.get("stepxl", 10))
        self.value_min = float(config.get("value-min", 0))
        self.value_max = float(config.get("value-max", 100))

        # Internal status
        self._turns = 0
        self._cw = 0
        self._ccw = 0
        self.encoder_current_value = 0

        OnOff.__init__(self, config=config, button=button)

    def init(self):
        if self._inited:
            return
        value = self.button.get_current_value()
        if value is not None:
            self.encoder_current_value = value
            logger.debug(f"init: button {self.button_name()} initialized on/off at {self.encoder_current_value}")
        elif self.initial_value is not None:
            self.encoder_current_value = self.initial_value
            logger.debug(f"init: button {self.button_name()} initialized on/off at {self.onoff_current_value} from initial-value")
        if self.encoder_current_value is not None:
            self._inited = True

    def is_valid(self):
        if self.writable_dataref is None:
            logger.error(f"is_valid: button {self.button_name()}: {type(self).__name__} must have a dataref to write to")
            return False
        return super().is_valid()

    def activate(self, state):
        if state < 2:
            if state:
                if self.is_off():
                    self.button.xp.commandOnce(self.commands[0])
                else:
                    self.button.xp.commandOnce(self.commands[1])
                # Update current value and write dataref if present
                self.onoff_current_value = not self.onoff_current_value
                self.view()
            return
        ok = False
        x = self.encoder_current_value
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
            self.encoder_current_value = x
            self.write_dataref(x)

    def get_status(self):
        a = super().get_status()
        if a is None:
            a = {}
        return a | {
            "step": self.step,
            "stepxl": self.stepxl,
            "value_min": self.value_min,
            "value_max": self.value_max,
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
    SLIDER_MAX = 8064
    SLIDER_MIN = -8192

    def __init__(self, config: dict, button: "Button"):
        Activation.__init__(self, config=config, button=button)

        self.value_min = float(config.get("value-min", 0))
        self.value_max = float(config.get("value-max", 100))
        self.value_step = float(config.get("value-step", 0))
        if self.value_min > self.value_max:
            temp = self.value_min
            self.value_min = self.value_max
            self.value_max = temp

    def is_valid(self):
        if self.writable_dataref is None:
            logger.error(f"is_valid: button {self.button_name()}: {type(self).__name__} must have a dataref to write to")
            return False
        return super().is_valid()

    def activate(self, state):
        super().activate(state)
        frac = abs(state - Slider.SLIDER_MAX) / (Slider.SLIDER_MAX - Slider.SLIDER_MIN)
        if self.value_step != 0:
            nstep = (self.value_max - self.value_min) / self.value_step
            frac = int(frac * nstep) / nstep
        value = self.value_min + frac * (self.value_max - self.value_min)
        logger.debug(f"activate: button {self.button_name()}: {type(self).__name__} written value={value} in {self.writable_dataref}")

    def describe(self):
        """
        Describe what the button does in plain English
        """
        a = [
            f"This slider produces a value between [{self.value_min}, {self.value_max}].",
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
        logger.info(f"activate: button {self.button_name()} has no action (value={state})")

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
    "encoder-value": EncoderValue,
    "knob": EncoderValue,
    "slider": Slider,
    "cursor": Slider,
    "swipe": Swipe
}

