# ###########################
# Representation that displays the content of sim/aircraft/view/acf_ICAO on an icon.
# These buttons are highly XP specific.
#
import logging

from .representation import IconText

logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)
logger.setLevel(logging.DEBUG)


class AircraftIconNew(IconText):

    REPRESENTATION_NAME = "aircraft-new"

    def __init__(self, config: dict, button: "Button"):
        IconText.__init__(self, config=config, button=button)
        self._aircraft_config = config.get(AircraftIconNew.REPRESENTATION_NAME, {})  # historical
        self.string_datarefs = config.get("string-datarefs", [])


    def get_datarefs(self) -> list:
        print("***", self.string_datarefs)
        return self.string_datarefs


    def get_image_for_icon(self):
        value = self.button.get_dataref_value(self.string_datarefs[0])
        print(">>>", self.button.button_name())
        print(">>>", self.string_datarefs[0], value)

    def describe(self):
        return "The representation display the current aircraft ICAO code."

