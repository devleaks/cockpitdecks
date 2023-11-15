# ###########################
# Representation that displays the content of sim/aircraft/view/acf_ICAO on an icon.
# These buttons are highly XP specific.
#
import logging

from .xp_str import StringIcon

logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)
# logger.setLevel(logging.DEBUG)


class AircraftIcon(StringIcon):
    def __init__(self, config: dict, button: "Button"):
        StringIcon.__init__(self, config=config, button=button)
        self._strconfig = config.get("aircraft")  # historical
