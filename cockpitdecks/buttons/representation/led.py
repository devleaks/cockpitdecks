"""
Representation for LED.
"""

import logging


from cockpitdecks import DECK_FEEDBACK
from .representation import Representation

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


#
# ###############################
# LED TYPE REPRESENTATION
#
#
class LED(Representation):

    REPRESENTATION_NAME = "led"
    REQUIRED_DECK_FEEDBACKS = DECK_FEEDBACK.LED

    PARAMETERS = {
        "led": {"type": "string", "prompt": "LED", "default-value": "single"},
    }

    def __init__(self, button: "Button"):
        Representation.__init__(self, button=button)

        self.mode = self._config.get("led", "single")  # unused

    def render(self):
        value = self.get_button_value()
        v = value is not None and value != 0
        return (v, self.mode)

    def clean(self):
        old_value = self.button.value
        self.button.value = 0  # switch it off for the clean display
        self.button.render()
        self.button.value = old_value

    def describe(self) -> str:
        """
        Describe what the button does in plain English
        """
        a = ["The representation turns ON or OFF a single LED light"]
        return "\n\r".join(a)
