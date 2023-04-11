# Base class for all decks
#
import os
import logging
import pickle
import inspect

from time import sleep
from enum import Enum
from abc import ABC, abstractmethod

from PIL import Image, ImageDraw, ImageFont, ImageOps
from ruamel.yaml import YAML

from .constant import CONFIG_FOLDER, CONFIG_FILE, RESOURCES_FOLDER
from .constant import ID_SEP, DEFAULT_LAYOUT, DEFAULT_PAGE_NAME
from .color import convert_color
from .page import Page
from .button import Button

logger = logging.getLogger("Deck")
# logger.setLevel(logging.DEBUG)

yaml = YAML()

# Attribute keybords
KW_BUTTONS = "buttons"
KW_INCLUDES = "includes"
KW_BACKPAGE = "back"


class Deck(ABC):
    """
    Loads the configuration of a Deck.
    A Deck has a collection of Pages, and knows which one is currently being displayed.
    """

    def __init__(self, name: str, config: dict, cockpit: "Cockpit", device = None):
        self.logging_level = "INFO"
        self._config = config
        self.name = name
        self.cockpit = cockpit
        self.device = device

        self.set_default(config, cockpit)

        self.layout_config = {}
        self.pages = {}
        self.home_page = None           # this is a Page, not a str.
        self.current_page = None        # this is a Page, not a str.
        self.previous_page = None       # this is a Page, not a str.
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
            logger.warning(f"__init__: deck has no layout, using default")

        self.valid = True

    # #######################################
    # Deck Common Functions
    #
    def init(self):
        if not self.valid:
            logger.warning(f"init: deck {self.name}: is invalid")
            return
        self.load()     # will load default page if no page found
        self.start()    # Some system may need to start before we can load a page

    def get_id(self):
        return ID_SEP.join([self.cockpit.get_id(), self.name, self.layout])

    def get_button_value(self, name):
        a = name.split(ID_SEP)
        if len(a) > 0:
            if a[0] == self.name:
                if a[1] in self.pages.keys():
                    return self.pages[a[1]].get_button_value(ID_SEP.join(a[1:]))
                else:
                    logger.warning(f"get_button_value: so such page {a[1]}")
            else:
                logger.warning(f"get_button_value: not my deck {a[0]} ({self.name})")
        return None

    def set_default(self, config: dict, base):
        """
        Loads a layout global configuration parameters.

        :param      fn:   The function
        :type       fn:   Function
        """
        # Logging level
        self.logging_level = config.get("logging-level", "INFO")
        llvalue = getattr(logging, self.logging_level)
        if llvalue is not None:
            logger.setLevel(llvalue)
            logger.debug(f"set_default: logging level set to {self.logging_level}")

        self.default_label_font = config.get("default-label-font", base.default_label_font)
        self.default_label_size = config.get("default-label-size", base.default_label_size)
        self.default_label_color = config.get("default-label-color", base.default_label_color)
        self.default_label_color = convert_color(self.default_label_color)
        self.default_label_position = config.get("default-label-position", base.default_label_position)
        self.default_icon_name = config.get("default-icon-color", self.name + base.default_icon_name)
        self.default_icon_color = config.get("default-icon-color", base.default_icon_color)
        self.default_icon_color = convert_color(self.default_icon_color)
        self.fill_empty_keys = config.get("fill-empty-keys", base.fill_empty_keys)
        self.empty_key_fill_color = config.get("empty-key-fill-color", base.empty_key_fill_color)
        self.empty_key_fill_color = convert_color(self.empty_key_fill_color)
        self.empty_key_fill_icon = config.get("empty-key-fill-icon", base.empty_key_fill_icon)
        self.annunciator_style = config.get("annunciator-style", base.annunciator_style)
        self.cockpit_color = config.get("cockpit-color", base.cockpit_color)
        self.cockpit_color = convert_color(self.cockpit_color)
        self.default_logo = config.get("default-wallpaper-logo", base.default_logo)
        self.default_wallpaper = config.get("default-wallpaper", base.default_wallpaper)
        self.default_home_page_name = config.get("default-homepage-name", base.default_home_page_name)

        if base == self:  # non default instances
            self.logo = config.get("wallpaper-logo", base.logo)
            self.wallpaper = config.get("wallpaper", base.wallpaper)
            self.home_page_name = config.get("homepage-name", base.home_page_name)
        else:
            self.logo = config.get("wallpaper-logo", base.default_logo)
            self.wallpaper = config.get("wallpaper", base.default_wallpaper)
            self.home_page_name = config.get("homepage-name", base.default_home_page_name)

    def load_layout_config(self, fn):
        """
        Loads a layout global configuration parameters.

        :param      fn:   The function
        :type       fn:   Function
        """
        if os.path.exists(fn):
            with open(fn, "r") as fp:
                self.layout_config = yaml.load(fp)
                logger.debug(f"load_layout_config: loaded layout config {fn}")
            if self.layout_config is not None and type(self.layout_config) == dict:
                self.set_default(self.layout_config, self)
        else:
            logger.debug(f"load_layout_config: no layout config file")

    def inspect(self, what: str = None):
        """
        This function is called on all pages of this Deck.
        """
        logger.info(f"*"*60)
        logger.info(f"Deck {self.name} -- {what}")
        for v in self.pages.values():
            v.inspect(what)

    def load(self):
        """
        Loads Streamdeck pages during configuration
        """
        if self.layout is None:
            self.make_default_page()
            return

        dn = os.path.join(self.cockpit.acpath, CONFIG_FOLDER, self.layout)
        if not os.path.exists(dn):
            logger.warning(f"load: deck has no layout folder '{self.layout}', loading default page")
            self.make_default_page()
            return

        pages = os.listdir(dn)
        if CONFIG_FILE in pages:  # first load config
            self.load_layout_config(os.path.join(dn, CONFIG_FILE))
        for p in pages:
            if p == CONFIG_FILE:
                continue
            elif p.endswith(".yaml") or p.endswith(".yml"):
                fn = os.path.join(dn, p)
                # if os.path.exists(fn):  # we know the file should exists...
                with open(fn, "r") as fp:
                    page_config = yaml.load(fp)

                    name = ".".join(p.split(".")[:-1])  # build default page name, remove extension ".yaml" or ".yml" from filename
                    if "name" in page_config:
                        name = page_config["name"]

                    if name in self.pages.keys():
                        logger.warning(f"load: page {name}: duplicate name, ignored")
                        continue

                    if not KW_BUTTONS in page_config:
                        logger.error(f"load: {name} has no button definition '{KW_BUTTONS}', ignoring")
                        continue

                    logger.debug(f"load: loading page {name} (from file {fn.replace(self.cockpit.acpath, '... ')})..")
                    this_page = Page(name, page_config, self)
                    this_page.load_defaults(page_config, self)
                    self.pages[name] = this_page

                    # Page buttons
                    this_page.load_buttons(page_config[KW_BUTTONS])

                    # Page includes
                    if KW_INCLUDES in page_config:
                        includes = page_config[KW_INCLUDES]
                        if type(page_config[KW_INCLUDES]) == str:  # just one file
                            includes = includes.split(",")
                        logger.debug(f"load: deck {self.name}: page {name} includes {includes}..")
                        ipb = 0
                        for inc in includes:
                            fni = os.path.join(dn, inc + ".yaml")
                            if os.path.exists(fni):
                                with open(fni, "r") as fpi:
                                    inc_config = yaml.load(fpi)
                                    # how to merge? for now, just merge buttons
                                    if KW_BUTTONS in inc_config:
                                        before = len(this_page.buttons)
                                        this_page.load_buttons(inc_config[KW_BUTTONS])
                                        ipb = len(this_page.buttons) - before
                            else:
                                logger.warning(f"load: includes: {inc}: file {fni} not found")
                        logger.info(f"load: deck {self.name}: page {name} includes {inc} (from file {fni.replace(self.cockpit.acpath, '... ')}), include contains {ipb} buttons")
                        logger.debug(f"load: includes: ..included")

                    logger.info(f"load: deck {self.name}: page {name} loaded (from file {fn.replace(self.cockpit.acpath, '... ')}), contains {len(this_page.buttons)} buttons")
                # else:
                #     logger.warning(f"load: file {p} not found")

            else:  # not a yaml file
                logger.debug(f"load: {dn}: ignoring file {p}")

        if not len(self.pages) > 0:
            self.valid = False
            logger.error(f"load: {self.name}: has no page, ignoring")
            # self.load_default_page()
        else:
            self.set_home_page()
            logger.info(f"load: deck {self.name}: loaded {len(self.pages)} pages from layout {self.layout}")

    def change_page(self, page: str = None):
        """
        Returns the currently loaded page name

        :param      page:  The page
        :type       page:  str
        """
        logger.debug(f"change_page: deck {self.name} change page to {page}..")
        if page is None:
            self.load_home_page()
            return
        if page == KW_BACKPAGE:
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
            logger.info(f"change_page: deck {self.name} changed page to {page}")
            return self.current_page.name
        else:
            logger.warning(f"change_page: deck {self.name}: page {page} not found")
            if self.current_page is not None:
                return self.current_page.name
        return None

    def reload_page(self):
        self.change_page(self.current_page.name)

    def set_home_page(self):
        if not len(self.pages) > 0:
            self.valid = False
            logger.error(f"set_home_page: deck {self.name} has no page, ignoring")
        else:
            if self.home_page_name in self.pages.keys():
                self.home_page = self.pages[self.home_page_name]
            else:
                logger.debug(f"set_home_page: deck {self.name}: no home page named {self.home_page_name}")
                self.home_page = self.pages[list(self.pages.keys())[0]]  # first page
            logger.debug(f"set_home_page: deck {self.name}: home page {self.home_page.name}")

    def load_home_page(self):
        """
        Connects to device and send initial keys.
        """
        if self.home_page is not None:
            self.change_page(self.home_page.name)
            logger.debug(f"load_home_page: deck {self.name}, home page {self.home_page.name} loaded")
        else:
            logger.debug(f"load_home_page: deck {self.name} has no home page")

    @abstractmethod
    def make_default_page(self, b: str = None):
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
    def print_page(self, page: Page):
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

    def terminate(self):
        for p in self.pages.values():
            p.terminate()
        self.pages = {}


class DeckWithIcons(Deck):
    """
    Loads the configuration of a Deck.
    A Deck has a collection of Pages, and knows which one is currently being displayed.
    """

    def __init__(self, name: str, config: dict, cockpit: "Cockpit", device = None):

        Deck.__init__(self, name=name, config=config, cockpit=cockpit, device=device)

        self.pil_helper = None
        self.icons = {}  # icons ready for this deck

    # #######################################
    # Deck Specific Functions
    #
    # #######################################
    # Deck Specific Functions : Installation
    #
    def init(self):
        if not self.valid:
            logger.warning(f"init: deck {self.name}: is invalid")
            return
        self.make_default_icon()
        self.load_icons()
        self.load()     # will load default page if no page found
        self.start()    # Some system may need to start before we can load a page

    def get_display_for_pil(self):
        """
        Return device or device element to use for PIL.
        """
        return None

    def make_default_icon(self):
        """
        Connects to device and send initial keys.
        """
        # Add default icon for this deck
        if self.device is not None:
            self.icons[self.default_icon_name] = self.pil_helper.create_image(deck=self.device, background=self.default_icon_color)
        else:
            self.icons[self.default_icon_name] = Image.new(mode="RGBA", size=(256, 256), color=self.default_icon_color)
        # copy it at highest level too
        # self.cockpit.icons[self.default_icon_name] = self.icons[self.default_icon_name]
        logger.debug(f"make_default_icon: create default {self.default_icon_name} icon ({self.icons.keys()})")

    def load_icons(self):
        """
        Each device model requires a different icon format (size).
        We could build a set per deck model rather than deck instance...
        """
        dn = self.cockpit.icon_folder
        if dn is not None:
            cache = os.path.join(dn, f"{self.name}_icon_cache.pickle")
            if os.path.exists(cache):
                with open(cache, "rb") as fp:
                    icons_temp = pickle.load(fp)
                    self.icons.update(icons_temp)
                logger.info(f"load_icons: deck {self.name}: {len(self.icons)} icons loaded from cache")
                return

        if self.device is not None:
            for k, v in self.cockpit.icons.items():
                self.icons[k] = self.pil_helper.create_scaled_image(self.device, v, margins=[0, 0, 0, 0])
            if dn is not None:
                cache = os.path.join(dn, f"{self.name}_icon_cache.pickle")
                with open(cache, "wb") as fp:
                    pickle.dump(self.icons, fp)
            logger.info(f"load_icons: deck {self.name}: {len(self.icons)} icons loaded")
        else:
            logger.warning(f"load_icons: deck {self.name} has no device")

    def create_icon_for_key(self, button, colors):
        return None

    def scale_icon_for_key(self, button, image):
        return None

    # #######################################
    # Deck Specific Functions : Rendering
    #
    def _send_key_image_to_device(self, key, image):
        pass
