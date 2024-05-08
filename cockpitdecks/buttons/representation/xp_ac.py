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
        # need to delete from cache to recreate a new image
        if self.icon is not None and self.icon in self.button.deck.icons:
            del self.button.deck.icons[self.icon]
        return super().get_image()

    def describe(self) -> str:
        return "The representation display the current aircraft ICAO code."
