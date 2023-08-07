# Base class for all decks
#
import os
import logging
import pickle
import inspect

from time import sleep
from enum import Enum
from abc import ABC, abstractmethod
from functools import reduce

from PIL import Image, ImageDraw, ImageOps

from cockpitdecks import CONFIG_FOLDER, CONFIG_FILE, RESOURCES_FOLDER, ICONS_FOLDER
from cockpitdecks import ID_SEP, KW, ANNUNCIATOR_STYLES, DEFAULT_LAYOUT, DEFAULT_PAGE_NAME, COCKPIT_COLOR
from cockpitdecks import Config

from cockpitdecks.resources.color import convert_color
from .page import Page
from .button import Button
from cockpitdecks.buttons.activation import DECK_ACTIVATIONS, DEFAULT_ACTIVATIONS
from cockpitdecks.buttons.representation import DECK_REPRESENTATIONS, DEFAULT_REPRESENTATIONS

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

DECKS_FOLDER = "decks"

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
        self.model = config.get(KW.MODEL.value)
        self._buttons = {}
        self._activations = set()
        self._representations = set()

        self.cockpit.set_logging_level(__name__)

        self.set_defaults(config, cockpit)

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
            logger.error(f"{self.name}: has no serial number, cannot use")

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
            logger.warning(f"deck has no layout, using default")

        # Local non default values are initialized from defaults
        # May be overwritten by configuration parameters.
        self.logo = config.get("logo", cockpit.default_logo)
        self.wallpaper = config.get("wallpaper", cockpit.default_wallpaper)
        self.home_page_name = config.get("homepage-name", cockpit.default_home_page_name)

        self.valid = True

    # #######################################
    # Deck Common Functions
    #
    def init(self):
        if not self.valid:
            logger.warning(f"deck {self.name}: is invalid")
            return
        self.read_definition()
        self.load()     # will load default page if no page found
        self.start()    # Some system may need to start before we can load a page

    def get_id(self):
        return ID_SEP.join([self.cockpit.get_id(), self.name, self.layout])

    def read_definition(self):
        dt = self.model if self.model is not None else type(self).__name__
        fn = os.path.join(os.path.dirname(__file__), RESOURCES_FOLDER, DECKS_FOLDER, dt + ".yaml")
        logger.debug(f"{type(self).__name__}, {self.model}: {fn}")
        if not os.path.exists(fn):
            logger.error(f"no deck definition {fn} for {type(self).__name__}")
            return

        self.deck_content = Config(fn)

        if not self.deck_content.is_valid():
            logger.error(f"no deck definition for {dt}")
            return

        cnt = 0
        for button in self.deck_content[KW.BUTTONS.value]:
            name = button.get(KW.NAME.value)
            repeat = button.get(KW.REPEAT.value)
            prefix = button.get(KW.PREFIX.value, "")

            action = button.get(KW.ACTION.value)
            activation = [KW.NONE.value]
            if action is None or action.lower() == KW.NONE.value:
                action = KW.NONE.value
            else:
                activation = DECK_ACTIVATIONS.get(action)
                if activation is None:
                    logger.warning(f"deck {self.name}: action {button.get(KW.ACTION.value)} not found in DECK_ACTIVATIONS")

            view = button.get(KW.VIEW.value)
            r = [KW.NONE.value]
            if view is None or view.lower() == KW.NONE.value:
                view = KW.NONE.value
            else:
                representation = DECK_REPRESENTATIONS.get(view)
                if representation is None:
                    logger.warning(f"deck {self.name}: view {button.get(KW.VIEW.value)} not found in DECK_REPRESENTATIONS")

            if activation is not None and representation is not None:
                if repeat is None:
                    if name is None:
                        name = "NO_NAME_" + str(cnt)
                        cnt = cnt + 1
                        logger.warning(f"deck {self.name}: button has no name, using default {name}")

                    self._buttons[prefix + name] = {
                        KW.INDEX.value: prefix + name,
                        KW.INDEX_NUMERIC.value: 0,
                        KW.ACTION.value: button.get(KW.ACTION.value),
                        KW.VIEW.value: button.get(KW.VIEW.value),
                        KW.ACTIVATIONS.value: activation,
                        KW.REPRESENTATIONS.value: representation
                    }
                    if KW.IMAGE.value in button:
                        self._buttons[prefix + str(i)][KW.IMAGE.value] = button.get(KW.IMAGE.value)
                else:  # name is ignored
                    for i in range(repeat):
                        idx = str(i) if prefix is None else prefix + str(i)
                        self._buttons[idx] = {
                            KW.INDEX.value: idx,
                            KW.INDEX_NUMERIC.value: i,
                            KW.ACTION.value: button.get(KW.ACTION.value),
                            KW.VIEW.value: button.get(KW.VIEW.value),
                            KW.ACTIVATIONS.value: activation,
                            KW.REPRESENTATIONS.value: representation
                        }
                        if KW.IMAGE.value in button:
                            self._buttons[idx][KW.IMAGE.value] = button.get(KW.IMAGE.value)
                        # else: don't set it, a sign that there is no image
            else:
                logger.warning(f"deck {self.name}: cannot proceed with {button} definition")
        logger.debug(f"deck {self.name}: buttons: {self._buttons.keys()}..")
        # with open(f"{dt}.out", "w") as fp:
        #     yaml.dump(self._buttons, fp)
        self.valid_activations()        # will print debug
        self.valid_representations()    # will print debug
        logger.debug(f"..deck {self.name} done")

    def get_button_value(self, name):
        a = name.split(ID_SEP)
        if len(a) > 0:
            if a[0] == self.name:
                if a[1] in self.pages.keys():
                    return self.pages[a[1]].get_button_value(ID_SEP.join(a[1:]))
                else:
                    logger.warning(f"so such page {a[1]}")
            else:
                logger.warning(f"not my deck {a[0]} ({self.name})")
        return None

    def set_defaults(self, config: dict, base):
        """
        Loads a layout global configuration parameters.

        :param      fn:   The function
        :type       fn:   Function
        """
        self.default_label_font = config.get("default-label-font", base.default_label_font)
        self.default_label_size = config.get("default-label-size", base.default_label_size)
        self.default_label_color = config.get("default-label-color", base.default_label_color)
        self.default_label_color = convert_color(self.default_label_color)
        self.default_label_position = config.get("default-label-position", base.default_label_position)
        self.default_icon_name = config.get("default-icon-color", self.name + base.default_icon_name)
        self.default_icon_texture = config.get("default-icon-texture", base.default_icon_texture)
        self.default_icon_color = config.get("default-icon-color", base.default_icon_color)
        self.default_icon_color = convert_color(self.default_icon_color)
        self.default_annun_texture = config.get("default-annunciator-texture", base.default_annun_texture)
        self.default_annun_color = config.get("default-annunciator-color", base.default_annun_color)
        self.default_annun_color = convert_color(self.default_annun_color)
        self.annunciator_style = config.get("annunciator-style", base.annunciator_style)
        self.annunciator_style = ANNUNCIATOR_STYLES(self.annunciator_style)
        self.fill_empty_keys = config.get("fill-empty-keys", base.fill_empty_keys)
        self.cockpit_color = config.get("cockpit-color", base.cockpit_color)
        self.cockpit_color = convert_color(self.cockpit_color)
        self.cockpit_texture = config.get("cockpit-texture", base.cockpit_texture)
        self.default_logo = config.get("default-logo", base.default_logo)
        self.default_wallpaper = config.get("default-wallpaper", base.default_wallpaper)
        self.default_home_page_name = config.get("default-homepage-name", base.default_home_page_name)

        if base == self:  # non default instances
            self.logo = config.get("logo", base.logo)
            self.wallpaper = config.get("wallpaper", base.wallpaper)
            self.home_page_name = config.get("homepage-name", base.home_page_name)
        else:
            self.logo = config.get("logo", base.default_logo)
            self.wallpaper = config.get("wallpaper", base.default_wallpaper)
            self.home_page_name = config.get("homepage-name", base.default_home_page_name)

    def load_layout_config(self, fn):
        """
        Loads a layout global configuration parameters.

        :param      fn:   The function
        :type       fn:   Function
        """
        self.layout_config = Config(fn)
        if self.layout_config.is_valid():
            self.set_defaults(self.layout_config, self)
        else:
            logger.debug(f"no layout config file")

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
            logger.warning(f"deck has no layout folder '{self.layout}', loading default page")
            self.make_default_page()
            return

        pages = os.listdir(dn)
        if CONFIG_FILE in pages:  # first load config
            self.load_layout_config(os.path.join(dn, CONFIG_FILE))
        for p in pages:
            if p == CONFIG_FILE:
                continue
            elif p.endswith(".yaml") or p.endswith(".yml"):  # does not work if case sensitive, no YAML or Yaml or YML...
                fn = os.path.join(dn, p)
                # if os.path.exists(fn):  # we know the file should exists...
                page_config = Config(fn)
                if page_config.is_valid():
                    name = ".".join(p.split(".")[:-1])  # build default page name, remove extension ".yaml" or ".yml" from filename
                    if "name" in page_config:
                        name = page_config["name"]

                    if name in self.pages.keys():
                        logger.warning(f"page {name}: duplicate name, ignored")
                        continue

                    if not KW.BUTTONS.value in page_config:
                        logger.error(f"{name} has no button definition '{KW.BUTTONS.value}', ignoring")
                        continue

                    logger.debug(f"loading page {name} (from file {fn.replace(self.cockpit.acpath, '... ')})..")
                    this_page = Page(name, page_config, self)
                    this_page.load_defaults(page_config, self)
                    self.pages[name] = this_page

                    # Page buttons
                    this_page.load_buttons(page_config[KW.BUTTONS.value])

                    # Page includes
                    if KW.INCLUDES.value in page_config:
                        includes = page_config[KW.INCLUDES.value]
                        if type(page_config[KW.INCLUDES.value]) == str:  # just one file
                            includes = includes.split(",")
                        logger.debug(f"deck {self.name}: page {name} includes {includes}..")
                        ipb = 0
                        for inc in includes:
                            fni = os.path.join(dn, inc + ".yaml")
                            inc_config = Config(fni)
                            if inc_config.is_valid():
                                if KW.BUTTONS.value in inc_config:
                                    before = len(this_page.buttons)
                                    this_page.load_buttons(inc_config[KW.BUTTONS.value])
                                    ipb = len(this_page.buttons) - before
                            else:
                                logger.warning(f"includes: {inc}: file {fni} not found")
                        logger.info(f"deck {self.name}: page {name} includes {inc} (from file {fni.replace(self.cockpit.acpath, '... ')}), include contains {ipb} buttons")
                        logger.debug(f"includes: ..included")

                    logger.info(f"deck {self.name}: page {name} loaded (from file {fn.replace(self.cockpit.acpath, '... ')}), contains {len(this_page.buttons)} buttons")
                # else:
                #     logger.warning(f"file {p} not found")

            else:  # not a yaml file
                logger.debug(f"{dn}: ignoring file {p}")

        if not len(self.pages) > 0:
            self.valid = False
            logger.error(f"{self.name}: has no page, ignoring")
            # self.load_default_page()
        else:
            self.set_home_page()
            logger.info(f"deck {self.name}: loaded {len(self.pages)} pages from layout {self.layout}")

    def change_page(self, page: str = None):
        """
        Returns the currently loaded page name

        :param      page:  The page
        :type       page:  str
        """
        logger.debug(f"deck {self.name} change page to {page}..")
        if page is None:
            self.load_home_page()
            return
        if page == KW.BACKPAGE.value:
            if len(self.page_history) > 1:
                page = self.page_history.pop()  # this page
                page = self.page_history.pop()  # previous one
            else:
                page = self.home_page.name
            logger.debug(f"deck {self.name} back page to {page}..")
        if page in self.pages.keys():
            if self.current_page is not None:
                self.cockpit.sim.remove_datarefs_to_monitor(self.current_page.datarefs)
                self.current_page.clean()
            logger.debug(f"deck {self.name} ..installing new page..")
            self.previous_page = self.current_page
            self.current_page = self.pages[page]
            self.page_history.append(self.current_page.name)
            logger.debug(f"..reset device {self.name}..")
            self.device.reset()
            self.cockpit.sim.add_datarefs_to_monitor(self.current_page.datarefs)  # set which datarefs to monitor
            self.current_page.render()
            logger.debug(f"deck {self.name} ..done")
            logger.info(f"deck {self.name} changed page to {page}")
            return self.current_page.name
        else:
            logger.warning(f"deck {self.name}: page {page} not found")
            if self.current_page is not None:
                return self.current_page.name
        return None

    def reload_page(self):
        self.change_page(self.current_page.name)

    def set_home_page(self):
        if not len(self.pages) > 0:
            self.valid = False
            logger.error(f"deck {self.name} has no page, ignoring")
        else:
            if self.home_page_name in self.pages.keys():
                self.home_page = self.pages[self.home_page_name]
            else:
                logger.debug(f"deck {self.name}: no home page named {self.home_page_name}")
                self.home_page = self.pages[list(self.pages.keys())[0]]  # first page
            logger.debug(f"deck {self.name}: home page {self.home_page.name}")

    def load_home_page(self):
        """
        Connects to device and send initial keys.
        """
        if self.home_page is not None:
            self.change_page(self.home_page.name)
            logger.debug(f"deck {self.name}, home page {self.home_page.name} loaded")
        else:
            logger.debug(f"deck {self.name} has no home page")

    @abstractmethod
    def make_default_page(self, b: str = None):
        """
        Connects to device and send initial keys.
        """
        pass

    # #######################################
    # Deck Specific Functions : Activation
    #
    def get_index_prefix(self, index):
        b = self._buttons.get(index)
        if b is not None:
            return b.get(KW.PREFIX.value)
        logger.warning(f"deck {self.name}: no button index {index}")
        return None

    def get_index_numeric(self, index):
        # Useful to just get the int value of index
        b = self._buttons.get(index)
        if b is not None:
            return b.get(KW.INDEX.value_NUMRIC)
        logger.warning(f"deck {self.name}: no button index {index}")
        return None

    def valid_indices(self):
        return list(self._buttons.keys())

    def valid_activations(self, index = None):
        if index is not None:
            b = self._buttons.get(index)
            if b is not None:
                logger.debug(f"deck {self.name}: button {index}: {DEFAULT_ACTIVATIONS + b[KW.ACTIVATIONS.value]}")
                return DEFAULT_ACTIVATIONS + b[KW.ACTIVATIONS.value]
            else:
                logger.warning(f"deck {self.name}: no button index {index}, returning default for deck")
        all_activations = set(DEFAULT_ACTIVATIONS).union(set(reduce(lambda l, b: l.union(set(b.get(KW.ACTIVATIONS.value, set()))), self._buttons.values(), set())))
        logger.debug(f"deck {self.name}: {all_activations}")
        return list(all_activations)

    def valid_representations(self, index = None):
        if index is not None:
            b = self._buttons.get(index)
            if b is not None:
                logger.debug(f"deck {self.name}: button {index}: {DEFAULT_REPRESENTATIONS + b[KW.ACTIVATIONS.value]}")
                return DEFAULT_REPRESENTATIONS + b[KW.REPRESENTATIONS.value]
            else:
                logger.warning(f"deck {self.name}: no button index {index}, returning default for deck")
        all_representations = set(DEFAULT_REPRESENTATIONS).union(set(reduce(lambda l, b: l.union(set(b.get(KW.REPRESENTATIONS.value, set()))), self._buttons.values(), set())))
        logger.debug(f"deck {self.name}: {all_representations}")
        return list(all_representations)

    # #######################################
    # Deck Specific Functions : Activation
    #
    def key_change_callback(self, deck, key, state):
        """
        This is the function that is called when a key is pressed.
        """
        # logger.debug(f"Deck {deck.id()} Key {key} = {state}")
        if self.cockpit.sim.use_flight_loop:  # if we use a flight loop, key_change_processing will be called from there
            self.cockpit.sim.events.put([self.name, key, state])
            logger.debug(f"{key} {state} enqueued")
        else:
            # logger.debug(f"{key} {state}")
            self.key_change_processing(deck, key, state)

    def key_change_processing(self, deck, key, state):
        """
        This is the function that is called when a key is pressed.
        """
        # logger.debug(f"Deck {deck.id()} Key {key} = {state}")
        # logger.debug(f"Deck {deck.id()} Keys: {self.current_page.buttons.keys()}")
        if self.current_page is not None:
            idx = str(key)
            if idx in self.current_page.buttons.keys():
                self.current_page.buttons[idx].activate(state)
            else:
                logger.debug(f"{idx} not found on page {self.current_page.name}")
        else:
            logger.warning(f"no current page")

    # #######################################
    # Deck Specific Functions : Representation
    #
    def print_page(self, page: Page):
        pass

    def fill_empty(self, key):
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
            logger.warning(f"deck {self.name}: is invalid")
            return
        self.read_definition()
        self.load_icons()
        self.load()     # will load default page if no page found
        self.start()    # Some system may need to start before we can load a page

    def get_display_for_pil(self, b: str = None):
        """
        Return device or device element to use for PIL.
        """
        return self.device

    def get_index_image_size(self, index):
        b = self._buttons.get(index)
        if b is not None:
            return b.get(KW.IMAGE.value)
        logger.warning(f"deck {self.name}: no button index {index}")
        return None

    def load_icons(self):
        """
        Each device model requires a different icon format (size).
        We could build a set per deck model rather than deck instance...
        """
        logger.info(f"deck {self.name}: use cache {self.cockpit.cache_icon}")
        dn = self.cockpit.icon_folder
        if dn is not None:
            cache = os.path.join(dn, f"{self.name}_icon_cache.pickle")
            if os.path.exists(cache) and self.cockpit.cache_icon:
                with open(cache, "rb") as fp:
                    icons_temp = pickle.load(fp)
                    self.icons.update(icons_temp)
                logger.info(f"deck {self.name}: {len(self.icons)} icons loaded from cache")
                return

        if self.device is not None:
            for k, v in self.cockpit.icons.items():
                self.icons[k] = self.pil_helper.create_scaled_image(self.device, v, margins=[0, 0, 0, 0])
            if dn is not None:
                cache = os.path.join(dn, f"{self.name}_icon_cache.pickle")
                if self.cockpit.cache_icon:
                    with open(cache, "wb") as fp:
                        pickle.dump(self.icons, fp)
                    logger.info(f"deck {self.name}: {len(self.icons)} icons cached")
                else:
                    logger.info(f"deck {self.name}: {len(self.icons)} icons loaded")
        else:
            logger.warning(f"deck {self.name} has no device")

    def get_icon_background(self, name: str, width: int, height: int, texture_in, color_in, use_texture = True, who: str = "Cockpit"):
        """
        Returns a **Pillow Image** of size width x height with either the file specified by texture or a uniform color
        """
        def get_texture():
            tarr = []
            if texture_in is not None:
                tarr.append(texture_in)
            if self.default_icon_texture is not None:
                tarr.append(self.default_icon_texture)
            if self.cockpit_texture is not None:
                tarr.append(self.cockpit_texture)

            dirs = []
            dirs.append(os.path.join(os.path.dirname(__file__), RESOURCES_FOLDER))
            dirs.append(os.path.join(os.path.dirname(__file__), RESOURCES_FOLDER, ICONS_FOLDER))
            if self.cockpit.acpath is not None:  # add to search path
                dirs.append(os.path.join(self.cockpit.acpath, CONFIG_FOLDER, RESOURCES_FOLDER))
                dirs.append(os.path.join(self.cockpit.acpath, CONFIG_FOLDER, ICONS_FOLDER))

            for dn in dirs:
                for texture in tarr:
                    fn = os.path.join(dn, texture)
                    if os.path.exists(fn):
                        return fn
            return None

        def get_color():
            for t in [color_in, self.default_icon_color, self.cockpit_color]:
                if t is not None:
                    return t
            return COCKPIT_COLOR

        image = None

        texture = get_texture()
        if use_texture and texture is not None:
            if texture in self.cockpit.icons.keys():
                image = self.cockpit.icons[texture]
            else:
                image = Image.open(texture)
                self.cockpit.icons[texture] = image
            logger.debug(f"{who}: texture {texture_in} in {texture}")

        if image is not None:  # found a texture as requested
            image = image.resize((width, height))
            return image

        if use_texture and texture is None:
            logger.debug(f"{who}: should use texture but no texture found, using uniform color")

        color = get_color()
        image = Image.new(mode="RGBA", size=(width, height), color=color)
        logger.debug(f"{who}: uniform color {color} (color_in={color_in})")
        return image

    def create_icon_for_key(self, index, colors, texture, name: str = None):
        # Abstact
        return None

    def scale_icon_for_key(self, index, image, name: str = None):
        # Abstact
        return None

    def get_image_size(self, index):
        # Abstact
        return (0, 0)

    def fill_empty(self, key):
        icon = self.create_icon_for_key(key, colors=self.cockpit_color, texture=self.cockpit_texture, name=f"{self.name}:empty:{key}")
        if icon is not None:
            self._send_key_image_to_device(key, icon)
        else:
            logger.warning(f"deck {self.name}: {key}: no fill icon")

    # #######################################
    # Deck Specific Functions : Rendering
    #
    def _send_key_image_to_device(self, key, image):
        pass
