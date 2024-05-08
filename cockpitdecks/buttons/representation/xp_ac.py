# ###########################
# Representation that displays the content of sim/aircraft/view/acf_ICAO on an icon.
# These buttons are highly XP specific.
#
import logging

from .representation import IconText
from cockpitdecks import STRING_DATAREF_PREFIX

logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)
# logger.setLevel(logging.DEBUG)


class AircraftIcon(IconText):

    REPRESENTATION_NAME = "aircraft"

    def __init__(self, config: dict, button: "Button"):
        IconText.__init__(self, config=config, button=button)
        self.text_config = config.get(AircraftIcon.REPRESENTATION_NAME, {})
        self.string_datarefs = config.get("string-datarefs", [])

    def get_datarefs(self) -> list:
        return [STRING_DATAREF_PREFIX + d for d in self.string_datarefs]

    def get_image(self):
        new_text = self.button.get_dataref_value(self.string_datarefs[0], default="----")
        old_text = self.text_config.get("text")
        if new_text != old_text:
            self.text_config["text"] = new_text
            del self.button.deck.icons[self.icon]
            logger.debug(f"{'*'*40} {self.button.button_name()}: {self.string_datarefs[0]}={self.text}")
        return super().get_image()

    def describe(self) -> str:
        return "The representation display the current aircraft ICAO code."
