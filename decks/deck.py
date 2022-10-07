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
# logger.setLevel(logging.DEBUG)

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

        self.default_label_font = config.get("default-label-font", cockpit.default_label_font)
        self.default_label_size = config.get("default-label-size", cockpit.default_label_size)
        self.default_label_color = config.get("default-label-color", cockpit.default_label_color)
        self.default_label_color = convert_color(self.default_label_color)
        self.default_icon_name = config.get("default-icon-color", name + cockpit.default_icon_name)
        self.default_icon_color = config.get("default-icon-color", cockpit.default_icon_color)
        self.default_icon_color = convert_color(self.default_icon_color)
        self.fill_empty = config.get("fill-empty-keys", cockpit.fill_empty)
        self.logo = config.get("default-wallpaper-logo", cockpit.default_logo)
        self.wallpaper = config.get("default-wallpaper", cockpit.default_wallpaper)

        self.pil_helper = None
        self.icons = {}  # icons ready for this deck

        self.pages = {}
        self.home_page = None
        self.current_page = None
        self.previous_page = None
        self.page_history = []

        self.valid = False
        self.running = False

        self.previous_key_values = {}
        self.current_key_values = {}

        if "serial" in config:
            self.serial = config["serial"]
        else:
            self.valid = False
            logger.error(f"__init__: {self.name}: has no serial number, cannot use")

        self.available_keys = None
        if device is not None and hasattr(device, "key_names"):
            self.available_keys = device.key_names()

        if device is not None and hasattr(device, "key_count"):
            self.numkeys = device.key_count()
            if self.available_keys is None:
                self.available_keys = list(range(self.numkeys))

        if self.available_keys is None:
            self.valid = False
            logger.error(f"__init__: {self.name}: cannot determine available keys")

        self.brightness = 100
        if "brightness" in config:
            self.brightness = int(config["brightness"])
            if self.device is not None:
                self.device.set_brightness(self.brightness)

        self.layout = None
        if "layout" in config:
            self.layout = config["layout"]  # config["layout"] may be None to choose no layout
        else:
            self.layout = DEFAULT_LAYOUT
            logger.warning(f"__init__: stream deck has no layout, using default")

        self.valid = True

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
        # logger.debug(f"key_change_callback: Deck {deck.id()} Key {key} = {state}")
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
        # logger.debug(f"key_change_processing: Deck {deck.id()} Keys: {self.current_page.buttons.keys()}")
        if self.current_page is not None and key in self.current_page.buttons.keys():
            self.current_page.buttons[key].activate(state)

    def create_icon_for_key(self, button, colors):
        if self.pil_helper is not None:
            return self.pil_helper.create_image(deck=self.device, background=colors)
        return None

    def make_default_icon(self):
        """
        Connects to device and send initial keys.
        """
        # Add default icon for this deck
        if self.device is not None:
            self.icons[self.default_icon_name] = PILHelper.create_image(deck=self.device, background=self.default_icon_color)
        else:
            self.icons[self.default_icon_name] = Image.new(mode="RGBA", size=(256, 256), color=self.default_icon_color)
        # copy it at highest level too
        # self.cockpit.icons[self.default_icon_name] = self.icons[self.default_icon_name]
        logger.debug(f"make_default_icon: create default {self.default_icon_name} icon ({self.icons.keys()})")

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
                self.cockpit.xp.remove_datarefs_to_monitor(self.current_page.datarefs)
                self.current_page.clean()
            self.previous_page = self.current_page
            self.current_page = self.pages[page]
            self.page_history.append(self.current_page.name)
            self.device.reset()
            self.cockpit.xp.add_datarefs_to_monitor(self.current_page.datarefs)  # set which datarefs to monitor
            self.current_page.render()
            logger.debug(f"change_page: deck {self.name} ..done")
        else:
            logger.warning(f"change_page: deck {self.name}: page {page} not found")


    def set_key_image(self, button: Button): # idx: int, image: str, label: str = None):
        pass

    def start(self):
        pass

    def terminate(self):
        pass
