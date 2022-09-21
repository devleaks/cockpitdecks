# Base class for all decks
#
import os
import logging
import yaml
import threading
import pickle

from time import sleep

from enum import Enum

from PIL import Image, ImageDraw, ImageFont, ImageOps
from StreamDeck.ImageHelpers import PILHelper

from .constant import CONFIG_DIR, RESOURCES_FOLDER, INIT_PAGE, DEFAULT_LAYOUT
from .constant import convert_color
from .button import Button, STREAM_DECK_BUTTON_TYPES
from .page import Page

logger = logging.getLogger("Deck")

DEFAULT_PAGE_NAME = "X-Plane"


class Deck:
    """
    Loads the configuration of a Stream Deck.
    A Deck has a collection of Pages, and knows which one is currently being displayed.
    """

    def __init__(self, name: str, config: dict, cockpit: "Cockpit", device = None):
        self._config = config
        self.name = name
        self.cockpit = cockpit
        self.device = device
        self.home_page = None
        self.current_page = None
        self.previous_page = None
        self.page_history = []
        self.pil_helper = None

    def init(self):
        """
        Connects to device and send initial keys.
        """
        if self.home_page is not None:
            self.change_page(self.home_page.name)
        logger.info(f"init: deck {self.name} initialized")

    def load(self):
        """
        Loads Deck pages during configuration
        """
        pass

    def load_default_page(self):
        # Generates an image that is correctly sized to fit across all keys of a given
        #
        # The following two helper functions are stolen from streamdeck example scripts (tiled_image)
        pass

    def key_change_callback(self, deck, key, state):
        """
        This is the function that is called when a key is pressed.
        """
        logger.debug(f"key_change_callback: Deck {deck.id()} Key {key} = {state}")
        if self.cockpit.xp.use_flight_loop:  # if we use a flight loop, key_change_processing will be called from there
            self.cockpit.xp.events.put([self.name, key, state])
            logger.debug(f"key_change_callback: {key} {state} enqueued")
        else:
            # logger.debug(f"key_change_callback: {key} {state}")
            self.key_change_processing(deck, key, state)

    def key_change_processing(self, deck, key, state):
        """
        This is the function that is called when a key is pressed.
        """
        # logger.debug(f"key_change_processing: Deck {deck.id()} Key {key} = {state}")
        if self.current_page is not None and key in self.current_page.buttons.keys():
            self.current_page.buttons[key].activate(state)

    def create_icon_for_key(self, button, colors):
        if self.pil_helper is not None:
            return self.pil_helper.create_image(deck=self.device, background=colors)
        return None

    def make_icon_for_device(self):
        """
        Each device model requires a different icon format (size).
        We could build a set per Stream Deck model rather than stream deck instance...
        """
        pass

    def change_page(self, page: str):
        logger.debug(f"change_page: deck {self.name} change page to {page}..")
        if page == "back":
            if len(self.page_history) > 1:
                page = self.page_history.pop()  # this page
                page = self.page_history.pop()  # previous one
            else:
                page = self.home_page.name
            logger.debug(f"change_page: deck {self.name} change page to {page}..")
        if page in self.pages.keys():
            if self.current_page is not None:
                self.current_page.clean()
            self.previous_page = self.current_page
            self.current_page = self.pages[page]
            self.page_history.append(self.current_page.name)
            self.device.reset()
            self.cockpit.xp.set_datarefs(self.current_page.datarefs)  # set which datarefs to monitor
            self.current_page.render()
            logger.debug(f"change_page: deck {self.name} ..done")
        else:
            logger.warning(f"change_page: deck {self.name}: page {page} not found")


    def start(self):
        pass


    def set_key_image(self, button: Button): # idx: int, image: str, label: str = None):
        pass

    def terminate(self):
        pass
