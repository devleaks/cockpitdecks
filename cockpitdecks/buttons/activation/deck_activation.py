"""
Button action and activation abstraction
"""

import logging
import threading

from cockpitdecks.constant import ID_SEP
from cockpitdecks.event import EncoderEvent, PushEvent, TouchEvent
from cockpitdecks.resources.color import is_integer
from cockpitdecks import CONFIG_KW, DECK_KW, DECK_ACTIONS
from cockpitdecks.resources.intvariables import COCKPITDECKS_INTVAR
from .activation import Activation

from .parameters import PARAM_DECK, PARAM_INITIAL_VALUE, PARAM_PUSH_AUTOREPEAT, PARAM_COMMAND_BLOCK
from .schemas import SCHEMA_DECK, SCHEMA_PUSH_AUTOREPEAT, SCHEMA_COMMAND_BLOCK

logger = logging.getLogger(__name__)
# from cockpitdecks import SPAM
# logger.setLevel(SPAM_LEVEL)
# logger.setLevel(logging.DEBUG)


class DeckActivation(Activation):
    """
    Base class for all deck activations.
    """

    ACTIVATION_NAME = "deck"

    PARAMETERS = Activation.PARAMETERS | PARAM_DECK

    SCHEMA = Activation.SCHEMA | SCHEMA_DECK

    def __init__(self, button: "Button"):
        Activation.__init__(self, button=button)


#
# ###############################
# PUSH-BUTTON TYPE ACTIVATIONS
#
#
class Push(DeckActivation):
    """
    Defines a Push activation.
    The supplied command is executed each time a button is pressed.
    """

    ACTIVATION_NAME = "push"
    REQUIRED_DECK_ACTIONS = [DECK_ACTIONS.PRESS, DECK_ACTIONS.LONGPRESS, DECK_ACTIONS.PUSH]

    PARAMETERS = DeckActivation.PARAMETERS | PARAM_PUSH_AUTOREPEAT | PARAM_INITIAL_VALUE | PARAM_COMMAND_BLOCK

    SCHEMA = DeckActivation.SCHEMA | SCHEMA_PUSH_AUTOREPEAT | SCHEMA_COMMAND_BLOCK

    # Default values
    AUTO_REPEAT_DELAY = 1  # seconds
    AUTO_REPEAT_SPEED = 0.2  # seconds

    def __init__(self, button: "Button"):
        DeckActivation.__init__(self, button=button)

        # Activation arguments
        # Command
        cmd = button._config.get(CONFIG_KW.COMMAND.value)
        if cmd is not None:
            cmdname = ":".join([self.button.get_id(), type(self).__name__])
            if type(cmd) is str:
                cmd = {CONFIG_KW.COMMAND.value: cmd}
            self._command = self.sim.instruction_factory(name=cmdname, instruction_block=cmd)

        # Working variables
        self.pressed = False  # True while the button is pressed, False when released

        # Auto-repeat
        self.auto_repeat = self.button.has_option("auto-repeat")
        self.auto_repeat_delay = Push.AUTO_REPEAT_DELAY
        self.auto_repeat_speed = Push.AUTO_REPEAT_SPEED
        self.exit = None
        self.set_auto_repeat()

        self.onoff_current_value = None
        self.initial_value = button._config.get("initial-value")
        if self.initial_value is not None:
            if type(self.initial_value) is bool:
                self.onoff_current_value = self.initial_value
            else:
                self.onoff_current_value = self.initial_value != 0

    def __str__(self):  # print its status
        return str(super()) + "\n" + ", ".join([f"command: {self._command}", f"is_valid: {self.is_valid()}"])

    def set_auto_repeat(self):
        if not self.auto_repeat:
            return

        value = self.button.option_value("auto-repeat")
        if type(value) is bool:  # options: auto-repeat; uses default
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
        logger.debug(f"{self.auto_repeat_delay}, {self.auto_repeat_speed}")

    def is_on(self):
        value = self.button.value
        if value is not None:
            if type(value) in [dict, tuple]:  # gets its value from internal state
                self.onoff_current_value = not self.onoff_current_value if self.onoff_current_value is not None else False
            elif type(value) is bool:  # expect bool or number... (no check for number)
                self.onoff_current_value = value
            else:
                self.onoff_current_value = self.initial_value != 0  # @todo: fails if not number...
            logger.debug(f"button {self.button_name} is {self.onoff_current_value}")
        else:
            self.onoff_current_value = self.activation_count % 2 == 1
            logger.debug(f"button {self.button_name} is {self.onoff_current_value} from internal state")

        return self.onoff_current_value

    def is_off(self):
        return not self.is_on()

    def is_valid(self):
        if self._command is None:
            logger.warning(f"button {self.button_name}: {type(self).__name__} has no command")
            return False
        return super().is_valid()

    def activate(self, event) -> bool:
        if not self.can_handle(event):
            return False
        if not super().activate(event):
            return False
        if event.pressed:
            if not (self.has_long_press() or self.has_beginend_command()):  # we don't have to wait for the release to trigger the command
                self._command.execute()
            if self.auto_repeat and self.exit is None:
                self.auto_repeat_start()
        else:
            if self.button.is_guarded():
                return False

            if (self.has_long_press() and not self.long_pressed()) and not self.has_beginend_command():
                self._command.execute()
            if self.auto_repeat:
                self.auto_repeat_stop()
        return True  # normal termination

    # Auto repeat
    def auto_repeat_loop(self):
        self.exit.wait(self.auto_repeat_delay)
        while not self.exit.is_set():
            self._command.execute()
            self.exit.wait(self.auto_repeat_speed)
        logger.debug("exited")

    def auto_repeat_start(self):
        """
        Starts auto_repeat
        """
        if self.exit is None:
            self.exit = threading.Event()
            self.thread = threading.Thread(target=self.auto_repeat_loop, name=f"Activation::auto_repeat({self.button_name})")
            self.thread.start()
        else:
            logger.warning(f"button {self.button_name}: already started")

    def auto_repeat_stop(self):
        """
        Stops auto_repeat
        """
        if self.exit is not None:
            self.exit.set()
            self.thread.join(timeout=2 * self.auto_repeat_speed)
            if self.thread.is_alive():
                logger.warning("..thread may hang..")
            else:
                self.exit = None
        else:
            logger.debug(f"button {self.button_name}: already stopped")

    def describe(self) -> str:
        """
        Describe what the button does in plain English
        """
        return "\n\r".join(
            [
                f"The button executes {self._command} when it is activated (pressed).",
                "The button does nothing when it is de-activated (released).",
            ]
        )


class BeginEndPress(Push):
    """
    Execute beginCommand while the key is pressed and endCommand when the key is released.
    """

    ACTIVATION_NAME = "begin-end-command"
    REQUIRED_DECK_ACTIONS = [DECK_ACTIONS.PRESS, DECK_ACTIONS.LONGPRESS, DECK_ACTIONS.PUSH]

    PARAMETERS = {"command": {"type": "string", "prompt": "Command", "mandatory": True}}

    PARAMETERS = {"command": {"type": "string", "prompt": "Command", "mandatory": True}}

    def __init__(self, button: "Button"):
        Push.__init__(self, button=button)

        # Command
        if self._command is not None:
            del self._command
        self._command = None
        cmd = button._config.get(CONFIG_KW.COMMAND.value)
        if cmd is not None:
            cmdname = ":".join([self.button.get_id(), type(self).__name__])
            self._command = self.sim.instruction_factory(name=cmdname, instruction_block={CONFIG_KW.BEGIN_END.value: cmd})

    def is_valid(self):
        # if type(self._command).__name__ != "BeginEndCommand":
        #     logger.warning(f"{self.button.get_id()}: {type(self)}: command is not BeginEndCommand: {type(self._command)}")
        #     return False
        return super().is_valid()

    def activate(self, event) -> bool:
        if not self.can_handle(event):
            return False
        if not super().activate(event):
            return False
        if event.pressed:
            self._command.execute()
            self.skip_view = True
        else:
            self._command.execute()
        return True  # normal termination

    def inspect(self, what: str | None = None):
        if what is not None and "activation" in what:
            super().inspect(what=what)

    def describe(self) -> str:
        """
        Describe what the button does in plain English
        """
        return "\n\r".join(
            [
                f"The button begins command {self._command} when it is activated (pressed).",
                f"The button ends command {self._command} when it is de-activated (released).",
                f"(Begin and end command is a special terminology (phase of execution of a command) of X-Plane.)",
            ]
        )


class OnOff(Activation):
    """
    Defines a On / Off push activation: Two commands are executed alternatively.
    On or Off status is determined by the number of time a button is pressed.
    """

    ACTIVATION_NAME = "onoff"
    REQUIRED_DECK_ACTIONS = [DECK_ACTIONS.PRESS, DECK_ACTIONS.LONGPRESS, DECK_ACTIONS.PUSH]

    PARAMETERS = PARAM_INITIAL_VALUE | {"commands": {"type": "sub", "list": PARAM_COMMAND_BLOCK, "min": 2, "max": 2}}

    SCHEMA = Activation.SCHEMA | {
        "commands": {"type": "list", "schema": SCHEMA_COMMAND_BLOCK, "minlength": 2, "maxlength": 2},
        "dataref": {"type": "string", "meta": {"label": "Dataref"}},
    }

    # PARAMETERS = PARAM_INITIAL_VALUE | {
    #     "commands": {"type": "sub", "list": [
    #             {"name": "command1", "type": "string", "prompt": "Command to turn on", "mandatory": True},
    #             {"name": "command2", "type": "string", "prompt": "Command to turn off", "mandatory": True},
    #         ]
    #     }
    # }

    def __init__(self, button: "Button"):
        Activation.__init__(self, button=button)

        # Activation arguments
        # Commands
        self._commands = []
        cmds = button._config.get(CONFIG_KW.COMMANDS.value)
        if cmds is not None:
            cmdname = ":".join([self.button.get_id(), type(self).__name__])
            self._commands = [self.sim.instruction_factory(name=cmdname, instruction_block={CONFIG_KW.COMMAND.value: cmd}) for cmd in cmds]

        # Internal variables
        self.onoff_current_value = False  # bool on or off, true = on

    def init(self):
        if self._inited:
            return
        if self.initial_value is not None:
            if type(self.initial_value) is bool:  # expect bool or number... (no check for number)
                self.onoff_current_value = self.initial_value
            else:
                self.onoff_current_value = self.initial_value != 0
            logger.debug(f"button {self.button_name} initialized on/off at {self.onoff_current_value} from initial-value")
        self._inited = True

    def __str__(self):  # print its status
        return (
            str(super())
            + "\n"
            + ", ".join(
                [
                    f"commands: {self._commands}",
                    f"is_off: {self.is_off()}",
                    f"is_valid: {self.is_valid()}",
                ]
            )
        )

    def num_commands(self) -> int:
        return len(self._commands) if self._commands is not None else 0

    def is_valid(self):
        if self.num_commands() > 0:
            if self.num_commands() < 2:
                logger.error(f"button {self.button_name}: {type(self).__name__} must have at least two commands")
                return False
        elif self._set_sim_data is None:
            logger.error(f"button {self.button_name}: {type(self).__name__} must have at least two commands or a dataref to write to")
            return False
        return super().is_valid()

    def is_on(self):
        value = self.button.value
        if value is not None:
            if type(value) in [dict, tuple]:  # gets its value from internal state
                self.onoff_current_value = not self.onoff_current_value if self.onoff_current_value is not None else False
            elif type(value) is bool:
                self.onoff_current_value = value
            elif type(value) in [int, float]:
                value = int(value)
                if self.button.has_option("modulo"):
                    self.onoff_current_value = value % 2 == 1
                else:  # option bool or binary
                    self.onoff_current_value = value != 0
            else:
                logger.debug(f"button {self.button_name} has special value ({value}), using internal state")
                self.onoff_current_value = self.activation_count % 2 == 1
            logger.debug(f"button {self.button_name} is {self.onoff_current_value}")
        else:
            self.onoff_current_value = self.activation_count % 2 == 1
            logger.debug(f"button {self.button_name} is {self.onoff_current_value} from internal state")
        return self.onoff_current_value

    def is_off(self):
        return not self.is_on()

    def activate(self, event) -> bool:
        if not self.can_handle(event):
            return False
        if not super().activate(event):
            return False
        if event.pressed:
            if self.num_commands() > 1:
                if self.is_off():
                    self._commands[0].execute()
                else:
                    self._commands[1].execute()
            # Update current value and write dataref if present
            self.onoff_current_value = not self.onoff_current_value
            # self.button.value = self.onoff_current_value  # update internal state
        return True  # normal termination

    def get_activation_value(self):
        return self.onoff_current_value

    def get_state_variables(self) -> dict:
        s = super().get_state_variables()
        if s is None:
            s = {}
        s = s | {COCKPITDECKS_INTVAR.ACTIVATION_ON.value: self.is_on()}
        return s

    def describe(self) -> str:
        """
        Describe what the button does in plain English
        """
        a = []
        if self._commands is not None and len(self._commands) > 1:
            a = a + [
                f"The button executes command {self._commands[0]} when its current value is OFF (0).",
                f"The button executes command {self._commands[1]} when its current value is ON (not 0).",
            ]
        a.append(f"The button does nothing when it is de-activated (released).")
        if self._set_sim_data is not None:
            a.append(f"The button writes its value in dataref {self._set_sim_data.name}.")

        # if self.button.has_external_value():
        #     a.append(f"The button gets its current value from its button value (dataref, or formula).")
        # else:
        #     a.append(f"The button gets its current value from internal parameters.")

        a.append(f"The current value is {'ON' if self.is_on() else 'OFF'}.")
        return "\n\r".join(a)


class ShortOrLongpress(Activation):
    """
    Execute beginCommand while the key is pressed and endCommand when the key is released.
    """

    ACTIVATION_NAME = "short-or-long-press"
    REQUIRED_DECK_ACTIONS = [DECK_ACTIONS.PRESS, DECK_ACTIONS.LONGPRESS, DECK_ACTIONS.PUSH]

    PARAMETERS = {
        "command-short": {"type": "string", "prompt": "Command short press", "mandatory": True},
        "command-long": {"type": "string", "prompt": "Command long press", "mandatory": True},
        "long-time": {"type": "float", "prompt": "Time"},
    }

    SCHEMA = {
        "command-short": {"type": "string", "meta": {"label": "Command short press"}, "required": True},
        "command-long": {"type": "string", "meta": {"label": "Command long press"}, "required": True},
        "long-time": {"type": "float", "meta": {"label": "Time"}},
    }

    def __init__(self, button: "Button"):
        Activation.__init__(self, button=button)

        # Activation arguments
        # Commands
        self._commands = []
        cmds = button._config.get(CONFIG_KW.COMMANDS.value)
        if cmds is not None:
            cmdname = ":".join([self.button.get_id(), type(self).__name__])
            self._commands = [self.sim.instruction_factory(name=cmdname, instruction_block={CONFIG_KW.COMMAND.value: cmd}) for cmd in cmds]

        # Internal variables
        self.long_time = self._config.get("long-time", 2)

    def activate(self, event) -> bool:
        if not self.can_handle(event):
            return False
        if not super().activate(event):
            return False
        if not event.pressed:
            if self.num_commands() > 1:
                if self.duration < self.long_time:
                    self._commands[0].execute()
                    logger.debug(f"short {self.duration}, {self.long_time}")
                else:
                    self._commands[1].execute()
                    logger.debug(f"looooong {self.duration}, {self.long_time}")
        return True  # normal termination

    def num_commands(self):
        return len(self._commands) if self._commands is not None else 0

    def inspect(self, what: str | None = None):
        if what is not None and "activation" in what:
            super().inspect(what=what)

    def describe(self) -> str:
        """
        Describe what the button does in plain English
        """
        return "\n\r".join(
            [
                f"The button executes {self._commands[0]} when it is activated shortly (pressed).",
                f"The button ends command {self._commands[1]} when it is de-activated after a long press (released after more than {self.long_time}secs.).",
                "(Begin and end command is a special terminology (phase of execution of a command) of X-Plane.)",
            ]
        )


class UpDown(Activation):
    """
    Defines a button activation for a button that runs back and forth
    between 2 values like -2 1 0 1 2, or 0 1 2 3 4 3 2 1 0.
    Two commands are executed, one when the value increases,
    another one when the value decreases.
    """

    ACTIVATION_NAME = "updown"
    REQUIRED_DECK_ACTIONS = [DECK_ACTIONS.PRESS, DECK_ACTIONS.LONGPRESS, DECK_ACTIONS.PUSH]

    PARAMETERS = PARAM_INITIAL_VALUE | {
        "commands": {"type": "sub", "list": PARAM_COMMAND_BLOCK, "min": 2, "max": 2},
        "stops": {"type": "integer", "prompt": "Number of stops", "default-value": 2},
    }

    SCHEMA = Activation.SCHEMA | {
        "commands": {"type": "list", "schema": SCHEMA_COMMAND_BLOCK, "minlength": 2, "maxlength": 2},
        "stops": {"type": "integer", "meta": {"label": "Number of stops", "default": 2}},
    }

    def __init__(self, button: "Button"):
        Activation.__init__(self, button=button)

        # Activation arguments
        self.stops = int(button._config.get("stops", 2))  # may fail
        # Commands
        self._commands = []
        cmds = button._config.get(CONFIG_KW.COMMANDS.value)
        if cmds is not None:
            cmdname = ":".join([self.button.get_id(), type(self).__name__])
            self._commands = [self.sim.instruction_factory(name=cmdname, instruction_block={CONFIG_KW.COMMAND.value: cmd}) for cmd in cmds]

        # Internal variables
        self.go_up = True
        self.stop_current_value = 0
        self.init_differed()

    def init_differed(self):
        if self._inited:
            return
        if self.initial_value is not None:
            if is_integer(self.initial_value):
                value = abs(self.initial_value)
                if value > self.stops - 1:
                    logger.warning(f"button {self.button_name} initial value {value} too large. Set to {self.stops - 1}.")
                    value = self.stops - 1
                if self.initial_value < 0:
                    self.go_up = False  # reverse direction
                self.initial_value = value
                self.stop_current_value = value
            logger.debug(f"button {self.button_name} initialized stop at {self.stop_current_value} from initial-value")
        if self.stop_current_value == 0:
            self.go_up = True
        elif self.stop_current_value == (self.stops - 1):
            self.go_up = False
        self._inited = True

    def __str__(self):  # print its status
        return (
            super().__str__()
            + "\n"
            + ", ".join(
                [
                    f"commands: {self._commands}",
                    f"stops: {self.stops}",
                    f"is_valid: {self.is_valid()}",
                ]
            )
        )

    def num_commands(self):
        return len(self._commands) if self._commands is not None else 0

    def is_valid(self):
        if self.num_commands() > 0:
            if self.num_commands() < 2:
                logger.error(f"button {self.button_name}: {type(self).__name__} must have at least 2 commands")
                return False
        elif self._set_sim_data is None:
            logger.error(f"button {self.button_name}: {type(self).__name__} must have at least two commands or a dataref to write to")
            return False
        if self.stops is None or self.stops == 0:
            logger.error(f"button {self.button_name}: {type(self).__name__} must have a number of stops")
            return False
        return super().is_valid()

    def activate(self, event) -> bool:
        if not self.can_handle(event):
            return False
        if not super().activate(event):
            return False
        if event.pressed:
            currval = self.button.value
            if currval is None:
                currval = 0
                self.go_up = True
            if currval > self.stops:
                currval = self.stops - 1
                self.go_up = False
            nextval = int(currval + 1 if self.go_up else currval - 1)
            logger.debug(f"{currval}, {nextval}, {self.go_up}")
            if self.stops > 2 and self.num_commands() > 2 and self.num_commands() == self.stops:
                self._commands[nextval].execute()
                if self.go_up:
                    if nextval >= (self.stops - 1):
                        nextval = self.stops - 1
                        self.go_up = False
                else:
                    if nextval <= 0:
                        nextval = 0
                        self.go_up = True
            else:
                if self.go_up:
                    if self.num_commands() > 0:
                        self._commands[0].execute()  # up
                    if nextval >= (self.stops - 1):
                        nextval = self.stops - 1
                        self.go_up = False
                else:
                    if self.num_commands() > 1:
                        self._commands[1].execute()  # down
                    if nextval <= 0:
                        nextval = 0
                        self.go_up = True
            # Update current value and write dataref if present
            self.stop_current_value = nextval
        return True  # normal termination

    def get_activation_value(self):
        return self.stop_current_value

    def get_state_variables(self) -> dict:
        s = super().get_state_variables()
        if s is None:
            s = {}
        s = s | {"stops": self.stops, "go_up": self.go_up, "stop": self.stop_current_value}
        return s

    def describe(self) -> str:
        """
        Describe what the button does in plain English
        """
        a = []
        if self._commands is not None and len(self._commands) > 1:
            a.append(f"The button executes command {self._commands[0]} when it increases its current value.")
            a.append(f"The button executes command {self._commands[1]} when it decreases its current value.")
        a.append(f"The button does nothing when it is de-activated (released).")
        if self._set_sim_data is not None:
            a.append(f"The button writes its value in dataref {self._set_sim_data.name}.")
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


class EncoderProperties:
    """Trait for property definitions"""

    def __init__(self, button: "Button"):
        # Encoder commands (and more if available)
        self._commands = []
        cmds = button._config.get(CONFIG_KW.COMMANDS.value)
        if cmds is not None:
            cmdname = ":".join([self.button.get_id(), type(self).__name__])
            self._commands = [self.sim.instruction_factory(name=cmdname, instruction_block={CONFIG_KW.COMMAND.value: cmd}) for cmd in cmds]

    @property
    def _turns(self):
        path = ID_SEP.join([self.get_id(), COCKPITDECKS_INTVAR.ENCODER_TURNS.value])
        dref = self.button.sim.get_internal_variable(path)
        value = dref.value
        return 0 if value is None else value

    @property
    def _cw(self):
        path = ID_SEP.join([self.get_id(), COCKPITDECKS_INTVAR.ENCODER_CLOCKWISE.value])
        dref = self.button.sim.get_internal_variable(path)
        value = dref.value
        return 0 if value is None else value

    @property
    def _ccw(self):
        path = ID_SEP.join([self.get_id(), COCKPITDECKS_INTVAR.ENCODER_COUNTER_CLOCKWISE.value])
        dref = self.button.sim.get_internal_variable(path)
        value = dref.value
        return 0 if value is None else value


class Encoder(Activation, EncoderProperties):
    """
    Defines a know with stepped value.
    One command is executed when the encoder is turned clockwise one step,
    another command is executed the encoder is turned counter-clockwise one step.
    """

    ACTIVATION_NAME = "encoder"
    REQUIRED_DECK_ACTIONS = DECK_ACTIONS.ENCODER

    PARAMETERS = PARAM_INITIAL_VALUE | {
        "commands": {"type": "sub", "list": PARAM_COMMAND_BLOCK, "min": 2, "max": 2},
        "stops": {"type": "integer", "prompt": "Number of stops", "default-value": 2},
    }

    SCHEMA = Activation.SCHEMA | {
        "commands": {"type": "list", "schema": SCHEMA_COMMAND_BLOCK, "minlength": 2, "maxlength": 2},
        "stops": {"type": "integer", "meta": {"label": "Number of stops", "default": 2}},
    }

    def __init__(self, button: "Button"):
        Activation.__init__(self, button=button)
        EncoderProperties.__init__(self, button=button)

    def num_commands(self):
        return len(self._commands) if self._commands is not None else 0

    def is_valid(self):
        if self.num_commands() < 2:
            logger.error(f"button {self.button_name}: {type(self).__name__} must have at least 2 commands")
            return False
        return super().is_valid()

    def activate(self, event) -> bool:
        if not self.can_handle(event):
            return False
        if not super().activate(event):
            return False
        if event.turned_counter_clockwise:  # rotate left
            self._commands[0].execute()
            self.inc(COCKPITDECKS_INTVAR.ENCODER_TURNS.value, -1)
            self.inc(COCKPITDECKS_INTVAR.ENCODER_COUNTER_CLOCKWISE.value)
        elif event.turned_clockwise:  # rotate right
            self._commands[1].execute()
            self.inc(COCKPITDECKS_INTVAR.ENCODER_TURNS.value, 1)
            self.inc(COCKPITDECKS_INTVAR.ENCODER_CLOCKWISE.value)
        else:
            logger.warning(f"button {self.button_name}: {type(self).__name__} invalid event {event.turned_clockwise, event.turned_counter_clockwise}")
        return True  # normal termination

    def get_activation_value(self):
        return self._turns

    def get_state_variables(self) -> dict:
        a = {
            COCKPITDECKS_INTVAR.ENCODER_CLOCKWISE.value: self._cw,
            COCKPITDECKS_INTVAR.ENCODER_COUNTER_CLOCKWISE.value: self._ccw,
            COCKPITDECKS_INTVAR.ENCODER_TURNS.value: self._turns,
        }
        return a | super().get_state_variables()

    def describe(self) -> str:
        """
        Describe what the button does in plain English
        """
        return "\n\r".join(
            [
                f"This encoder executes command {self._commands[0]} when it is turned clockwise.",
                f"This encoder executes command {self._commands[1]} when it is turned counter-clockwise.",
            ]
        )


class EncoderPush(Push, EncoderProperties):
    """
    Defines a encoder with stepped value coupled to a Push button.
    First command is executed when encoder is pushed.

    Without dual option:
    Second command is executed when the encoder is turned clockwise one step,
    Third command is executed the encoder is turned counter-clockwise one step.

    With longpush option:
    Command 0: Executed when turned clockwise and not pushed
    Command 1: Executed when turned counter-clockwise and not pushed
    Command 2: Executed when turned clockwise and pushed simultaneously
    Command 3: Executed when turned counter-clockwise and pushed simultaneously
    """

    ACTIVATION_NAME = "encoder-push"
    REQUIRED_DECK_ACTIONS = [DECK_ACTIONS.ENCODER, DECK_ACTIONS.PRESS, DECK_ACTIONS.LONGPRESS, DECK_ACTIONS.PUSH]

    PARAMETERS = PARAM_INITIAL_VALUE | {
        "commands": {"type": "sub", "list": PARAM_COMMAND_BLOCK, "min": 3, "max": 3},
    }

    SCHEMA = Activation.SCHEMA | {
        "commands": {"type": "list", "schema": {"type": "string"}, "minlength": 3, "maxlength": 3},
        "long-press": {"type": "string", "meta": {"label": "Long Press"}},
    }

    def __init__(self, button: "Button"):
        Push.__init__(self, button=button)
        EncoderProperties.__init__(self, button=button)

        # Activation arguments
        if len(self._commands) > 0:
            self._command = self._commands[0]
        else:
            logger.error(f"button {self.button_name}: {type(self).__name__} must have at least one command")

        self.longpush = self.button.has_option("longpush")

    def num_commands(self):
        return len(self._commands) if self._commands is not None else 0

    def is_valid(self):
        if self.longpush and self.num_commands() != 4:
            logger.warning(f"button {self.button_name}: {type(self).__name__} must have 4 commands for longpush mode")
            return False
        elif not self.longpush and self.num_commands() != 3:
            logger.warning(f"button {self.button_name}: {type(self).__name__} must have 3 commands")
            return False
        return True  # super().is_valid()

    def activate(self, event) -> bool:
        if not self.can_handle(event):
            return False

        # Pressed
        if type(event) is PushEvent:
            return super().activate(event)

        self.inc(COCKPITDECKS_INTVAR.ACTIVATION_COUNT.value)  # since super() not called

        # Turned
        if type(event) is EncoderEvent:
            if event.turned_counter_clockwise:  # rotate counter-clockwise
                if self.longpush:
                    if self.is_pressed():
                        self._commands[2].execute()
                        self.inc(COCKPITDECKS_INTVAR.ENCODER_TURNS.value, -1)
                        self.inc(COCKPITDECKS_INTVAR.ENCODER_COUNTER_CLOCKWISE.value)
                    else:
                        self._commands[0].execute()
                        self.inc(COCKPITDECKS_INTVAR.ENCODER_TURNS.value, -1)
                        self.inc(COCKPITDECKS_INTVAR.ENCODER_COUNTER_CLOCKWISE.value)
                    self.inc(COCKPITDECKS_INTVAR.ACTIVATION_LONGPUSH.value)
                else:
                    self._commands[1].execute()
                    self.inc(COCKPITDECKS_INTVAR.ENCODER_TURNS.value, -1)
                    self.inc(COCKPITDECKS_INTVAR.ENCODER_COUNTER_CLOCKWISE.value)
                    self.inc(COCKPITDECKS_INTVAR.ACTIVATION_SHORTPUSH.value)
            elif event.turned_clockwise:  # rotate clockwise
                if self.longpush:
                    if self.is_pressed():
                        self._commands[3].execute()
                        self.inc(COCKPITDECKS_INTVAR.ENCODER_TURNS.value)
                        self.inc(COCKPITDECKS_INTVAR.ENCODER_CLOCKWISE.value)
                    else:
                        self._commands[1].execute()
                        self.inc(COCKPITDECKS_INTVAR.ENCODER_TURNS.value)
                        self.inc(COCKPITDECKS_INTVAR.ENCODER_CLOCKWISE.value)
                    self.inc(COCKPITDECKS_INTVAR.ACTIVATION_LONGPUSH.value)
                else:
                    self._commands[2].execute()
                    self.inc(COCKPITDECKS_INTVAR.ENCODER_TURNS.value)
                    self.inc(COCKPITDECKS_INTVAR.ENCODER_CLOCKWISE.value)
                    self.inc(COCKPITDECKS_INTVAR.ACTIVATION_SHORTPUSH.value)
            return True

        logger.warning(f"button {self.button_name}: {type(self).__name__} invalid event {event}")
        return True  # normal termination

    def get_activation_value(self):
        return self._turns

    def get_state_variables(self) -> dict:
        a = {
            COCKPITDECKS_INTVAR.ENCODER_CLOCKWISE.value: self._cw,
            COCKPITDECKS_INTVAR.ENCODER_COUNTER_CLOCKWISE.value: self._ccw,
            COCKPITDECKS_INTVAR.ENCODER_TURNS.value: self._turns,
        }
        return a | super().get_state_variables()

    def describe(self) -> str:
        """
        Describe what the button does in plain English
        """
        if self.longpush:
            return "\n\r".join(
                [
                    f"This encoder has longpush option.",
                    f"This encoder executes command {self._commands[0]} when it is not pressed and turned clockwise.",
                    f"This encoder executes command {self._commands[1]} when it is not pressed and turned counter-clockwise.",
                    f"This encoder executes command {self._commands[2]} when it is pressed and turned clockwise.",
                    f"This encoder executes command {self._commands[3]} when it is pressed and turned counter-clockwise.",
                ]
            )
        else:
            return "\n\r".join(
                [
                    f"This encoder does not have longpush option.",
                    f"This encoder executes command {self._commands[0]} when it is pressed.",
                    f"This encoder does not execute any command when it is released.",
                    f"This encoder executes command {self._commands[1]} when it is turned clockwise.",
                    f"This encoder executes command {self._commands[2]} when it is turned counter-clockwise.",
                ]
            )


class EncoderOnOff(OnOff, EncoderProperties):
    """
    Defines a encoder with stepped value coupled to a OnOff button.
    First command is executed when button is Off and pressed.
    Second command is executed when button is On and pressed.
    Without dual option:
    Third command is execute when encoder is turned clockwise one step.
    Fourth command is executed the encoder is turned counter-clockwise one step.

    With dual option:
    Third command: Executed when turned clockwise and ON
    Fourth command: Executed when turned counter-clockwise and ON
    Fifth command: Executed when turned clockwise and OFF
    Sixth command: Executed when turned counter-clockwise and OFF
    """

    ACTIVATION_NAME = "encoder-onoff"
    REQUIRED_DECK_ACTIONS = [DECK_ACTIONS.ENCODER, DECK_ACTIONS.PRESS, DECK_ACTIONS.LONGPRESS, DECK_ACTIONS.PUSH]

    PARAMETERS = PARAM_INITIAL_VALUE | {
        "commands": {"type": "sub", "list": PARAM_COMMAND_BLOCK, "min": 4, "max": 4},
    }

    SCHEMA = Activation.SCHEMA | {
        "commands": {
            "type": "list",
            "schema": {"type": "string"},
            "minlength": 4,
            "maxlength": 4,
            "meta": {"label": "Commands"},
        },
    }

    def __init__(self, button: "Button"):
        OnOff.__init__(self, button=button)
        EncoderProperties.__init__(self, button=button)

        # Activation options
        self.dual = self.button.has_option("dual")

    def num_commands(self):
        return len(self._commands) if self._commands is not None else 0

    def is_valid(self):
        if self.dual and self.num_commands() != 6:
            logger.warning(f"button {self.button_name}: {type(self).__name__} must have 6 commands for dual mode")
            return False
        elif not self.dual and self.num_commands() != 4:
            logger.warning(f"button {self.button_name}: {type(self).__name__} must have 4 commands")
            return False
        return True  # super().is_valid()

    def activate(self, event) -> bool:
        if not self.can_handle(event):
            return False
        if type(event) is PushEvent:
            return super().activate(event)

        self.inc(COCKPITDECKS_INTVAR.ACTIVATION_COUNT.value)  # since super() not called

        if type(event) is EncoderEvent:
            if event.turned_clockwise:  # rotate clockwise
                if self.is_on():
                    if self.dual:
                        self._commands[2].execute()
                        self.inc(COCKPITDECKS_INTVAR.ACTIVATION_ON.value)
                    else:
                        self._commands[2].execute()
                        self.inc(COCKPITDECKS_INTVAR.ACTIVATION_OFF.value)
                    self.inc(COCKPITDECKS_INTVAR.ENCODER_TURNS.value)
                    self.inc(COCKPITDECKS_INTVAR.ENCODER_CLOCKWISE.value)
                else:
                    if self.dual:
                        self._commands[4].execute()
                    else:
                        self._commands[2].execute()
                    self.inc(COCKPITDECKS_INTVAR.ENCODER_TURNS.value)
                    self.inc(COCKPITDECKS_INTVAR.ENCODER_CLOCKWISE.value)
            elif event.turned_counter_clockwise:  # rotate counter-clockwise
                if self.is_on():
                    if self.dual:
                        self._commands[3].execute()
                        self.inc(COCKPITDECKS_INTVAR.ACTIVATION_ON.value)
                    else:
                        self._commands[3].execute()
                        self.inc(COCKPITDECKS_INTVAR.ACTIVATION_OFF.value)
                    self.inc(COCKPITDECKS_INTVAR.ENCODER_TURNS.value, -1)
                    self.inc(COCKPITDECKS_INTVAR.ENCODER_COUNTER_CLOCKWISE.value)
                else:
                    if self.dual:
                        self._commands[5].execute()
                    else:
                        self._commands[3].execute()
                    self.inc(COCKPITDECKS_INTVAR.ENCODER_TURNS.value, -1)
                    self.inc(COCKPITDECKS_INTVAR.ENCODER_COUNTER_CLOCKWISE.value)
            return True

        logger.warning(f"button {self.button_name}: {type(self).__name__} invalid event {event}")
        return True  # normal termination

    def get_activation_value(self):
        return self._turns

    def get_state_variables(self) -> dict:
        a = {
            COCKPITDECKS_INTVAR.ENCODER_CLOCKWISE.value: self._cw,
            COCKPITDECKS_INTVAR.ENCODER_COUNTER_CLOCKWISE.value: self._ccw,
            COCKPITDECKS_INTVAR.ENCODER_TURNS.value: self._turns,
        }
        return a | super().get_state_variables()

    def describe(self) -> str:
        """
        Describe what the button does in plain English
        """
        if self.dual:
            return "\n\r".join(
                [
                    f"This encoder has dual option.",
                    f"This encoder executes command {self._commands[0]} when it is pressed and OFF.",
                    f"This encoder executes command {self._commands[1]} when it is pressed and ON.",
                    f"This encoder does not execute any command when it is released.",
                    f"This encoder executes command {self._commands[2]} when it is OFF and turned clockwise.",
                    f"This encoder executes command {self._commands[3]} when it is OFF and turned counter-clockwise.",
                    f"This encoder executes command {self._commands[4]} when it is ON and turned clockwise.",
                    f"This encoder executes command {self._commands[5]} when it is ON and turned counter-clockwise.",
                ]
            )
        else:
            return "\n\r".join(
                [
                    f"This encoder does not have dual option.",
                    f"This encoder executes command {self._commands[0]} when it is pressed and OFF.",
                    f"This encoder executes command {self._commands[1]} when it is pressed and ON.",
                    f"This encoder does not execute any command when it is released.",
                    f"This encoder executes command {self._commands[2]} when it is turned clockwise.",
                    f"This encoder executes command {self._commands[3]} when it is turned counter-clockwise.",
                ]
            )


class EncoderValue(OnOff, EncoderProperties):
    """
    Activation that maintains an internal value and optionally write that value to a dataref
    """

    ACTIVATION_NAME = "encoder-value"
    REQUIRED_DECK_ACTIONS = [DECK_ACTIONS.ENCODER, DECK_ACTIONS.PRESS, DECK_ACTIONS.LONGPRESS, DECK_ACTIONS.PUSH]

    PARAMETERS = PARAM_INITIAL_VALUE | {
        "commands": {"type": "sub", "list": PARAM_COMMAND_BLOCK, "min": 4, "max": 4},
    }

    SCHEMA = Activation.SCHEMA | {
        "commands": {
            "type": "list",
            "schema": {"type": "string"},
            "minlength": 2,
            "maxlength": 4,
            "meta": {"label": "Commands"},
        },
        "value-min": {
            "type": "float",
            "meta": {"label": "Minimum value"},
        },
        "value-max": {
            "type": "float",
            "meta": {"label": "Maximum value"},
        },
        "step": {
            "type": "float",
            "meta": {"label": "Step value"},
        },
        "stepxl": {
            "type": "float",
            "meta": {"label": "Large step value"},
        },
        "set-dataref": {"type": "string", "meta": {"label": "Dataref to set"}},
        "dataref": {"type": "string", "meta": {"label": "Dataref"}},
        "value": {"type": "float", "meta": {"label": "Value"}},
    }

    def __init__(self, button: "Button"):
        OnOff.__init__(self, button=button)
        EncoderProperties.__init__(self, button=button)

        # Activation arguments
        self.step = float(button._config.get("step", 1))
        self.stepxl = float(button._config.get("stepxl", 10))
        self.value_min = float(button._config.get("value-min", 0))
        self.value_max = float(button._config.get("value-max", 100))

        # Internal variables
        self.encoder_current_value = 0
        self.onoff_current_value = False

        self.init_differed()

    def init_differed(self):
        if self._inited:
            return
        value = self.button.value
        if value is not None:
            self.encoder_current_value = value
            logger.debug(f"button {self.button_name} initialized on/off at {self.encoder_current_value}")
        elif self.initial_value is not None:
            self.encoder_current_value = self.initial_value
            logger.debug(f"button {self.button_name} initialized on/off at {self.onoff_current_value} from initial-value")
        if self.encoder_current_value is not None:
            self._inited = True

    def is_valid(self):
        if self._set_sim_data is None:
            logger.error(f"button {self.button_name}: {type(self).__name__} must have a dataref to write to")
            return False
        return super().is_valid()

    def is_on(self):
        # DO NOT fetch the button's value to determine on/off
        # On/off is a local state of this activation
        return self.onoff_current_value

    def activate(self, event) -> bool:
        if not self.can_handle(event):
            return False

        if type(event) is PushEvent:
            if event.pressed:
                if len(self._commands) > 1:
                    if self.is_off():  ## ISSUE: Uses button value to determine on (>=1) or off (-1<v<1)
                        self._commands[0].execute()
                    else:
                        self._commands[1].execute()
                else:
                    logger.debug(f"button {self.button_name} not enough commands {len(self._commands)}/é")
                # Update current value and write dataref if present
                self.onoff_current_value = not self.onoff_current_value
            return True

        self.inc(COCKPITDECKS_INTVAR.ACTIVATION_COUNT.value)  # since super() not called

        if type(event) is EncoderEvent:
            ok = False
            x = self.encoder_current_value
            if x is None:  # why?
                x = 0
            if event.turned_counter_clockwise:  # rotate left
                x = max(self.value_min, x - self.step)
                ok = True
                self.inc(COCKPITDECKS_INTVAR.ENCODER_TURNS.value, -1)
                self.inc(COCKPITDECKS_INTVAR.ENCODER_COUNTER_CLOCKWISE.value)
            elif event.turned_clockwise:  # rotate right
                x = min(self.value_max, x + self.step)
                ok = True
                self.inc(COCKPITDECKS_INTVAR.ENCODER_TURNS.value)
                self.inc(COCKPITDECKS_INTVAR.ENCODER_CLOCKWISE.value)
            else:
                logger.warning(f"{type(self).__name__} invalid event {event}")

            if ok:
                self.encoder_current_value = x
            return True

        logger.warning(f"button {self.button_name}: {type(self).__name__} invalid event {event}")
        return False

    def get_activation_value(self):
        # On/Off status accessible through state variable only
        return self.encoder_current_value

    def get_state_variables(self) -> dict:
        a = {
            "step": self.step,
            "stepxl": self.stepxl,
            "value_min": self.value_min,
            "value_max": self.value_max,
            COCKPITDECKS_INTVAR.ENCODER_CLOCKWISE.value: self._cw,
            COCKPITDECKS_INTVAR.ENCODER_COUNTER_CLOCKWISE.value: self._ccw,
            COCKPITDECKS_INTVAR.ENCODER_TURNS.value: self._turns,
            "on": self.onoff_current_value,
            "value": self.encoder_current_value,
        }
        return a | super().get_state_variables()

    def describe(self) -> str:
        """
        Describe what the button does in plain English
        """
        a = [
            f"This encoder increases a value by {self.step} when it is turned clockwise.",
            f"This encoder decreases a value by {self.step} when it is turned counter-clockwise.",
            f"The value remains in the range [{self.value_min}-{self.value_max}].",
        ]
        if self._set_sim_data is not None:
            a.append(f"The value is written in dataref {self._set_sim_data.name}.")
        return "\n\r".join(a)


class EncoderValueExtended(OnOff, EncoderProperties):
    """
    Activation that maintains an internal value and optionally write that value to a dataref
    """

    ACTIVATION_NAME = "encoder-value-extended"
    REQUIRED_DECK_ACTIONS = [DECK_ACTIONS.ENCODER, DECK_ACTIONS.PRESS, DECK_ACTIONS.LONGPRESS, DECK_ACTIONS.PUSH]

    PARAMETERS = {
        "value-min": {
            "type": "float",
            "prompt": "Minimum value",
        },
        "value-max": {
            "type": "float",
            "prompt": "Maximum value",
        },
        "step": {
            "type": "float",
            "prompt": "Step value",
        },
        "step-xl": {
            "type": "float",
            "prompt": "Large step value",
        },
        "set-dataref": {"type": "string", "prompt": "Dataref"},
    }

    SCHEMA = {
        "value-min": {
            "type": "float",
            "meta": {"label": "Minimum value"},
        },
        "value-max": {
            "type": "float",
            "meta": {"label": "Maximum value"},
        },
        "step": {
            "type": "float",
            "meta": {"label": "Step value"},
        },
        "step-xl": {
            "type": "float",
            "meta": {"label": "Large step value"},
        },
        "set-dataref": {"type": "string", "meta": {"label": "Dataref"}},
    }

    def __init__(self, button: "Button"):
        OnOff.__init__(self, button=button)
        EncoderProperties.__init__(self, button=button)

        # Activation arguments
        self.step = float(button._config.get("step", 1))
        self.stepxl = float(button._config.get("stepxl", 10))
        self.value_min = float(button._config.get("value-min", 0))
        self.value_max = float(button._config.get("value-max", 100))

        # Activation options
        self.options = button._config.get("options", None)

        # Internal variables
        self.encoder_current_value = float(button._config.get("initial-value", 1))
        self._step_mode = self.step

        self._local_dataref = None
        local_dataref = button._config.get("dataref", None)  # "local-dataref"
        if local_dataref is not None:
            self._local_dataref = self.button.sim.get_internal_variable(local_dataref)

        self.init_differed()

    def init_differed(self):
        if self._inited:
            return
        value = self.button.value
        if value is not None:
            self.encoder_current_value = value
            logger.debug(f"button {self.button_name} initialized on/off at {self.encoder_current_value}")
        elif self.initial_value is not None:
            self.encoder_current_value = self.initial_value
            logger.debug(f"button {self.button_name} initialized on/off at {self.onoff_current_value} from initial-value")
        if self.encoder_current_value is not None:
            self._inited = True

    def decrease(self, x):
        if self.options == "modulo":
            new_x = (x - self._step_mode - self.value_min) % (self.value_max - self.value_min + 1) + self.value_min
            return new_x
        else:
            x = x - self._step_mode
            if x < self.value_min:
                return self.value_min
            return x

    def increase(self, x):
        if self.options == "modulo":
            new_x = (x + self._step_mode - self.value_min) % (self.value_max - self.value_min + 1) + self.value_min
            return new_x
        else:
            x = x + self._step_mode
            if x > self.value_max:
                return self.value_max
            return x

    def is_valid(self):
        if self._set_sim_data is None:
            logger.error(f"button {self.button_name}: {type(self).__name__} must have a dataref to write to")
            return False
        return super().is_valid()

    def activate(self, event) -> bool:
        if not self.can_handle(event):
            return False

        if type(event) is PushEvent:
            if not super().activate(event):
                return False

            if event.pressed:

                if self.has_long_press() and self.long_pressed():
                    self.long_press(event)
                    logger.debug(f"button {self.button_name}: {type(self).__name__}: long pressed")
                    return

                if self._step_mode == self.step:
                    self._step_mode = self.stepxl
                else:
                    self._step_mode = self.step
                return True

        self.inc(COCKPITDECKS_INTVAR.ACTIVATION_COUNT.value)  # since super() not called

        if type(event) is EncoderEvent:
            ok = False
            x = self.encoder_current_value
            if x is None:
                x = 0
            if not hasattr(event, "pressed"):
                if event.turned_counter_clockwise:  # anti-clockwise
                    x = self.decrease(x)
                    ok = True
                    self.inc(COCKPITDECKS_INTVAR.ENCODER_TURNS.value, -1)
                    self.inc(COCKPITDECKS_INTVAR.ENCODER_COUNTER_CLOCKWISE.value)
                elif event.turned_clockwise:  # clockwise
                    x = self.increase(x)
                    ok = True
                    self.inc(COCKPITDECKS_INTVAR.ENCODER_TURNS.value)
                    self.inc(COCKPITDECKS_INTVAR.ENCODER_CLOCKWISE.value)
            if ok:
                self.encoder_current_value = x
                if self._local_dataref is not None:
                    self._local_dataref.update_value(new_value=x)
            return True

        logger.warning(f"button {self.button_name}: {type(self).__name__} invalid event {event}")
        return False

    def get_activation_value(self):
        return self.encoder_current_value

    def get_state_variables(self) -> dict:
        a = {
            "step": self.step,
            "stepxl": self.stepxl,
            "value_min": self.value_min,
            "value_max": self.value_max,
            COCKPITDECKS_INTVAR.ENCODER_CLOCKWISE.value: self._cw,
            COCKPITDECKS_INTVAR.ENCODER_COUNTER_CLOCKWISE.value: self._ccw,
            COCKPITDECKS_INTVAR.ENCODER_TURNS.value: self._turns,
        }
        return a | super().get_state_variables()

    def describe(self) -> str:
        """
        Describe what the button does in plain English
        """
        a = [
            f"This encoder increases a value by {self.step} when it is turned clockwise.",
            f"This encoder decreases a value by {self.step} when it is turned counter-clockwise.",
            f"The value remains in the range [{self.value_min}-{self.value_max}].",
        ]
        if self._set_sim_data is not None:
            a.append(f"The value is written in dataref {self._set_sim_data.name}.")
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

    ACTIVATION_NAME = "slider"
    REQUIRED_DECK_ACTIONS = DECK_ACTIONS.CURSOR

    SLIDER_MAX = 100
    SLIDER_MIN = -100

    PARAMETERS = {
        "value-min": {
            "type": "float",
            "prompt": "Minimum value",
        },
        "value-max": {
            "type": "float",
            "prompt": "Maximum value",
        },
        "step": {
            "type": "float",
            "prompt": "Step value",
        },
        "set-dataref": {"type": "string", "prompt": "Dataref"},
    }

    SCHEMA = {
        "value-min": {
            "type": "float",
            "meta": {"label": "Minimum value"},
        },
        "value-max": {
            "type": "float",
            "meta": {"label": "Maximum value"},
        },
        "step": {
            "type": "float",
            "meta": {"label": "Step value"},
        },
        "set-dataref": {"type": "string", "meta": {"label": "Dataref"}},
    }

    def __init__(self, button: "Button"):
        Activation.__init__(self, button=button)

        # Activation arguments
        self.value_min = float(self._config.get("value-min", 0))
        self.value_max = float(self._config.get("value-max", 100))
        self.value_step = float(self._config.get("value-step", 0))
        if self.value_min > self.value_max:
            temp = self.value_min
            self.value_min = self.value_max
            self.value_max = temp
        self.current_value = 0

        bdef = self.button.deck.deck_type.filter({DECK_KW.ACTION.value: DECK_ACTIONS.CURSOR.value})
        range_values = bdef[0].get(DECK_KW.RANGE.value)
        if range_values is not None and type(range_values) in [list, tuple]:
            Slider.SLIDER_MAX = max(range_values)
            Slider.SLIDER_MIN = min(range_values)

    def is_valid(self):
        if self._set_sim_data is None:
            logger.error(f"button {self.button_name}: {type(self).__name__} must have a dataref to write to")
            return False
        return super().is_valid()

    def activate(self, event) -> bool:
        if not self.can_handle(event):
            return False

        pct = abs(event.value - Slider.SLIDER_MIN) / (Slider.SLIDER_MAX - Slider.SLIDER_MIN)
        if self.value_step != 0:
            nstep = (self.value_max - self.value_min) / self.value_step
            pct = int(pct * nstep) / nstep
        value = self.value_min + pct * (self.value_max - self.value_min)
        self.current_value = value
        logger.debug(f"button {self.get_id()}: {type(self).__name__} written value={value} in {self._set_sim_data.name}")
        return True  # normal termination

    def get_activation_value(self):
        return self.current_value

    def describe(self) -> str:
        """
        Describe what the button does in plain English
        """
        a = [
            f"This slider produces a value between [{self.value_min}, {self.value_max}].",
            f"The raw value from slider is modified by formula {self.button.formula}.",
        ]
        if self._set_sim_data is not None:
            a.append(f"The value after modification by the formula is written in dataref {self._set_sim_data.name}.")
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

    ACTIVATION_NAME = "swipe"
    REQUIRED_DECK_ACTIONS = DECK_ACTIONS.SWIPE

    PARAMETERS = PARAM_COMMAND_BLOCK

    SCHEMA = SCHEMA_COMMAND_BLOCK

    def __init__(self, button: "Button"):
        Activation.__init__(self, button=button)

    def activate(self, event) -> bool:
        if not self.can_handle(event):
            return False
        logger.info(f"button {self.button_name} has no action (value={event})")
        return True  # normal termination

    def describe(self) -> str:
        """
        Describe what the button does in plain English
        """
        return "\n\r".join(
            [
                f"This surface is used to monitor swipes of a finger over the surface.",
                f"There currently is no handling of this type of activation.",
            ]
        )


class EncoderToggle(Activation, EncoderProperties):
    """
    Defines a encoder with stepped value coupled to an on/off button.

    On
    Command 0: Executed when turned clockwise
    Command 1: Executed when turned counter-clockwise
    Off
    Command 2: Executed when turned clockwise
    Command 3: Executed when turned counter-clockwise
    """

    ACTIVATION_NAME = "encoder-toggle"
    REQUIRED_DECK_ACTIONS = [DECK_ACTIONS.ENCODER, DECK_ACTIONS.PRESS, DECK_ACTIONS.LONGPRESS, DECK_ACTIONS.PUSH]

    PARAMETERS = PARAM_INITIAL_VALUE | {
        "commands": {"type": "sub", "list": PARAM_COMMAND_BLOCK, "min": 4, "max": 4},
    }

    SCHEMA = Activation.SCHEMA | {"commands": {"type": "list", "schema": SCHEMA_COMMAND_BLOCK, "minlength": 4, "maxlength": 4}}

    def __init__(self, button: "Button"):
        Activation.__init__(self, button=button)
        EncoderProperties.__init__(self, button=button)

        # Internal variables
        self.longpush = True
        self._on = True

    def num_commands(self):
        return len(self._commands) if self._commands is not None else 0

    def is_valid(self):
        if self.num_commands() != 4:
            logger.warning(f"button {self.button_name}: {type(self).__name__} must have 4 commands")
            return False
        return True  # super().is_valid()

    def activate(self, event) -> bool:
        if not self.can_handle(event):
            return False

        if type(event) is PushEvent:
            if not super().activate(event):
                return False
            if event.pressed and self._on:
                self._on = False
            elif event.pressed and not self._on:
                self._on = True
            return True

        self.inc(COCKPITDECKS_INTVAR.ACTIVATION_COUNT.value)  # since super() not called

        if type(event) is EncoderEvent:
            if event.turned_counter_clockwise and not self.is_pressed():  # rotate anti clockwise
                if self._on:
                    self._commands[0].execute()
                else:
                    self._commands[2].execute()
                self.inc(COCKPITDECKS_INTVAR.ENCODER_TURNS.value, -1)
                self.inc(COCKPITDECKS_INTVAR.ENCODER_COUNTER_CLOCKWISE.value)

            elif event.turned_clockwise and not self.is_pressed():  # rotate clockwise
                if self._on:
                    self._commands[1].execute()
                    self.inc(COCKPITDECKS_INTVAR.ACTIVATION_ON.value)
                else:
                    self._commands[3].execute()
                    self.inc(COCKPITDECKS_INTVAR.ACTIVATION_OFF.value)
                self.inc(COCKPITDECKS_INTVAR.ENCODER_TURNS.value)
                self.inc(COCKPITDECKS_INTVAR.ENCODER_CLOCKWISE.value)
            return True

        logger.warning(f"button {self.button_name}: {type(self).__name__} invalid event {event}")
        return False  # normal termination

    def get_state_variables(self) -> dict:
        a = {
            COCKPITDECKS_INTVAR.ENCODER_CLOCKWISE.value: self._cw,
            COCKPITDECKS_INTVAR.ENCODER_COUNTER_CLOCKWISE.value: self._ccw,
            COCKPITDECKS_INTVAR.ENCODER_TURNS.value: self._turns,
        }
        return a | super().get_state_variables()

    def describe(self) -> str:
        """
        Describe what the button does in plain English
        """
        if self.longpush:
            return "\n\r".join(
                [
                    f"This encoder has longpush option.",
                    f"This encoder executes command {self._commands[0]} when it is not pressed and turned clockwise.",
                    f"This encoder executes command {self._commands[1]} when it is not pressed and turned counter-clockwise.",
                    f"This encoder executes command {self._commands[2]} when it is pressed and turned clockwise.",
                    f"This encoder executes command {self._commands[3]} when it is pressed and turned counter-clockwise.",
                ]
            )
        else:
            return "\n\r".join(
                [
                    f"This encoder does not have longpush option.",
                    f"This encoder executes command {self._commands[0]} when it is pressed.",
                    f"This encoder does not execute any command when it is released.",
                    f"This encoder executes command {self._commands[1]} when it is turned clockwise.",
                    f"This encoder executes command {self._commands[2]} when it is turned counter-clockwise.",
                ]
            )


#
# ###############################
# Touch screen activation for Mosaic-like icons
# (large icons composed from multiple icons)
#
class Mosaic(Activation):
    """
    Defines a Push activation.
    The supplied command is executed each time a button is pressed.
    (May be this proxy/transfer/indirection/forward could be done in driver?)
    """

    ACTIVATION_NAME = "mosaic"
    REQUIRED_DECK_ACTIONS = [DECK_ACTIONS.SWIPE, DECK_ACTIONS.PUSH]

    PARAMETERS = PARAM_PUSH_AUTOREPEAT | PARAM_INITIAL_VALUE | PARAM_COMMAND_BLOCK

    SCHEMA = Activation.SCHEMA | SCHEMA_PUSH_AUTOREPEAT | SCHEMA_COMMAND_BLOCK

    # Default values
    AUTO_REPEAT_DELAY = 1  # seconds
    AUTO_REPEAT_SPEED = 0.2  # seconds

    def __init__(self, button: "Button"):
        Activation.__init__(self, button=button)

        # Working variables
        self.pressed = False  # True while the button is pressed, False when released

    def __str__(self):  # print its status
        return str(super()) + "\n" + f", is_valid: {self.is_valid()}"

    def is_valid(self):
        return super().is_valid()

    def activate(self, event) -> bool:
        if not self.can_handle(event):
            return False
        if not super().activate(event):
            return False

        if type(event) is TouchEvent:
            coords = event.xy()
            button_def = self.button._definition.mosaic.get_button(x=coords[0], y=coords[1])
            if button_def is not None:
                logger.info(f"found button def {button_def.name}")
                button = self.button.page.find_button(button_def)
                if button is not None:
                    logger.info(f"found button {button.index}")
                    PushEvent(deck=event.deck, button=button.index, pressed=event.start is None)
            else:
                logger.debug(f"coordinates {coords} does not hit a button")

            return True
        else:  # swipe event
            logger.warning("swiped: {event.touched_only()}, {event.xy()}")
        # determine which tile was hit
        # activate proper event in tile
        return False  # normal termination

    def describe(self) -> str:
        """
        Describe what the button does in plain English
        """
        return "\n\r".join(
            [
                f"The button converts its swipe event into a push event for a tile.",
            ]
        )
