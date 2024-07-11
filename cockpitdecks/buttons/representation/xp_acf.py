# ###########################
# Representation that displays FCU data.
# Horizontal: present the entire FCU.
# Vertical: present half FCU left or right.
# These buttons are *highly* X-Plane and Toliss Airbus specific.
#
import os
import logging

from cockpitdecks import AIRCRAFT_CHANGE_MONITORING_DATAREF
from cockpitdecks.simulator import Dataref
from .icon import IconText

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


class Aircraft(IconText):
    """Class to display the aircraft and AND trigger a new aircraft load when aircraft ICAO has changed.

    Should check more than aircraft ICAO:

    string-datarefs:
      - sim/aircraft/view/acf_ICAO
      - sim/aircraft/view/acf_tailnum

    """

    REPRESENTATION_NAME = "aircraft"

    PARAMETERS = {}

    def __init__(self, button: "Button"):
        IconText.__init__(self, button=button)
