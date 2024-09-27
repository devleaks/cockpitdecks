# Cockpitdecks Custom Deck driver.
#
from __future__ import annotations

import logging
from typing import Dict

from cockpitdecks.deck import Deck

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


class CustomDeckManager:

    @staticmethod
    def enumerate(acpath: str | None = None) -> Dict[str, CustomDeck]:
        """Returns all the custom devices available to Cockpitdecks.
        """
        return {}


class CustomDeck(Deck):
    """
    Loads the configuration of a virtual deck
    """

    DECK_NAME = "customdeck"
    DRIVER_NAME = "customdriver"
    MIN_DRIVER_VERSION = "0.0.0"
    DEVICE_MANAGER = CustomDeckManager

    def __init__(self, name: str, config: dict, cockpit: "Cockpit", device=None):
        Deck.__init__(self, name=name, config=config, cockpit=cockpit, device=device)

        self.cockpit.set_logging_level(__name__)

        self.valid = True

        self.init()


    # #######################################
    #
    # Deck Specific Functions : Definition
    #
    def make_default_page(self, b: str | None = None):
        # Generates an image that is correctly sized to fit across all keys of a given
        #
        # The following two helper functions are stolen from streamdeck example scripts (tiled_image)
        pass

    # #######################################
    #
    # Deck Specific Functions : Activation
    #
    def key_change_callback(self, key, state: int, data: dict | None = None) -> None:
        """
        This is the function that is called when a key is pressed.
        For virtual decks, this function is quite complex
        since it has to take the "shape" of any "real physical deck" it virtualize
        Event codes:
         0 = Push/press RELEASE
         1 = Push/press PRESS
         2 = Turned clockwise
         3 = Turned counter-clockwise
         4 = Pulled
         9 = Slider, event data contains value
        10 = Touch start, event data contains value
        11 = Touch end, event data contains value
        12 = Swipe, event data contains value
        14 = Tap, event data contains value

        """
        logger.debug(f"Deck {self.name} Key {key} = {state} ({data})")
        return None

    # #######################################
    #
    # Deck Specific Functions : Representation
    #
    def render(self, button: "Button"):  # idx: int, image: str, label: str = None):
        logger.debug(f"Deck {self.name}: button {button.name}")
        pass

    # #######################################
    #
    # Deck Specific Functions : Operations
    #
    def start(self):
        pass

    def stop(self):
        pass

    @staticmethod
    def terminate_device(device, name: str = "unspecified"):
        logger.info(f"{name} terminated (reason {name})")
