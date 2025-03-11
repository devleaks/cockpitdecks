"""
Button action and activation abstraction
"""

import logging
import random
import subprocess

from cockpitdecks.event import PushEvent
from cockpitdecks import DECK_ACTIONS, CONFIG_KW, ID_SEP, instruction
from .activation import Activation

# from ...cockpit import CockpitInstruction

logger = logging.getLogger(__name__)
# from cockpitdecks import SPAM
# logger.setLevel(SPAM_LEVEL)
# logger.setLevel(logging.DEBUG)

INSTRUCTION_PREFIX = "cockpitdecks-"


class LoadPage(Activation):
    """
    Defines a Page change activation.
    """

    ACTIVATION_NAME = "page"
    REQUIRED_DECK_ACTIONS = [DECK_ACTIONS.PRESS, DECK_ACTIONS.LONGPRESS, DECK_ACTIONS.PUSH]

    KW_BACKPAGE = "back"

    PARAMETERS = {
        "page": {"type": "string", "prompt": "Page", "default-value": "back", "mandatory": True},
        "deck": {"type": "string", "prompt": "Remote deck", "optional": True},
    }

    def __init__(self, button: "Button"):
        Activation.__init__(self, button=button)

        # Activation arguments
        self.page = self._config.get("page", LoadPage.KW_BACKPAGE)  # default is to go to previously loaded page, if any
        self.remote_deck = self._config.get("deck")
        self.instruction = self.cockpit.instruction_factory(
            name=INSTRUCTION_PREFIX + "page",
            instruction_block={"page": self.page, "deck": self.remote_deck if self.remote_deck is not None else self.button.deck.name},
        )

    def is_valid(self):
        if self.page is None:
            logger.warning(f"button {self.button_name}: {type(self).__name__} has no page")
            return False
        return super().is_valid()

    def activate(self, event: PushEvent) -> bool:
        if not self.can_handle(event):
            return False
        if not super().activate(event):
            return False
        if event.pressed:
            self.instruction.execute()
        return True  # Normal termination

    def describe(self) -> str:
        """
        Describe what the button does in plain English
        """
        deck = f"deck {self.remote_deck}" if self.remote_deck is not None else "the current deck"
        return "\n\r".join([f"The button loads page {self.page} on {deck}."])


class Reload(Activation):
    """
    Reloads all decks.
    """

    ACTIVATION_NAME = "reload"
    REQUIRED_DECK_ACTIONS = [DECK_ACTIONS.PRESS, DECK_ACTIONS.LONGPRESS, DECK_ACTIONS.PUSH]

    PARAMETERS = {
        "deck": {
            "type": "string",
            "prompt": "Deck",
        }
    }

    def __init__(self, button: "Button"):
        Activation.__init__(self, button=button)
        self.deck = self._config.get("deck")
        self.instruction = None
        if self.deck is None:
            self.instruction = self.cockpit.instruction_factory(name=INSTRUCTION_PREFIX + "reload", instruction_block={})
        else:
            self.instruction = self.cockpit.instruction_factory(name=INSTRUCTION_PREFIX + "reload1", instruction_block={"deck": self.deck})

    def activate(self, event) -> bool:
        if not self.can_handle(event):
            return False
        if not event.pressed:  # trigger on button "release"
            self.instruction.execute()
            # if self.deck is not None:
            #     self.button.deck.cockpit.reload_deck(deck_name=self.deck)
            # else:
            #     self.button.deck.cockpit.reload_decks()
        return True

    def describe(self) -> str:
        """
        Describe what the button does in plain English
        """
        return "\n\r".join(["The button reloads all decks and tries to reload the page that was displayed."])


class ChangeTheme(Activation):
    """
    Reloads all decks.
    """

    ACTIVATION_NAME = "theme"
    REQUIRED_DECK_ACTIONS = [DECK_ACTIONS.PRESS, DECK_ACTIONS.LONGPRESS, DECK_ACTIONS.PUSH]

    PARAMETERS = {
        "theme": {
            "type": "string",
            "prompt": "Theme",
        }
    }

    def __init__(self, button: "Button"):
        Activation.__init__(self, button=button)

        # Activation arguments
        self.theme = self._config.get("theme")
        self.instruction = self.cockpit.instruction_factory(name=INSTRUCTION_PREFIX + "theme", instruction_block={"theme": self.theme})

    def is_valid(self):
        if self.theme is None:
            logger.warning(f"button {self.button_name}: {type(self).__name__} has no theme")
            return False
        return super().is_valid()

    def activate(self, event) -> bool:
        if not self.can_handle(event):
            return False
        if not self.is_valid():
            return False
        if not event.pressed:  # trigger on button "release"
            self.instruction.execute()
        return True  # normal termination

    def describe(self) -> str:
        """
        Describe what the button does in plain English
        """
        return "\n\r".join([f"The button switches between dark and light (night and day) themes and reload pages."])


class Inspect(Activation):
    """
    Inspect all decks.
    """

    ACTIVATION_NAME = "inspect"
    REQUIRED_DECK_ACTIONS = [DECK_ACTIONS.PRESS, DECK_ACTIONS.LONGPRESS, DECK_ACTIONS.PUSH]

    PARAMETERS = {
        "what": {
            "type": "choice",
            "prompt": "What to inspect",
            "default-value": "status",
            "choices": ["thread", "datarefs", "monitored", "print", "invalid", "status", "config", "valid", "desc", "dataref", "desc"],
        }
    }

    def __init__(self, button: "Button"):
        Activation.__init__(self, button=button)

        # Activation arguments
        self.what = self._config.get("what", "status")

    def activate(self, event) -> bool:
        if not self.can_handle(event):
            return False
        if event.pressed:
            self.button.deck.cockpit.inspect(self.what)
        return True  # normal termination

    def get_state_variables(self) -> dict:
        s = super().get_state_variables()
        if s is None:
            s = {}
        s = s | {"what": self.what}
        return s

    def describe(self) -> str:
        """
        Describe what the button does in plain English
        """
        return "\n\r".join([f"The button displays '{self.what}' information about each cockpit, deck, page and/or button."])


class Stop(Activation):
    """
    Stops all decks.
    """

    ACTIVATION_NAME = "stop"
    REQUIRED_DECK_ACTIONS = [DECK_ACTIONS.PRESS, DECK_ACTIONS.LONGPRESS, DECK_ACTIONS.PUSH]

    PARAMETERS = {}

    def __init__(self, button: "Button"):
        Activation.__init__(self, button=button)
        self.instruction = self.cockpit.instruction_factory(name=INSTRUCTION_PREFIX + self.ACTIVATION_NAME, instruction_block={})

    def activate(self, event) -> bool:
        if not self.can_handle(event):
            return False

        # Guard handling
        if not super().activate(event):
            return False

        if not self.is_guarded():
            if not event.pressed:  # trigger on button "release"
                self.instruction.execute()
        return True  # normal termination

    def describe(self) -> str:
        """
        Describe what the button does in plain English
        """
        return "\n\r".join(["The button stops Cockpitdecks and terminates gracefully."])


class StartSimulator(Activation):
    """
    Starts local copy of simulator software if not running.
    Currently only works on MacOS.
    """

    ACTIVATION_NAME = "simulator"
    REQUIRED_DECK_ACTIONS = [DECK_ACTIONS.PRESS, DECK_ACTIONS.LONGPRESS, DECK_ACTIONS.PUSH]

    PARAMETERS = {}

    def __init__(self, button: "Button"):
        Activation.__init__(self, button=button)

    def activate(self, event) -> bool:
        if not self.can_handle(event):
            return False

        # Guard handling
        if not super().activate(event):
            return False

        if not self.is_guarded():
            if not event.pressed:  # os dependent
                # 1. Should check it is already running, may be remote?
                # 2. Start it locally at least:
                # 2.a: build path from environ (SIM_HOME) and exe name (to be guesses or hardcoded)
                p = subprocess.Popen(["open", "/Users/pierre/X-Plane 12/X-Plane.app"])

        return True  # normal termination

    def describe(self) -> str:
        """
        Describe what the button does in plain English
        """
        return "\n\r".join(["The button stops Cockpitdecks and terminates gracefully."])


class Obs(Activation):
    """
    Stops all decks.
    """

    ACTIVATION_NAME = "obs"
    REQUIRED_DECK_ACTIONS = [DECK_ACTIONS.PRESS, DECK_ACTIONS.LONGPRESS, DECK_ACTIONS.PUSH]

    PARAMETERS = {
        "observable": {
            "type": "string",
            "prompt": "Observable",
        },
        "action": {
            "type": "choice",
            "prompt": "Action",
            "default-value": "toggle",
            "choices": ["toggle", "enable", "disable"],
        },
    }

    def __init__(self, button: "Button"):
        Activation.__init__(self, button=button)
        self.observable = self._config.get(CONFIG_KW.OBSERVABLE.value)
        self.instruction = self.cockpit.instruction_factory(
            name=INSTRUCTION_PREFIX + "obs", instruction_block={"observable": self.observable, "action": self._config.get(CONFIG_KW.ACTION.value, "toggle")}
        )

    def get_variables(self) -> set:
        if self.observable is not None:
            return {ID_SEP.join([CONFIG_KW.OBSERVABLE.value, self.observable])}
        return set()

    def activate(self, event) -> bool:
        if not self.can_handle(event):
            return False

        # Guard handling
        if not super().activate(event):
            return False

        if not self.is_guarded():
            if not event.pressed:  # trigger on button "release"
                self.instruction.execute()
        return True  # normal termination

    def describe(self) -> str:
        """
        Describe what the button does in plain English
        """
        return "\n\r".join(["The button enable, disable, or toggle (enable/disable) an observable."])


class Random(Activation):
    """
    Set the value of the button to a float random number between 0 and 1..
    """

    ACTIVATION_NAME = "random"
    REQUIRED_DECK_ACTIONS = [DECK_ACTIONS.PRESS, DECK_ACTIONS.LONGPRESS, DECK_ACTIONS.PUSH, DECK_ACTIONS.ENCODER]

    PARAMETERS = {}

    def __init__(self, button: "Button"):
        Activation.__init__(self, button=button)

        # Activation arguments
        self.random_value = 0.0

    def activate(self, event) -> bool:
        if not self.can_handle(event):
            return False
        if event.pressed:
            self.random_value = random.random()
        return True  # normal termination

    def get_state_variables(self) -> dict:
        s = super().get_state_variables()
        if s is None:
            s = {}
        s = s | {"random": self.random_value}
        return s

    def describe(self) -> str:
        """
        Describe what the button does in plain English
        """
        return "\n\r".join(["The button stops Cockpitdecks and terminates gracefully."])
