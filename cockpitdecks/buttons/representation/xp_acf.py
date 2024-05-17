# ###########################
# Representation that displays FCU data.
# Horizontal: present the entire FCU.
# Vertical: present half FCU left or right.
# These buttons are *highly* X-Plane and Toliss Airbus specific.
#
import os
import logging

from cockpitdecks import ICON_SIZE
from .icon import IconText

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

AIRCRAFT_DATAREF = "sim/aircraft/view/acf_ICAO"


class Aircraft(IconText):
    """Class to display the aircraft and AND trigger a new aircraft load when aircraft ICAO has changed.

    Should check more than aircraft ICAO:

    string-datarefs:
      - sim/aircraft/view/acf_ICAO
      - sim/aircraft/view/acf_tailnum
      - sim/aircraft/view/acf_relative_path

    """

    REPRESENTATION_NAME = "aircraft"

    def __init__(self, config: dict, button: "Button"):
        IconText.__init__(self, config=config, button=button)
        self.aircraft = config.get("aircraft")
        self._current_aircraft = None

    def aircraft_changed(self) -> bool:
        curr = self.button.get_dataref_value(AIRCRAFT_DATAREF)
        return False if curr is None else self._current_aircraft != curr

    def change_aircraft(self):
        curr = self.button.get_dataref_value(AIRCRAFT_DATAREF)
        if curr is None:
            logger.warning(f"no aircraft in {AIRCRAFT_DATAREF}")
            return
        if self._current_aircraft is None:  # first aircraft, no need to change
            self._current_aircraft = curr
            logger.info(f"loaded aircraft {curr}")
            return
        self._current_aircraft = curr
        logger.info(f"loading new aircraft {curr}")
        #
        #
        # sleep(60)  # need time to load aircraft before we can fetch its path
        #            # otherwise, we get the path to the previous aircraft!
        #
        #
        path = self.button.get_dataref_value("sim/aircraft/view/acf_relative_path")
        if path is not None:
            acpath = os.path.dirname(path)
            self.button.deck.cockpit.load_aircraft(acpath)
        else:
            logger.warning(f"no aircraft path")

    def get_image(self):
        if self.aircraft_changed():
            self.change_aircraft()
        return super().get_image()
