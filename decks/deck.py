# Base class for all decks
#
import os
import logging
import yaml
import threading
import pickle
from time import sleep
from enum import Enum
from abc import ABC, abstractmethod

from PIL import Image, ImageDraw, ImageFont, ImageOps
from StreamDeck.ImageHelpers import PILHelper

from .constant import CONFIG_DIR, CONFIG_FILE, RESOURCES_FOLDER, DEFAULT_LAYOUT
from .constant import YAML_BUTTONS_KW, YAML_INCLUDE_KW
from .color import convert_color
from .page import Page
from .button import Button

logger = logging.getLogger("Deck")
# logger.setLevel(logging.DEBUG)


DEFAULT_PAGE_NAME = "X-Plane"


class Deck(ABC):
    """
    Loads the configuration of a Deck.
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
        self.fill_empty_keys = config.get("fill-empty-keys", cockpit.fill_empty_keys)
        self.empty_key_fill_color = config.get("empty-key-fill-color", cockpit.empty_key_fill_color)
        self.empty_key_fill_color = convert_color(self.empty_key_fill_color)
        self.empty_key_fill_icon = config.get("empty-key-fill-icon", cockpit.empty_key_fill_icon)
        self.annunciator_style = config.get("annunciator-style", cockpit.annunciator_style)
        self.cockpit_color = config.get("cockpit-color", cockpit.cockpit_color)
        self.logo = config.get("default-wallpaper-logo", cockpit.default_logo)
        self.wallpaper = config.get("default-wallpaper", cockpit.default_wallpaper)
        self.default_home_page_name = config.get("default-homepage-name", cockpit.default_home_page_name)

        self.pil_helper = None
        self.icons = {}  # icons ready for this deck

        self.layout_config = {}
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

    # #######################################
    # Deck Common Functions
    #
    def init(self):
        if self.valid:
            self.make_default_icon()
            self.make_icon_for_device()
            self.load()     # will load default page if no page found
            self.load_home_page()   # loads home page onto deck
            self.start()    # Some sustem may need to start before we load_home_page()

    def load_layout_config(self, fn):
        """
        Loads a layout global configuration parameters.

        :param      fn:   The function
        :type       fn:   Function
        """
        if os.path.exists(fn):
            with open(fn, "r") as fp:
                self.layout_config = yaml.safe_load(fp)
                logger.debug(f"load_layout_config: loaded layout config {fn}")
            if self.layout_config is not None and type(self.layout_config) == dict:
                self.default_home_page_name = self.layout_config.get("default-homepage-name")
                self.empty_key_fill_color = self.layout_config.get("empty-key-fill-color", self.cockpit.empty_key_fill_color)
                self.empty_key_fill_color = convert_color(self.empty_key_fill_color)
                self.empty_key_fill_icon = self.layout_config.get("empty-key-fill-icon", self.cockpit.empty_key_fill_icon)
        else:
            logger.debug(f"load_layout_config: no layout config file")

    def inspect(self):
        """
        This function is called on all pages of this Deck.
        """
        logger.info(f"Deck {self.name} -- Statistics")
        for v in self.pages.values():
            v.inspect()

    def load(self):
        """
        Loads Streamdeck pages during configuration
        """
        def load_buttons(page, buttons):
            for a in buttons:
                button = None

                # Where to place the button
                idx = Button.guess_index(a)
                if idx is None:
                    logger.error(f"load: page {page.name}: button has no index, ignoring {a}")
                    continue
                if str(idx) not in self.valid_indices():
                    logger.error(f"load: page {page.name}: button has invalid index '{idx}', ignoring {a}")
                    continue

                # How the button will behave, it is does something
                bty = Button.guess_activation_type(a)
                if bty is None or bty not in self.valid_activations(str(idx)):
                    logger.error(f"load: page {page.name}: button has invalid activation type {bty} for index {idx}, ignoring {a}")
                    continue

                # How the button will be represented, if it is
                bty = Button.guess_representation_type(a)
                if bty not in self.valid_representations(str(idx)):
                    logger.error(f"load: page {page.name}: button has invalid representation type {bty} for index {idx}, ignoring {a}")
                    continue

                button = Button(config=a, page=page)
                if button is not None:
                    page.add_button(idx, button)
                    logger.debug(f"load: ..page {page.name}: added button index {idx} {button.name}..")

        if self.layout is None:
            self.make_default_page()
            return

        dn = os.path.join(self.cockpit.acpath, CONFIG_DIR, self.layout)
        if not os.path.exists(dn):
            logger.warning(f"load: deck has no layout folder '{self.layout}', loading default page")
            self.make_default_page()
            return

        pages = os.listdir(dn)
        for p in pages:
            if p == CONFIG_FILE:
                self.load_layout_config(os.path.join(dn, p))
            elif p.endswith(".yaml") or p.endswith(".yml"):
                fn = os.path.join(dn, p)
                # if os.path.exists(fn):  # we know the file should exists...
                with open(fn, "r") as fp:
                    page_config = yaml.safe_load(fp)

                    name = ".".join(p.split(".")[:-1])  # build default page name, remove extension from filename
                    if "name" in page_config:
                        name = page_config["name"]

                    if name in self.pages.keys():
                        logger.warning(f"load: page {name}: duplicate name, ignored")
                        continue

                    if not YAML_BUTTONS_KW in page_config:
                        logger.error(f"load: {name} has no button definition '{YAML_BUTTONS_KW}', ignoring")
                        continue

                    logger.debug(f"load: loading page {name} (from file {fn.replace(self.cockpit.acpath, '... ')})..")
                    this_page = Page(name, page_config, self)
                    self.pages[name] = this_page

                    # Page buttons
                    load_buttons(this_page, page_config[YAML_BUTTONS_KW])

                    # Page includes
                    if YAML_INCLUDE_KW in page_config:
                        includes = page_config[YAML_INCLUDE_KW]
                        if type(page_config[YAML_INCLUDE_KW]) == str:  # just one file
                            includes = [includes]
                        logger.debug(f"load: includes: {includes} to page {name}..")
                        for inc in includes:
                            fni = os.path.join(dn, inc + ".yaml")
                            if os.path.exists(fni):
                                with open(fni, "r") as fpi:
                                    inc_config = yaml.safe_load(fpi)
                                    # how to merge? for now, just merge buttons
                                    if YAML_BUTTONS_KW in inc_config:
                                        load_buttons(this_page, inc_config[YAML_BUTTONS_KW])
                            else:
                                logger.warning(f"load: includes: {inc}: file {fni} not found")
                        logger.debug(f"load: includes: ..included")


                    logger.info(f"load: page {name} loaded (from file {fn.replace(self.cockpit.acpath, '... ')})")
                # else:
                #     logger.warning(f"load: file {p} not found")

            else:  # not a yaml file
                logger.debug(f"load: {dn}: ignoring file {p}")

        if not len(self.pages) > 0:
            self.valid = False
            logger.error(f"load: {self.name}: has no page, ignoring")
            # self.load_default_apge()
        else:
            self.set_home_page()

    def change_page(self, page: str):
        logger.debug(f"change_page: deck {self.name} change page to {page}..")
        if page == "back":
            if len(self.page_history) > 1:
                page = self.page_history.pop()  # this page
                page = self.page_history.pop()  # previous one
            else:
                page = self.home_page.name
            logger.debug(f"change_page: deck {self.name} back page to {page}..")
        if page in self.pages.keys():
            if self.current_page is not None:
                self.cockpit.xp.remove_datarefs_to_monitor(self.current_page.datarefs)
                self.current_page.clean()
            logger.debug(f"change_page: deck {self.name} ..installing new page..")
            self.previous_page = self.current_page
            self.current_page = self.pages[page]
            self.page_history.append(self.current_page.name)
            logger.debug(f"change_page: ..reset device {self.name}..")
            self.device.reset()
            self.cockpit.xp.add_datarefs_to_monitor(self.current_page.datarefs)  # set which datarefs to monitor
            self.current_page.render()
            logger.debug(f"change_page: deck {self.name} ..done")
            return self.current_page.name
        else:
            logger.warning(f"change_page: deck {self.name}: page {page} not found")
            if self.current_page is not None:
                return self.current_page.name
        return None

    def set_home_page(self):
        if not len(self.pages) > 0:
            self.valid = False
            logger.error(f"load: {self.name}: has no page, ignoring")
        else:
            if self.default_home_page_name in self.pages.keys():
                self.home_page = self.pages[self.default_home_page_name]
            else:
                self.home_page = self.pages[list(self.pages.keys())[0]]  # first page
            logger.info(f"load: deck {self.name} init page {self.home_page.name}")

    def load_home_page(self):
        """
        Connects to device and send initial keys.
        """
        if self.home_page is not None:
            self.change_page(self.home_page.name)
        logger.info(f"load_home_page: deck {self.name}, home page {self.home_page.name} loaded")

    # #######################################
    # Deck Specific Functions
    #
    # #######################################
    # Deck Specific Functions : Definition
    #
    @abstractmethod
    def make_default_page(self):
        """
        Connects to device and send initial keys.
        """
        pass

    @abstractmethod
    def valid_indices(self):
        return []

    @abstractmethod
    def valid_indices_with_image(self):
        return []

    def valid_activations(self, index = None):
        return ["none"] + ["page", "reload", "inspect", "stop"]

    def valid_representations(self, index = None):
        return ["none"]

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
        dn = self.cockpit.icon_folder
        if dn is not None:
            cache = os.path.join(dn, f"{self.name}_icon_cache.pickle")
            if os.path.exists(cache):
                with open(cache, "rb") as fp:
                    icons_temp = pickle.load(fp)
                    self.icons.update(icons_temp)
                logger.info(f"make_icon_for_device: {len(self.icons)} icons loaded from cache")
                return

        if self.device is not None:
            for k, v in self.cockpit.icons.items():
                self.icons[k] = self.pil_helper.create_scaled_image(self.device, v, margins=[0, 0, 0, 0])
            if dn is not None:
                cache = os.path.join(dn, f"{self.name}_icon_cache.pickle")
                with open(cache, "wb") as fp:
                    pickle.dump(self.icons, fp)
            logger.info(f"make_icon_for_device: deck {self.name} icons ready")
        else:
            logger.warning(f"make_icon_for_device: deck {self.name} has no device")

    def create_icon_for_key(self, button, colors):
        if self.pil_helper is not None:
            return self.pil_helper.create_image(deck=self.device, background=colors)
        return None

    # #######################################
    # Deck Specific Functions : Activation
    #
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

    # #######################################
    # Deck Specific Functions : Representation
    #
    def _send_key_image_to_device(self, key, image):
        pass

    @abstractmethod
    def render(self, button: Button):
        pass

    # #######################################
    # Deck Specific Functions : Device
    #
    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def terminate(self):
        pass

