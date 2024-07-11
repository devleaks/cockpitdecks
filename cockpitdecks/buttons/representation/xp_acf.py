"""X-Plane Aircraft Information Icon
"""
import os
import logging

from cockpitdecks import AIRCRAFT_CHANGE_MONITORING_DATAREF
from .icon import IconText

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


class Aircraft(IconText):
    """Class to display the aircraft.

    (Since the create of string-dataref, this is just a name changer for IconText.)
    """

    REPRESENTATION_NAME = "aircraft"

    PARAMETERS = {}

    def __init__(self, button: "Button"):
        IconText.__init__(self, button=button)
