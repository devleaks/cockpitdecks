# ###########################
#
import logging

from cockpitdecks import DECK_ACTIONS
from cockpitdecks.buttons.activation import UpDown

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


class LightDimmer(UpDown):
    """Customized class to dim deck back lights according to up-down switch value"""

    ACTIVATION_NAME = "dimmer"
    REQUIRED_DECK_ACTIONS = [DECK_ACTIONS.PRESS, DECK_ACTIONS.LONGPRESS, DECK_ACTIONS.PUSH]

    def __init__(self, button: "Button"):
        UpDown.__init__(self, button=button)
        self.dimmer = self._config.get("dimmer", [10, 90])
        self.adjust_cockpit = self._config.get("adjust-cockpit", True)

    def activate(self, event):
        currval = self.stop_current_value
        if currval is not None and 0 <= currval < len(self.dimmer):
            self.button.deck.set_brightness(self.dimmer[currval])
            if self.adjust_cockpit:
                self.button.deck.cockpit.adjust_light(brightness=int(self.dimmer[currval]) / 100)
        super().activate(event)
