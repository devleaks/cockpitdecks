# Base class for all decks
#
import os
import logging

from typing import Dict, List
from abc import ABC, abstractmethod

from PIL import Image

from cockpitdecks import CONFIG_FOLDER, CONFIG_FILE, RESOURCES_FOLDER, ICONS_FOLDER
from cockpitdecks import Config, ID_SEP, CONFIG_KW, DEFAULT_LAYOUT, DEFAULT_ATTRIBUTE_PREFIX
from cockpitdecks.resources.color import TRANSPARENT_PNG_COLOR_BLACK, convert_color

from cockpitdecks.decks.resources import DeckType
from cockpitdecks.buttons.representation import IconBase
from cockpitdecks.event import PushEvent, EncoderEvent, SwipeEvent
from cockpitdecks.resources.intdatarefs import INTERNAL_DATAREF
from .page import Page
from .button import Button

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


class Deck(ABC):
    """
    Loads the configuration of a Deck.
    A Deck has a collection of Pages, and knows which one is currently being displayed.
    """

    DECK_NAME = "none"
    DEVICE_MANAGER = None

    def __init__(self, name: str, config: dict, cockpit: "Cockpit", device=None):
        self._config = config  # content of aircraft/deckconfig/config.yaml decks attributes for this deck
        self.cockpit = cockpit
        self.sim = cockpit.sim
        self.cockpit.set_logging_level(__name__)

        self.deck_type: DeckType = {}

        self.name = name
        self.device = device

        self.serial = config.get("serial")
        if self.serial is None:
            logger.warning(f"{self.name}: has no serial number")

        self.valid = False
        self.running = False

        # Layout
        self.layout = config.get(CONFIG_KW.LAYOUT.value, DEFAULT_LAYOUT)
        self._layout_config: Dict[str, str | int | float | bool | Dict] = {}  # content of aircraft/deckconfig/layout/config.yaml

        # Pages
        self.pages: Dict[str, Page] = {}
        self.home_page: Page | None = None
        self.current_page: Page | None = None
        self.previous_page: Page | None = None
        self.page_history: List[str] = []

        self.brightness = int(config.get("brightness", 100))

        self.home_page_name = self.get_attribute("home-page-name")
        self.logo = self.get_attribute("logo")
        self.wallpaper = self.get_attribute("wallpaper")

        if self.layout is not None:
            self.valid = True

    # #######################################
    #
    # Deck Specific Functions : Initialisation, description (capabilities)
    #
    def init(self):
        """Initialisation procedure

        Load deck type definition, load deck parameters, load layout, pages,
        and install and start deck software.
        """
        if not self.valid:
            logger.warning(f"deck {self.name}: is invalid")
            return
        self.set_deck_type()
        self.set_brightness(self.brightness)
        self.load()  # will load default page if no page found
        self.start()  # Some system may need to start before we can load a page

    def get_id(self) -> str:
        """Returns deck identifier

        Returns:
            [str]: Deck identifier string
        """
        l = self.layout if self.layout is not None else DEFAULT_LAYOUT
        return ID_SEP.join([self.cockpit.get_id(), self.name, l])

    def inc(self, name: str, amount: float = 1.0, cascade: bool = False):
        self.sim.inc_internal_data(name=ID_SEP.join([self.get_id(), name]), amount=amount, cascade=cascade)

    def is_virtual_deck(self) -> bool:
        return self.deck_type.is_virtual_deck()

    def get_deck_button_definition(self, idx):
        """Returns a deck's button definition from the deck type.

        Args:
            idx ([strıint]): Button index on deck

        Returns:
            [ButtonType]: The button type at index.
        """
        return self.deck_type.get_button_definition(idx)

    def set_deck_type(self):
        """Installs the reference to the deck type."""
        deck_type = self._config.get(CONFIG_KW.TYPE.value)
        self.deck_type = self.cockpit.get_deck_type(deck_type)
        if self.deck_type is None:
            logger.error(f"no deck definition for {deck_type}")

    def get_deck_type(self) -> DeckType:
        """Returns the deck's type

        Returns:
            DeckType: the deck's type
        """
        return self.deck_type

    def get_attribute(self, attribute: str, default=None, propagate: bool = True, silence: bool = True):
        """Returns the default attribute value

        ..if avaialble at the deck level.
        If not, returns the parent's default attribute value (cockpit).

        Args:
            attribute (str): Attribute name
            silence (bool): Whether to complain if defalut value is not found (default: `False`)

        Returns:
            [type]: [description]
        """
        default_attribute = attribute
        if not attribute.startswith(DEFAULT_ATTRIBUTE_PREFIX):
            if not attribute.startswith("cockpit-"):  # no "default" for global cockpit-* attributes
                default_attribute = DEFAULT_ATTRIBUTE_PREFIX + attribute

        # Is there such an attribute in the layout definition?
        if self._layout_config is not None:
            value = self._layout_config.get(attribute)

        if value is not None:  # found!
            if silence:
                logger.debug(f"deck {self.name} returning {attribute}={value} (from layout)")
            else:
                logger.info(f"deck {self.name} returning {attribute}={value} (from layout)")
            return self.cockpit.convert_if_color_attribute(attribute=attribute, value=value, silence=silence)

        if not silence:
            logger.info(f"deck {self.name} no value in layout {self.layout} ({self._layout_config.get('__filename__')})")

        # Is there such an attribute in the deck definition?
        if self._config is not None:
            value = self._config.get(attribute)

        if value is not None:  # found!
            if silence:
                logger.debug(f"deck {self.name} returning {attribute}={value} (from deck)")
            else:
                logger.info(f"deck {self.name} returning {attribute}={value} (from deck)")
            return self.cockpit.convert_if_color_attribute(attribute=attribute, value=value, silence=silence)

        if not silence:
            logger.info(f"deck {self.name} no value in deck config")

        if propagate:
            if not silence:
                logger.info(f"deck {self.name} propagate to cockpit for {attribute}")
            return self.cockpit.get_attribute(default_attribute, default=default, silence=silence)

        if not silence:
            logger.warning(f"deck {self.name}: attribute not found {attribute}, returning default ({default})")

        return self.cockpit.convert_if_color_attribute(attribute=attribute, value=default, silence=silence)

    def get_index_prefix(self, index):
        """Returns the prefix of a button index for this deck."""
        return self.deck_type.get_index_prefix(index=index)

    def get_index_numeric(self, index):
        """Returns the numeric part of the index of a button index for this deck."""
        return self.deck_type.get_index_numeric(index=index)

    def valid_indices(self, with_icon: bool = False):
        """Returns the valid indices for this deck."""
        return self.deck_type.valid_indices(with_icon=with_icon)

    def valid_activations(self, index=None):
        """Returns the valid activations for the button pointed by the index.
        If None is given, returns all valid activations.
        """
        return self.deck_type.valid_activations(index=index, source=self.cockpit)

    def valid_representations(self, index=None):
        """Returns the valid representations for the button pointed by the index.
        If None is given, returns all valid representations.
        """
        return self.deck_type.valid_representations(index=index, source=self.cockpit)

    # #######################################
    #
    # Deck Specific Functions : Representation
    #
    def inspect(self, what: str | None = None):
        """Triggered by the Inspect activation.

        This function is called on all pages of this Deck.
        """
        logger.info(f"*" * 60)
        logger.info(f"Deck {self.name} -- {what}")
        for v in self.pages.values():
            v.inspect(what)

    def print_page(self, page: Page):
        """Produces an image of the deck's layout in the current directory.
        For testing and development purpose.
        """
        pass

    # ##################################################
    #
    # Deck Specific Functions : Page manipulations
    #
    def load(self):
        """
        Loads pages during configuration. If none is found, create a simple,
        static page with one activatio.

        """
        verbose = True

        if self.layout is None:
            self.make_default_page()
            return

        dn = os.path.join(self.cockpit.acpath, CONFIG_FOLDER, self.layout)
        if not os.path.exists(dn):
            logger.warning(f"deck {self.name} has no layout folder '{self.layout}', loading default page")
            self.make_default_page()
            return

        pages = os.listdir(dn)
        if CONFIG_FILE in pages:  # first load config
            self._layout_config = Config(os.path.join(dn, CONFIG_FILE))
            if not self._layout_config.is_valid():
                logger.debug("no layout config file")
            else:  # get new value if it exists
                self.home_page_name = self.get_attribute("home-page-name", self.home_page_name)
                self.logo = self.get_attribute("logo", self.logo)
                self.wallpaper = self.get_attribute("wallpaper", self.wallpaper)

        for p in pages:
            if p == CONFIG_FILE:
                continue
            elif not (p.lower().endswith(".yaml") or p.lower().endswith(".yml")):  # not a yaml file
                logger.debug(f"{dn}: ignoring file {p}")
                continue
            elif p.lower().endswith(".inc.yaml"):  # a special include file
                logger.debug(f"{dn}: file {p} is an include")
                continue

            fn = os.path.join(dn, p)
            # if os.path.exists(fn):  # we know the file should exists...
            page_config = Config(fn)
            if not page_config.is_valid():
                logger.warning(f"file {p} not found or invalid")
                continue

            verbose = page_config.get("verbose", False)

            page_name = ".".join(p.split(".")[:-1])  # build default page name, remove extension ".yaml" or ".yml" from filename
            if CONFIG_KW.NAME.value in page_config:
                page_name = page_config[CONFIG_KW.NAME.value]

            if page_name in self.pages.keys():
                logger.warning(f"page {page_name}: duplicate name, ignored")
                continue

            if not CONFIG_KW.BUTTONS.value in page_config:
                logger.error(f"{page_name} has no button definition '{CONFIG_KW.BUTTONS.value}', ignoring")
                continue

            display_fn = fn.replace(os.path.join(self.cockpit.acpath, CONFIG_FOLDER + os.sep), "..")
            logger.debug(f"loading page {page_name} (from file {display_fn})..")

            doc = page_config.get("info")
            if doc is not None:
                logger.info(f"page {page_name}: {doc}")

            this_page = Page(page_name, page_config.store, self)
            self.pages[page_name] = this_page

            # Page buttons
            this_page.load_buttons(buttons=page_config[CONFIG_KW.BUTTONS.value], deck_type=self.deck_type)

            # Page includes
            if CONFIG_KW.INCLUDES.value in page_config:
                includes = page_config[CONFIG_KW.INCLUDES.value]
                if type(page_config[CONFIG_KW.INCLUDES.value]) is str:  # just one file
                    includes = includes.split(",")
                logger.debug(f"deck {self.name}: page {page_name} includes {includes}..")
                ipb = 0
                for inc in includes:
                    if inc.endswith(".inc") or "." not in inc:  # no extension
                        fni = os.path.join(dn, inc + ".yaml")
                    # if not os.path.exists(fni):
                    #     fni = os.path.join(dn, inc + ".yml")
                    # if not os.path.exists(fni):
                    #     fni = os.path.join(dn, inc + ".txt")
                    # if not os.path.exists(fni):
                    #     logger.warning(f"includes: {inc}: file {os.path.join(dn, inc + '.{yaml|yml|txt}')} not found")
                    #     continue
                    if not os.path.exists(fni):
                        logger.warning(f"includes: {inc}: file {os.path.join(dn, inc + '.{yaml|yml|txt}')} not found")
                        continue
                    inc_config = Config(fni)
                    if inc_config.is_valid():
                        this_page.merge_attributes(inc_config.store)  # merges attributes first since can have things for buttons....
                        if CONFIG_KW.BUTTONS.value in inc_config:
                            before = len(this_page.buttons)
                            this_page.load_buttons(buttons=inc_config[CONFIG_KW.BUTTONS.value], deck_type=self.deck_type)
                            ipb = len(this_page.buttons) - before
                        del inc_config.store[CONFIG_KW.BUTTONS.value]
                    else:
                        logger.warning(f"includes: {inc}: file {fni} is invalid")
                display_fni = fni.replace(
                    os.path.join(self.cockpit.acpath, CONFIG_FOLDER + os.sep),
                    "..",
                )
                if verbose:
                    logger.info(f"deck {self.name}: page {page_name} includes {inc} (from file {display_fni}), include contains {ipb} buttons")
                logger.debug("includes: ..included")

            if verbose:
                logger.info(f"deck {self.name}: page {page_name} loaded (from file {display_fn}), contains {len(this_page.buttons)} buttons")

        if not len(self.pages) > 0:
            self.valid = False
            logger.error(f"{self.name}: has no page, ignoring")
            # self.load_default_page()
        else:
            self.set_home_page()
            logger.info(f"deck {self.name}: loaded {len(self.pages)} pages from layout {self.layout}: {', '.join(self.pages.keys())}.")

    def change_page(self, page: str | None = None):
        """Change the deck's page to the one supplied as argument.
           If none supplied, load the default page.

        Args:
            page| None ([str]): Name of page to load (default: `None`)

        Returns:
            [str | None]: Name of page loaded or None.
        """
        if page is None:
            logger.debug(f"deck {self.name} loading home page")
            self.load_home_page()
            return None
        if page == CONFIG_KW.BACKPAGE.value:
            if len(self.page_history) > 1:
                page = self.page_history.pop()  # this page
                page = self.page_history.pop()  # previous one
            else:
                if self.home_page is not None:
                    page = self.home_page.name
            logger.debug(f"deck {self.name} back page to {page}..")
        logger.debug(f"deck {self.name} changing page to {page}..")
        if page in self.pages.keys():
            if self.current_page is not None:
                logger.debug(f"deck {self.name} unloading page {self.current_page.name}..")
                logger.debug("..unloading datarefs..")
                self.cockpit.sim.remove_datarefs_to_monitor(self.current_page.simulator_data)
                logger.debug("..cleaning page..")
                self.current_page.clean()
                logger.debug(f"..reset device {self.name}..")
                self.device.reset()
            logger.debug(f"deck {self.name} ..installing new page {page}..")
            self.inc(INTERNAL_DATAREF.PAGE_CHANGES.value)
            self.previous_page = self.current_page
            self.current_page = self.pages[page]
            self.page_history.append(self.current_page.name)
            logger.debug("..loading datarefs..")
            self.cockpit.sim.add_datarefs_to_monitor(self.current_page.simulator_data)  # set which datarefs to monitor
            logger.debug("..rendering page..")
            self.current_page.render()
            logger.debug(f"deck {self.name} ..done")
            logger.info(f"deck {self.name} changed page to {page}")
            return self.current_page.name
        else:
            logger.warning(f"deck {self.name}: ..page {page} not found")
            if self.current_page is not None:
                return self.current_page.name
        return None

    def reload_page(self):
        """Reloads page to take into account changes in definition

        Please note that this may loead to unexpected results if page was
        too heavily modified or interaction with other pages occurred.
        """
        self.inc(INTERNAL_DATAREF.DECK_RELOADS.value)
        self.change_page(self.current_page.name)

    def set_home_page(self):
        """Finds and install the home page, if any."""
        if not len(self.pages) > 0:
            self.valid = False
            logger.error(f"deck {self.name} has no page, ignoring")
        else:
            if self.home_page_name in self.pages.keys():
                self.home_page = self.pages[self.home_page_name]
            else:
                logger.debug(f"deck {self.name}: no home page named {self.home_page_name}")
                self.home_page = self.pages[list(self.pages.keys())[0]]  # first page
            logger.info(f"deck {self.name}: home page {self.home_page.name}")

    def load_home_page(self):
        """Loads the home page, if any."""
        if self.home_page is not None:
            self.change_page(self.home_page.name)
            logger.debug(f"deck {self.name}, home page {self.home_page.name} loaded")
        else:
            logger.debug(f"deck {self.name} has no home page")

    @abstractmethod
    def make_default_page(self, b: str | None = None):
        """Generates a default home page for the deck,
        in accordance with its capabilities.
        """
        pass

    # ##################################################
    #
    # Deck Specific Functions : Usage
    #
    def get_button_value(self, name):
        """Get the value of a button from its internal identifier name

        [description]

        Args:
            name ([type]): [description]

        Returns:
            [type]: [description]
        """
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

    # #######################################
    #
    # Deck Specific Functions : Rendering
    #
    def fill_empty(self, key):
        """Procedure to fill keys that do not contain any feedback rendering.
        key ([str]): Key index to fill with empty/void feedback.
        """
        pass

    def clean_empty(self, key):
        """Procedure to clean (remove previous) keys that do not contain any feedback rendering.
        key ([str]): Key index to clean with empty/void feedback.
        """
        pass

    def vibrate(self, button):
        if hasattr(self, "_vibrate"):
            self._vibrate(button.get_vibration())

    def set_brightness(self, brightness: int):
        if self.device is not None and hasattr(self.device, "set_brightness"):
            self.device.set_brightness(brightness)

    @abstractmethod
    def render(self, button: Button):
        """Main procedure to render a button on the deck

        The procedure mainly fetches information from the button, for example,
        gets an image for display in a neutral, generic format (PNG, JPEG...),
        then format the image to the deck specific format (B646 format for example)
        and send it to the deck for display using the deck drive APIs.
        It also convert the button index to the specific index required by the deck.

        Args;
            button ([Button]): Button to render on the deck.
        """
        pass

    # #######################################
    #
    # Deck Specific Functions : Device and operations
    #
    @abstractmethod
    def start(self):
        """Called at end of initialisation to start the deck interaction,
        both ways.
        """
        pass

    def terminate(self, disconnected: bool = False):
        """Called at end of use of deck to cleanly reset all buttons to a default, neutral state
        and stop deck interaction,
        """
        for p in self.pages.values():
            p.terminate(disconnected)
        self.pages = {}

    # ##################################################
    #
    # Deck Specific Functions : Callbacks and activation
    #
    # There are highliy deck specific, no general function.
    def replay(self, key=None, state=None, data: dict | None = None):
        # This is a fairly generic replay function
        print("===== replay", self.name, key, state, data)
        if state in [0, 1, 4]:
            e = PushEvent(
                deck=self, button=key, pressed=(state != 0), pulled=(state == 4), code=state, autorun=False
            )  # autorun enqueues it in cockpit.event_queue for later execution
            e._replay = True
            e.run()
            logger.debug(f"REPLAY PushEvent deck {self.name} key {key} = {state}")
            return  # no other possible handling
        if state in [2, 3]:
            logger.debug(f"REPLAY EncoderEvent deck {self.name} key {key} = {state}")
            e = EncoderEvent(deck=self, button=key, clockwise=state == 2, code=state, autorun=False)
            e._replay = True
            e.run()
            return  # no other possible handling
        if state in [10, 11]:
            if data is None:
                logger.warning(f"REPLAY TouchEvent deck {self.name} key {key} = {state}: no data")
                return
            logger.debug(f"REPLAY TouchEvent deck {self.name} key {key} = {state}, {self._touch_event_start}, {data}")
            if state == 10:  # start
                self._touch_event_start = TouchEvent(
                    deck=self, button=key, pos_x=data.get("x"), pos_y=data.get("y"), cli_ts=data.get("ts"), code=state, autorun=False
                )
                self._touch_event_start._replay = True
                self._touch_event_start.run()
            else:  # probably end
                e = TouchEvent(
                    deck=self,
                    button=key,
                    pos_x=data.get("x"),
                    pos_y=data.get("y"),
                    cli_ts=data.get("ts"),
                    start=self._touch_event_start,
                    code=state,
                    autorun=False,
                )
                e._replay = True
                e.run()
                self._touch_event_start = None  # reset start
            return  # no other possible handling
        if state in [14]:
            e = TouchEvent(deck=self, button=key, pos_x=data.get("x"), pos_y=data.get("y"), cli_ts=data.get("ts"), code=state, autorun=False)
            e._replay = True
            e.run()
            logger.debug(f"REPLAY TouchEvent deck {self.name} key {key} = {state} (press event)")
            return  # no other possible handling
        if state in [9]:
            logger.debug(f"REPLAY SlideEvent deck {self.name} key {key} = {state}")
            if data is not None and "value" in data:
                e = SlideEvent(deck=self, button=key, value=int(data.get("value")), code=state, autorun=False)
                e._replay = True
                e.run()
                return  # no other possible handling
            else:
                logger.warning(f"deck {deck.name}: REPLAY SliderEvent has no value ({data})")
        logger.warning(f"deck {deck.name}: REPLAY unhandled event ({deck}, {key}, {state}, {data})")
        return None

    def get_default_page(self, index: str):
        return f"""
buttons:
  - index: {index}
    type: push
    formula: ${{state:activation_count}} 2 %
"""


class DeckWithIcons(Deck):
    """
    This type of deck is a variant of the above for decks with LCD capabilites,
    LCD being individual key display (like streamdecks) or a larger LCD with areas
    of interaction, like LoupedeckLive.
    This class complement the generic deck with image display function
    and utilities for image transformation.
    """

    def __init__(self, name: str, config: dict, cockpit: "Cockpit", device=None):
        Deck.__init__(self, name=name, config=config, cockpit=cockpit, device=device)

    def get_default_icon(self):
        icons = self.cockpit.icons
        default_icon_name = self.get_attribute("icon-name", "none.png")
        if default_icon_name in icons:
            return icons.get(default_icon_name)
        else:
            if len(icons) > 0:
                first = list(icons.keys())[0]
                return icons.get(first)
            else:
                logger.error("no default icon")
                return None

    # #######################################
    #
    # Deck Specific Functions : Icon specific functions
    #
    def get_image_size(self, index):
        """Gets image size for deck button index"""
        button_def = self.deck_type.get_button_definition(index)
        return button_def.display_size()

    def get_wallpaper(self, index):
        """Gets image size for deck button index"""
        button_def = self.deck_type.get_button_definition(index)
        return button_def.get_wallpaper()

    def create_empty_icon_for_key(self, index):
        return Image.new(mode="RGBA", size=self.get_image_size(index), color=TRANSPARENT_PNG_COLOR_BLACK)

    def get_icon_background(
        self,
        name: str,
        width: int,
        height: int,
        texture_in,
        color_in,
        use_texture=True,
        who: str = "Deck",
    ):
        """
        Returns a **Pillow Image** of size width x height with either the file specified by texture or a uniform color
        """

        def get_texture():
            tarr = []
            if texture_in is not None:
                tarr.append(texture_in)
            # default_icon_texture = self.get_attribute("icon-texture")
            # if default_icon_texture is not None:
            #     tarr.append(default_icon_texture)
            cockpit_texture = self.get_attribute("cockpit-texture")
            if cockpit_texture is not None:
                tarr.append(cockpit_texture)

            dirs = []
            dirs.append(os.path.join(os.path.dirname(__file__), RESOURCES_FOLDER))
            dirs.append(os.path.join(os.path.dirname(__file__), RESOURCES_FOLDER, ICONS_FOLDER))
            if self.cockpit.acpath is not None:  # add to search path
                dirs.append(os.path.join(self.cockpit.acpath, CONFIG_FOLDER, RESOURCES_FOLDER))
                dirs.append(
                    os.path.join(
                        self.cockpit.acpath,
                        CONFIG_FOLDER,
                        RESOURCES_FOLDER,
                        ICONS_FOLDER,
                    )
                )

            for dn in dirs:
                for texture in tarr:
                    fn = os.path.join(dn, texture)
                    if os.path.exists(fn):
                        return fn
            return None

        def get_color():
            for t in [
                color_in,
                # self.get_attribute("icon-color"),
                self.get_attribute("cockpit-color"),
            ]:
                if t is not None:
                    return convert_color(t)
            return convert_color(self.get_attribute("cockpit-color"))

        image = None
        if use_texture and texture_in is not None:
            image = self.cockpit.get_icon_image(texture_in)

        if image is not None:  # found a texture as requested
            logger.debug(f"{who}: use texture {texture_in}")
            image = image.resize((width, height))
            self.inc(INTERNAL_DATAREF.RENDER_BG_TEXTURE.value)
            return image
        if use_texture and texture_in is None:
            logger.debug(f"{who}: should use texture but no texture found, using uniform color")
        # texture = get_texture()
        # if use_texture and texture is not None:
        #     texture = os.path.normpath(texture)
        #     image = self.cockpit.get_icon_image(texture)
        # if image is not None:  # found a texture as requested
        #     logger.debug(f"{who}: use texture {texture}")
        #     image = image.resize((width, height))
        #     return image
        # if use_texture and texture is None:
        #     logger.debug(f"{who}: should use texture but no texture found, using uniform color")
        color = get_color()
        image = Image.new(mode="RGBA", size=(width, height), color=color)
        logger.debug(f"{who}: uniform color {color} (color_in={color_in})")
        self.inc(INTERNAL_DATAREF.RENDER_BG_COLOR.value)
        return image

    def create_icon_for_key(self, index, colors, texture):
        """Create a default icon for supplied key with proper texture or color"""
        image = None
        width, height = self.get_image_size(index)
        wp = self.get_wallpaper(index)  # for this block
        self.inc(INTERNAL_DATAREF.RENDER_CREATE_ICON.value)
        return (
            wp
            if wp is not None
            else self.get_icon_background(
                name=str(index),
                width=width,
                height=height,
                texture_in=texture,
                color_in=colors,
                use_texture=True,
                who=type(self).__name__,
            )
        )

    def scale_icon_for_key(self, index, image, name: str | None = None):
        margins = [0, 0, 0, 0]
        final_image = self.create_icon_for_key(index, colors=None, texture=None)

        thumbnail_max_width = final_image.width - (margins[1] + margins[3])
        thumbnail_max_height = final_image.height - (margins[0] + margins[2])

        thumbnail = image.convert("RGBA")
        thumbnail.thumbnail((thumbnail_max_width, thumbnail_max_height), Image.LANCZOS)

        thumbnail_x = margins[3] + (thumbnail_max_width - thumbnail.width) // 2
        thumbnail_y = margins[0] + (thumbnail_max_height - thumbnail.height) // 2

        final_image.paste(thumbnail, (thumbnail_x, thumbnail_y), thumbnail)
        return final_image

    def fill_empty(self, key):
        """Fills all empty buttons with a default representation.

        If clean is True, removes the reprensetation rather than install a default one.
        Removing a representation often means installing a default, neutral one.
        """
        icon = None
        if self.current_page is not None:
            icon = self.create_icon_for_key(
                key,
                colors=convert_color(self.current_page.get_attribute("cockpit-color")),
                texture=self.current_page.get_attribute("cockpit-texture"),
            )
        else:
            icon = self.create_icon_for_key(
                key,
                colors=self.get_attribute("cockpit-color"),
                texture=self.get_attribute("cockpit-texture"),
            )
        if icon is not None:
            self.set_key_icon(key, icon)
        else:
            logger.warning(f"deck {self.name}: {key}: no fill icon")

    def clean_empty(self, key):
        """Fills a button pointed by index with an empty representation."""
        self.fill_empty(key)

    # #######################################
    #
    # Deck Specific Functions : Rendering
    #
    def set_key_icon(self, key, image):
        """Access to lower level, raw function to install an image on a deck display
        pointed by th index key.

        Args:
            key ([type]): [description]
            image ([type]): [description]
        """
        pass

    def make_button(self, config: dict):
        # testing. returns random icon
        page = Page(name="_BUTTONDESIGNER", config={}, deck=self)
        page.load_buttons(buttons=[config], deck_type=self.deck_type)
        button: Button = page.buttons[list(page.buttons.keys())[0]]
        representation = button._representation
        if not isinstance(representation, IconBase):
            logger.warning(f"button: representation is not an image ({type(representation)})")
            return None
        return button

    def get_default_page(self, index: str):
        return f"""
buttons:
  - index: {index}
    type: push
    multi-texts:
      - text: 'HELLO\nPRESS ME'
        text-size: 20
      - text: 'WORLD\nPRESS ME'
        text-size: 20
    formula: ${{state:activation_count}} 2 %
"""
