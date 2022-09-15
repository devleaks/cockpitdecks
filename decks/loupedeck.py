import os
import logging
import yaml
import threading

from time import sleep

from enum import Enum

from .Loupedeck.ImageHelpers import PILHelper

from .constant import CONFIG_DIR, RESOURCES_FOLDER, INIT_PAGE, DEFAULT_LAYOUT
from .constant import convert_color
from .button import Button, BUTTON_TYPES
from .page import Page

from .streamdeck import Streamdeck
from .Loupedeck.Devices.constants import BUTTONS as LOUPEDECK_BUTTON_NAMES

logger = logging.getLogger("Loupedeck")

DEFAULT_PAGE_NAME = "X-Plane"
POLL_FREQ = 5  # default is 20


class Loupedeck(Streamdeck):
    """
    Loads the configuration of a Loupedeck.
    A Loupedeck has a collection of Pages, and knows which one is currently being displayed.
    """

    def __init__(self, name: str, config: dict, decks: "Decks", device = None):
        Streamdeck.__init__(self, name=name, config=config, decks=decks, device=None)

        self.name = name
        self.decks = decks
        self.device = device  # no longer None after Streamdeck.__init__()
        self.pages = {}
        self.icons = {}  # icons ready for this deck
        self.home_page = None       # if None means deck has loaded default wallpaper only.
        self.current_page = None
        self.previous_page = None
        self.page_history = []
        self.valid = True
        self.running = False
        self.monitoring_thread = None

        self.previous_key_values = {}
        self.current_key_values = {}

        self.default_label_font = config.get("default-label-font", decks.default_label_font)
        self.default_label_size = config.get("default-label-size", decks.default_label_size)
        self.default_label_color = config.get("default-label-color", decks.default_label_color)
        self.default_label_color = convert_color(self.default_label_color)
        self.default_icon_name = config.get("default-icon-color", name + decks.default_icon_name)
        self.default_icon_color = config.get("default-icon-color", decks.default_icon_color)
        self.default_icon_color = convert_color(self.default_icon_color)
        self.fill_empty = config.get("fill-empty-keys", decks.fill_empty)
        self.logo = config.get("default-wallpaper-logo", decks.default_logo)
        self.wallpaper = config.get("default-wallpaper", decks.default_wallpaper)

        if "serial" in config:
            self.serial = config["serial"]
        else:
            self.valid = False
            logger.error(f"__init__: loupedeck has no serial number, cannot use")

        self.valid = True

        if self.valid:
            self.make_icon_for_device()
            self.load()
            self.init()
            self.start()

    def load(self):
        """
        Loads Streamdeck pages during configuration
        """
        BUTTONS = "buttons"  # keywork in yaml file
        if self.layout is None:
            self.load_default_page()
            return

        dn = os.path.join(self.decks.acpath, CONFIG_DIR, self.layout)
        if not os.path.exists(dn):
            logger.warning(f"load: loupedeck has no layout folder '{self.layout}', loading default page")
            self.load_default_page()
            return

        pages = os.listdir(dn)
        for p in pages:
            if p.endswith("yaml") or p.endswith("yml"):
                name = ".".join(p.split(".")[:-1])  # remove extension from filename
                fn = os.path.join(dn, p)

                if os.path.exists(fn):
                    with open(fn, "r") as fp:
                        pc = yaml.safe_load(fp)

                        if not BUTTONS in pc:
                            logger.error(f"load: {fn} has no action")
                            continue

                        if "name" in pc:
                            name = pc["name"]

                        this_page = Page(name, self)

                        this_page.fill_empty = pc["fill-empty-keys"] if "fill-empty-keys" in pc else self.fill_empty
                        self.pages[name] = this_page

                        for a in pc[BUTTONS]:
                            button = None
                            bty = None
                            idx = None
                            if "index" in a:
                                idx = a["index"]  # DO NOT cast to int()
                            else:
                                logger.error(f"load: page {name}: button {a} has no index, ignoring")
                                continue

                            if idx not in LOUPEDECK_BUTTON_NAMES.values():
                                logger.error(f"load: page {name}: button {a} has index invalid for LoupedeckLive Device (keys={LOUPEDECK_BUTTON_NAMES.values()}), ignoring")
                                continue

                            if "type" in a:
                                bty = a["type"]

                            if bty in BUTTON_TYPES.keys():
                                button = BUTTON_TYPES[bty].new(config=a, page=this_page)
                                this_page.add_button(idx, button)
                            else:
                                logger.error(f"load: page {name}: button {a} invalid button type {bty}, ignoring")

                        logger.info(f"load: page {name} added (from file {fn.replace(self.decks.acpath, '... ')})")
                else:
                    logger.warning(f"load: file {p} not found")

            else:  # not a yaml file
                logger.debug(f"load: {dn}: ignoring file {p}")

        if not len(self.pages) > 0:
            self.valid = False
            logger.error(f"load: {self.name}: has no page, ignoring")
        else:
            if INIT_PAGE in self.pages.keys():
                self.home_page = self.pages[INIT_PAGE]
            else:
                self.home_page = self.pages[list(self.pages.keys())[0]]  # first page
            logger.info(f"load: loupedeck {self.name} init page {self.home_page.name}")

    def load_default_page(self):
        # Generates an image that is correctly sized to fit across all keys of a given
        #
        # The following two helper functions are stolen from streamdeck example scripts (tiled_image)
        pass

    def key_change_callback(self, deck, msg):
        """
        This is the function that is called when a key is pressed.
        """
        logger.debug(f"key_change_callback: {msg}")
        return
        # logger.debug(f"key_change_callback: Deck {deck.id()} Key {key} = {state}")
        if self.decks.xp.use_flight_loop:  # if we use a flight loop, key_change_processing will be called from there
            self.decks.xp.events.put([self.name, key, state])
            logger.debug(f"key_change_callback: {key} {state} enqueued")
        else:
            # logger.debug(f"key_change_callback: {key} {state}")
            self.key_change_processing(deck, key, state)

    def key_change_processing(self, deck, key, state):
        """
        This is the function that is called when a key is pressed.
        """
        # logger.debug(f"key_change_processing: Deck {deck.id()} Key {key} = {state}")
        if key in self.current_page.buttons.keys():
            self.current_page.buttons[key].activate(state)

    def make_icon_for_device(self):
        """
        Each device model requires a different icon format (size).
        We could build a set per Stream Deck model rather than loupedeck instance...
        """
        pass

    def change_page(self, page: str):
        logger.debug(f"change_page: deck {self.name} change page to {page}..")

    def start(self):
        if self.device is not None:
            self.device.set_callback(self.key_change_callback)
        logger.info(f"start: loupedeck {self.name} listening for key strokes")


        logger.info(f"start: loupedeck {self.name} listening for key strokes")


    def set_key_image(self, button: Button): # idx: int, image: str, label: str = None):
        pass

    def terminate(self):
        logger.info(f"terminate: deck {self.name} terminated")
