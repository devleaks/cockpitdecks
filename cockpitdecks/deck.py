# Base class for all decks
#
import os
import logging
import pickle

from typing import Dict, List, Any
from abc import ABC, abstractmethod
from functools import reduce

from PIL import Image

from cockpitdecks import CONFIG_FOLDER, CONFIG_FILE, DECK_FEEDBACK, RESOURCES_FOLDER, ICONS_FOLDER
from cockpitdecks import ID_SEP, CONFIG_KW, DEFAULT_LAYOUT
from cockpitdecks import Config
from cockpitdecks.resources.color import TRANSPARENT_PNG_COLOR_BLACK, convert_color, add_ext

from .page import Page
from .button import Button
from cockpitdecks.event import DeckEvent, PushEvent
from cockpitdecks.decks.resources import DeckType

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

DECKS_FOLDER = "decks"


class Deck(ABC):
    """
    Loads the configuration of a Deck.
    A Deck has a collection of Pages, and knows which one is currently being displayed.
    """

    DECK_NAME = "none"

    def __init__(self, name: str, config: dict, cockpit: "Cockpit", device=None):
        self._config = config
        self.name = name
        self.cockpit = cockpit
        self.device = device
        self.deck_type: DeckType = {}

        self.cockpit.set_logging_level(__name__)

        self._layout_config: Dict[str, str | int | float | bool | Dict] = {}
        self.pages: Dict[str, Page] = {}
        self.home_page: Page | None = None
        self.current_page: Page | None = None
        self.previous_page: Page | None = None
        self.page_history: List[str] = []

        self.valid = False
        self.running = False

        self.previous_key_values: Dict[str, Any] = {}
        self.current_key_values: Dict[str, Any] = {}

        if "serial" in config:
            self.serial = config["serial"]
        else:
            self.valid = False
            logger.error(f"{self.name}: has no serial number, cannot use")

        self.brightness = 100
        if "brightness" in config:
            self.brightness = int(config["brightness"])
            self.set_brightness(self.brightness)

        self.layout = config.get(CONFIG_KW.LAYOUT.value)
        # if self.layout is None:
        #     self.layout = DEFAULT_LAYOUT
        #     logger.warning(f"deck has no layout, using default")

        self.home_page_name = config.get("home-page-name", self.get_attribute("default-home-page-name"))
        self.logo = config.get("logo", self.get_attribute("default-logo"))
        self.wallpaper = config.get("wallpaper", self.get_attribute("default-wallpaper"))

        self.valid = True

    # #######################################
    #
    # Deck Common Functions
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
        self.load()  # will load default page if no page found
        self.start()  # Some system may need to start before we can load a page

    def get_id(self) -> str:
        """Returns deck identifier

        Returns:
            [str]: Deck identifier string
        """
        l = self.layout if self.layout is not None else "-nolayout-"
        return ID_SEP.join([self.cockpit.get_id(), self.name, l])

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

    def get_attribute(self, attribute: str, silence: bool = False):
        """Returns the default attribute value

        ..if avaialble at the deck level.
        If not, returns the parent's default attribute value (cockpit).

        Args:
            attribute (str): Attribute name
            silence (bool): Whether to complain if defalut value is not found (default: `False`)

        Returns:
            [type]: [description]
        """
        val = self._config.get(attribute)
        if val is not None:
            return val
        val = self._layout_config.get(attribute)
        if val is not None:
            return val
        ATTRNAME = "_defaults"
        val = None
        if hasattr(self, ATTRNAME):
            ld = getattr(self, ATTRNAME)
            if isinstance(ld, dict):
                val = ld.get(attribute)
        return val if val is not None else self.cockpit.get_attribute(attribute, silence=silence)

    # ##################################################
    #
    # Page manipulations
    #
    def load(self):
        """
        Loads pages during configuration. If none is found, create a simple,
        static page with one activatio.

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
            self._layout_config = Config(os.path.join(dn, CONFIG_FILE))
            if not self._layout_config.is_valid():
                logger.debug(f"no layout config file")

        for p in pages:
            if p == CONFIG_FILE:
                continue
            elif not (p.lower().endswith(".yaml") or p.lower().endswith(".yml")):  # not a yaml file
                logger.debug(f"{dn}: ignoring file {p}")
                continue

            fn = os.path.join(dn, p)
            # if os.path.exists(fn):  # we know the file should exists...
            page_config = Config(fn)
            if not page_config.is_valid():
                logger.warning(f"file {p} not found")
                continue

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

            this_page = Page(page_name, page_config.store, self)
            self.pages[page_name] = this_page

            # Page buttons
            this_page.load_buttons(page_config[CONFIG_KW.BUTTONS.value])

            # Page includes
            if CONFIG_KW.INCLUDES.value in page_config:
                includes = page_config[CONFIG_KW.INCLUDES.value]
                if type(page_config[CONFIG_KW.INCLUDES.value]) == str:  # just one file
                    includes = includes.split(",")
                logger.debug(f"deck {self.name}: page {page_name} includes {includes}..")
                ipb = 0
                for inc in includes:
                    fni = os.path.join(dn, inc + ".yaml")
                    inc_config = Config(fni)
                    if inc_config.is_valid():
                        this_page.merge_attributes(inc_config.store)  # merges attributes first since can have things for buttons....
                        if CONFIG_KW.BUTTONS.value in inc_config:
                            before = len(this_page.buttons)
                            this_page.load_buttons(inc_config[CONFIG_KW.BUTTONS.value])
                            ipb = len(this_page.buttons) - before
                        del inc_config.store[CONFIG_KW.BUTTONS.value]
                    else:
                        logger.warning(f"includes: {inc}: file {fni} not found")
                display_fni = fni.replace(
                    os.path.join(self.cockpit.acpath, CONFIG_FOLDER + os.sep),
                    "..",
                )
                logger.info(f"deck {self.name}: page {page_name} includes {inc} (from file {display_fni}), include contains {ipb} buttons")
                logger.debug(f"includes: ..included")

            logger.info(f"deck {self.name}: page {page_name} loaded (from file {display_fn}), contains {len(this_page.buttons)} buttons")

        if not len(self.pages) > 0:
            self.valid = False
            logger.error(f"{self.name}: has no page, ignoring")
            # self.load_default_page()
        else:
            self.set_home_page()
            logger.info(f"deck {self.name}: loaded {len(self.pages)} pages from layout {self.layout}")

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
                logger.debug(f"..unloading datarefs..")
                self.cockpit.sim.remove_datarefs_to_monitor(self.current_page.datarefs)
                self.cockpit.sim.remove_collections_to_monitor(self.current_page.dataref_collections)
                logger.debug(f"..cleaning page..")
                self.current_page.clean()
            logger.debug(f"deck {self.name} ..installing new page {page}..")
            self.previous_page = self.current_page
            self.current_page = self.pages[page]
            self.page_history.append(self.current_page.name)
            logger.debug(f"..reset device {self.name}..")
            self.device.reset()
            logger.debug(f"..loading datarefs..")
            self.cockpit.sim.add_datarefs_to_monitor(self.current_page.datarefs)  # set which datarefs to monitor
            self.cockpit.sim.add_collections_to_monitor(self.current_page.dataref_collections)
            logger.debug(f"..rendering page..")
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
            logger.debug(f"deck {self.name}: home page {self.home_page.name}")

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
    # Usage
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
    # Deck Specific Functions : Description (capabilities)
    #
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
        return self.deck_type.valid_activations(index=index)

    def valid_representations(self, index=None):
        """Returns the valid representations for the button pointed by the index.
        If None is given, returns all valid representations.
        """
        return self.deck_type.valid_representations(index=index)

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
    # Deck Specific Functions : Device
    #
    @abstractmethod
    def start(self):
        """Called at end of initialisation to start the deck interaction,
        both ways.
        """
        pass

    def terminate(self):
        """Called at end of use of deck to cleanly reset all buttons to a default, neutral state
        and stop deck interaction,
        """
        for p in self.pages.values():
            p.terminate()
        self.pages = {}


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

        self.icons: Dict[str, "PIL.Image"] = {}  # icons ready for this deck

    # #######################################
    # Deck Specific Functions
    #
    # #######################################
    # Deck Specific Functions : Installation
    #
    def init(self):
        """Specific DeckIcon initialisation procedure.

        Add a step to prepare and cache deck icons.
        Icons in proper format are cached locally for performance reasons.
        New icons will be cached when created.
        """
        if not self.valid:
            logger.warning(f"deck {self.name}: is invalid")
            return
        self.set_deck_type()
        self.load()  # will load default page if no page found
        self.start()  # Some system may need to start before we can load a page

    def get_display_for_pil(self, b: str | None = None):
        """
        Return device or device element to use for PIL.
        """
        return self.device

    def get_index_image_size(self, index):
        """Returns the image size and offset for supplied deck index."""
        b = self._buttons.get(index)
        if b is not None:
            return b.get(CONFIG_KW.IMAGE.value)
        logger.warning(f"deck {self.name}: no button index {index}")
        return None

    def get_icon(self, candidate_icon):
        icon = None
        for ext in [".png", ".jpg", ".jpeg"]:
            fn = add_ext(candidate_icon, ext)
            if icon is None and fn in self.icons.keys():
                logger.debug(f"deck {self.name}: {type(self).__name__}: icon {fn} found")
                return fn
        # icon is still None
        logger.debug(
            f"deck {self.name}: {type(self).__name__}: icon not found {candidate_icon}, asking to cockpit..."
        )  # , cockpit_icons={self.cockpit.icons.keys()}
        return self.cockpit.get_icon(candidate_icon)

    def get_icon_image(self, icon):
        image = self.icons.get(icon)
        return image if image is not None else self.cockpit.icons.get(icon)

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
            default_icon_texture = self.get_attribute("default-icon-texture")
            if default_icon_texture is not None:
                tarr.append(default_icon_texture)
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
                self.get_attribute("default-icon-color"),
                self.get_attribute("cockpit-color"),
            ]:
                if t is not None:
                    return convert_color(t)
            return convert_color(self.get_attribute("cockpit-color"))

        image = None

        texture = get_texture()
        if use_texture and texture is not None:
            texture = os.path.normpath(texture)
            if texture in self.cockpit.icons.keys():
                image = self.cockpit.get_icon_image(texture)

        if image is not None:  # found a texture as requested
            logger.debug(f"{who}: use texture {texture}")
            image = image.resize((width, height))
            return image

        if use_texture and texture is None:
            logger.debug(f"{who}: should use texture but no texture found, using uniform color")

        color = get_color()
        image = Image.new(mode="RGBA", size=(width, height), color=color)
        logger.debug(f"{who}: uniform color {color} (color_in={color_in})")
        return image

    def create_empty_image_for_key(self, index):
        return Image.new(mode="RGBA", size=self.get_image_size(index), color=TRANSPARENT_PNG_COLOR_BLACK)

    def create_icon_for_key(self, index, colors, texture, name: str | None = None):
        """Create a default icon for supplied key"""
        if name is not None and name in self.icons.keys():
            return self.icons.get(name)

        image = None
        width, height = self.get_image_size(index)
        image = self.get_icon_background(
            name=str(index),
            width=width,
            height=height,
            texture_in=texture,
            color_in=colors,
            use_texture=True,
            who=type(self).__name__,
        )

        if image is not None:
            image = image.convert("RGB")
            if name is not None:
                self.icons[name] = image

        return image

    def scale_icon_for_key(self, index, image, name: str | None = None):

        if name is not None and name in self.icons.keys():
            return self.icons.get(name)

        margins=[0, 0, 0, 0]
        final_image = self.create_icon_for_key(index, colors=None, texture=None)

        thumbnail_max_width = final_image.width - (margins[1] + margins[3])
        thumbnail_max_height = final_image.height - (margins[0] + margins[2])

        thumbnail = image.convert("RGBA")
        thumbnail.thumbnail((thumbnail_max_width, thumbnail_max_height), Image.LANCZOS)

        thumbnail_x = margins[3] + (thumbnail_max_width - thumbnail.width) // 2
        thumbnail_y = margins[0] + (thumbnail_max_height - thumbnail.height) // 2

        final_image.paste(thumbnail, (thumbnail_x, thumbnail_y), thumbnail)

        if final_image is not None:
            final_image = final_image.convert("RGB")
            if final_image is not None:
                self.icons[name] = final_image
        return final_image

    def get_image_size(self, index):
        """Gets image size for deck button index"""
        button = self.deck_type.get_button_definition(index)
        return button.display_size()

    def fill_empty(self, key, clean: bool = False):
        """Fills all empty buttons with e defalut representation.

        If clean is True, removes the reprensetation rather than install a default one.
        Removing a representation often means installing a default, neutral one.
        """
        icon = None
        if self.current_page is not None:
            icon = self.create_icon_for_key(
                key,
                colors=convert_color(self.current_page.get_attribute("cockpit-color")),
                texture=self.current_page.get_attribute("cockpit-texture"),
                name=f"{self.name}:{self.current_page.name}:{key}",
            )
        else:
            icon = self.create_icon_for_key(
                key,
                colors=self.get_attribute("cockpit-color"),
                texture=self.get_attribute("cockpit-texture"),
                name=f"{self.name}:{key}",
            )
        if icon is not None:
            self._send_key_image_to_device(key, icon)
        else:
            logger.warning(f"deck {self.name}: {key}: no fill icon{' cleaning' if clean else ''}")

    def clean_empty(self, key):
        """Fills a button pointed by index with an empty representation."""
        self.fill_empty(key, clean=True)

    # #######################################
    # Deck Specific Functions : Rendering
    #
    def _send_key_image_to_device(self, key, image):
        """Access to lower level, raw function to install an image on a deck display
        pointed by th index key.

        Args:
            key ([type]): [description]
            image ([type]): [description]
        """
        pass
