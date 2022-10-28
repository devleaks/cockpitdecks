# ###########################
# Knob-like buttons, with or without push capabilities
#
import logging
import threading
import time

from .button_core import Button, ButtonPush, ButtonDual

from .XTouchMini.Devices.xtouchmini import LED_MODE


logger = logging.getLogger("Knob")
# logger.setLevel(logging.DEBUG)


class KnobNone(Button):
    """
    A Knob that can turn left/right.
    """
    def __init__(self, config: dict, page: "Page"):
        Button.__init__(self, config=config, page=page)

    def has_key_image(self):
        return False

    def is_valid(self):
        return super().is_valid()

    def activate(self, state):
        logger.info(f"activate: button {self.name} has no action")

    def render(self):
        """
        No rendering for knobs, but render screen next to it in case it carries status.
        """
        disp = "left" if self.index[-1] == "L" else "right"
        if disp in self.page.buttons.keys():
            logger.debug(f"render: button {self.name} rendering {disp}")
            self.page.buttons[disp].render()


class Knob(KnobNone):
    """
    A Knob that can turn left/right.
    """
    def __init__(self, config: dict, page: "Page"):
        KnobNone.__init__(self, config=config, page=page)

    def is_valid(self):
        logger.warning(f"is_valid: button {self.name} must have 2 commands")
        return True  # super().is_valid()

    def activate(self, state):
        if state == 2:  # rotate left
            self.xp.commandOnce(self.commands[0])
        elif state == 3:  # rotate right
            self.xp.commandOnce(self.commands[1])
        else:
            logger.warning(f"activate: button {self.name} invalid state {state}")


class KnobPush(ButtonPush):
    """
    A Push button that can turn left/right.
    """
    def __init__(self, config: dict, page: "Page"):
        ButtonPush.__init__(self, config=config, page=page)

    def has_key_image(self):
        return False  # default

    def is_valid(self):
        if self.has_option("dual") and len(self.commands) != 4:
            logger.warning(f"is_valid: button {self.name} must have 4 commands for dual mode")
            return False
        elif not self.has_option("dual") and len(self.commands) != 2:
            logger.warning(f"is_valid: button {self.name} must have 2 commands")
            return False
        return True  # super().is_valid()

    def activate(self, state):
        if state < 2:
            super().activate(state)
        elif state == 2:  # rotate left
            if self.has_option("dual"):
                if self.is_pushed():
                    self.xp.commandOnce(self.commands[0])
                else:
                    self.xp.commandOnce(self.commands[2])
            else:
                self.xp.commandOnce(self.commands[0])
        elif state == 3:  # rotate right
            if self.has_option("dual"):
                if self.is_pushed():
                    self.xp.commandOnce(self.commands[1])
                else:
                    self.xp.commandOnce(self.commands[3])
            else:
                self.xp.commandOnce(self.commands[1])
        else:
            logger.warning(f"activate: button {self.name} invalid state {state}")

    def render(self):
        """
        No rendering for knobs, but render screen next to it in case it carries status.
        """
        disp = "left" if self.index[-1] == "L" else "right"
        if disp in self.page.buttons.keys():
            logger.debug(f"render: button {self.name} rendering {disp}")
            self.page.buttons[disp].render()


class KnobPushPull(ButtonDual):
    """
    A Push button that can turn left/right.
    """
    def __init__(self, config: dict, page: "Page"):
        ButtonDual.__init__(self, config=config, page=page)

    def has_key_image(self):
        return False  # default

    def is_valid(self):
        if self.has_option("dual") and len(self.commands) != 6:
            logger.warning(f"is_valid: button {self.name} must have 6 commands for dual mode")
            return False
        elif len(self.commands) != 4:
            logger.warning(f"is_valid: button {self.name} must have 4 commands")
            return False
        return True  # super().is_valid()

    def activate(self, state):
        if state < 2:
            super().activate(state)
        elif state == 2:  # rotate left
            if self.has_option("dual"):
                if self.is_pushed():
                    self.xp.commandOnce(self.commands[2])
                else:
                    self.xp.commandOnce(self.commands[4])
            else:
                self.xp.commandOnce(self.commands[2])
        elif state == 3:  # rotate right
            if self.has_option("dual"):
                if self.is_pushed():
                    self.xp.commandOnce(self.commands[3])
                else:
                    self.xp.commandOnce(self.commands[5])
            else:
                self.xp.commandOnce(self.commands[3])
        else:
            logger.warning(f"activate: button {self.name} invalid state {state}")

    def render(self):
        """
        No rendering for knobs, but render screen next to it in case it carries status.
        """
        disp = "left" if self.index[-1] == "L" else "right"
        if disp in self.page.buttons.keys():
            logger.debug(f"render: button {self.name} rendering {disp}")
            self.page.buttons[disp].render()


class KnobPushTurnRelease(ButtonPush):
    """
    A know button that can turn left/right either when pressed or released.
    """
    def __init__(self, config: dict, page: "Page"):
        ButtonPush.__init__(self, config=config, page=page)

    def has_key_image(self):
        return False  # default

    def is_valid(self):
        if len(self.commands) != 4:
            logger.warning(f"is_valid: button {self.name} must have 4 commands for dual mode")
            return False
        return True  # super().is_valid()

    def activate(self, state):
        if state < 2:
            super().activate(state)
        elif state == 2:  # rotate left
            if self.pressed:
                self.xp.commandOnce(self.commands[2])
            else:
                self.xp.commandOnce(self.commands[0])
        elif state == 3:  # rotate right
            if self.pressed:
                self.xp.commandOnce(self.commands[3])
            else:
                self.xp.commandOnce(self.commands[1])
        else:
            logger.warning(f"activate: button {self.name} invalid state {state}")

    def render(self):
        """
        No rendering for knobs, but render screen next to it in case it carries status.
        """
        disp = "left" if self.index[-1] == "L" else "right"
        if disp in self.page.buttons.keys():
            logger.debug(f"render: button {self.name} rendering {disp}")
            self.page.buttons[disp].render()


class KnobDataref(ButtonPush):
    """
    A knob button that writes directly to a dataref.
    """
    def __init__(self, config: dict, page: "Page"):
        ButtonPush.__init__(self, config=config, page=page)
        self.step = config.get("step")
        self.stepxl = config.get("stepxl")
        self.value = config.get("value")
        self.value_min = config.get("value-min")
        self.value_max = config.get("value-max")

    def has_key_image(self):
        return False  # default

    def is_valid(self):
        return True  # super().is_valid()

    def activate(self, state):
        if state < 2:
            super().activate(state)
        elif state == 2:  # rotate left
            step = self.step
            if self.has_option("dual") and self.is_pushed():
                step = self.stepxl
            self.value = self.value - step
            if self.value < self.value_min:
                self.value = self.value_min
            if self.dataref in self.xp.all_datarefs:
                vs = float(self.value)
                self.xp.WriteDataRef(dataref=self.dataref, value=vs, vtype='float')
                logger.debug(f"activate: button {self.name} dataref {self.dataref} = {vs} written")
            else:
                logger.warning(f"activate: button {self.name} dataref {self.dataref} not found")
        elif state == 3:  # rotate right
            step = self.step
            if self.has_option("dual") and self.is_pushed():
                step = self.stepxl
            self.value = self.value + step
            if self.value > self.value_max:
                self.value = self.value_max
            if self.dataref in self.xp.all_datarefs:  # need to be there at least because we also read it...
                vs = float(self.value)
                self.xp.WriteDataRef(dataref=self.dataref, value=vs, vtype='float')
                logger.debug(f"activate: button {self.name} dataref {self.dataref} = {vs} written")
            else:
                logger.warning(f"activate: button {self.name} dataref {self.dataref} not found")
        else:
            logger.warning(f"activate: button {self.name} invalid state {state}")

    def dataref_changed(self, dataref: "Dataref"):
        """
        One of its dataref has changed, records its value and provoke an update of its representation.
        """
        super().dataref_changed(dataref)
        self.value = self.current_value

    def render(self):
        """
        No rendering for knobs, but render screen next to it in case it carries status.
        """
        disp = "left" if self.index[-1] == "L" else "right"
        if disp in self.page.buttons.keys():
            logger.debug(f"render: button {self.name} rendering {disp}")
            self.page.buttons[disp].render()


class KnobLED(Knob):
    """
    A knob button that writes directly to a dataref.
    """
    def __init__(self, config: dict, page: "Page"):
        Knob.__init__(self, config=config, page=page)
        self.mode = config.get("led-mode", LED_MODE.SINGLE.value)
        if self.mode < 0 or self.mode > len(LED_MODE)-1:
            logger.warning(f"__init__: button {self.name}: invalid mode value {self.mode}, using default")
            self.mode = LED_MODE.SINGLE
        else:
            self.mode = LED_MODE(self.mode)  # assumes values are 0, 1, ... , N.

    def get_led(self):
        logger.debug(f"get_led: button {self.name}: returning {self.current_value}, {self.mode}")
        return int(self.current_value), self.mode

    def render(self):
        """
        Ask deck to set this button's image on the deck.
        set_key_image will call this button get_button function to get the icon to display with label, etc.
        """
        if self.deck is not None:
            if self.on_current_page():
                self.deck.set_key_image(self)
                # logger.debug(f"render: button {self.name} rendered")
            else:
                logger.debug(f"render: button {self.name} not on current page")
        else:
            logger.debug(f"render: button {self.name} has no deck")

    def clean(self):
        self.previous_value = None  # this will provoke a refresh of the value on data reload
        # should clean LED
