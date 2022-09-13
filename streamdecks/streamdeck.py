import os
import logging
import yaml
import threading

from time import sleep

from enum import Enum

from PIL import Image, ImageDraw, ImageFont, ImageOps
from StreamDeck.ImageHelpers import PILHelper

from .constant import CONFIG_DIR, RESOURCES_FOLDER, INIT_PAGE, DEFAULT_LAYOUT
from .constant import convert_color
from .button import Button, BUTTON_TYPES

logger = logging.getLogger("Streamdeck")
loggerPage = logging.getLogger("Page")
loggerDataref = logging.getLogger("Dataref")

DEFAULT_PAGE_NAME = "X-Plane"
POLL_FREQ = 5  # default is 20

class Page:
    """
    A Page is a collection of buttons.
    """

    def __init__(self, name: str, deck: "Streamdeck"):
        self.name = name
        self.deck = deck
        self.xp = self.deck.decks.xp  # shortcut alias

        self.fill_empty = None

        self.buttons = {}
        self.datarefs = {}


    def add_button(self, idx: int, button: Button):
        if idx in self.buttons.keys():
            loggerPage.error(f"add_button: button index {idx} already defined, ignoring {button.name}")
            return
        self.buttons[idx] = button
        # Build page dataref list, each dataref points at the button(s) that use it
        # loggerPage.debug(f"add_button: page {self.name}: button {button.name}: datarefs: {button.dataref_values.keys()}")

        for d in button.get_datarefs():
            if d not in self.datarefs:
                ref = self.xp.get_dataref(d)
                if ref is not None:
                    self.datarefs[d] = ref
                    self.datarefs[d].add_listener(button)
                else:
                    loggerPage.warning(f"add_button: page {self.name}: button {button.name}: failed to create dataref {d}")
        loggerPage.debug(f"add_button: page {self.name}: button {button.name} {idx} added")

    def dataref_changed(self, dataref):
        """
        For each button on this page, notifies the button if a dataref used by that button has changed.
        """
        if dataref.path in self.datarefs.keys():
            self.datarefs[dataref].notify()
        else:
            loggerPage.warning(f"dataref_changed: page {self.name}: dataref {dataref.path} not found")

    def activate(self, idx: int):
        if idx in self.buttons.keys():
            self.buttons[idx].activate()
        else:
            loggerPage.error(f"activate: page {self.name}: invalid button index {idx}")

    def render(self):
        """
        Renders this page on the deck
        """
        loggerPage.debug(f"render: page {self.name}: fill {self.fill_empty}")
        for button in self.buttons.values():
            button.render()
            # loggerPage.debug(f"render: page {self.name}: button {button.name} rendered")
        if self.fill_empty is not None:
            icon = None
            if self.fill_empty.startswith("(") and self.fill_empty.endswith(")"):
                colors = convert_color(self.fill_empty)
                icon = PILHelper.create_image(deck=self.deck.device, background=colors)
            elif self.fill_empty in self.deck.icons.keys():
                icon = self.deck.icons[self.fill_empty]
            if icon is not None:
                image = PILHelper.to_native_format(self.deck.device, icon)
                for i in range(self.deck.device.key_count()):
                    if i not in self.buttons.keys():
                        self.deck.device.set_key_image(i, image)
            else:
                loggerPage.warning(f"render: page {self.name}: fill image {self.fill_empty} not found")

    def clean(self):
        """
        Ask each button to stop rendering and clean its mess.
        """
        for button in self.buttons.values():
            button.clean()

class Streamdeck:
    """
    Loads the configuration of a Stream Deck.
    A Streamdeck has a collection of Pages, and knows which one is currently being displayed.
    """

    def __init__(self, name: str, config: dict, decks: "Streamdecks", device = None):
        self.name = name
        self.decks = decks
        self.device = device
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
            logger.error(f"__init__: stream deck has no serial number, cannot use")

        if device is not None:
            self.numkeys = device.key_count()
            logger.info(f"__init__: stream deck {self.name} has {self.numkeys} keys")
        # elif "model" in config:
        #     MAX_STREAM_DECK_MODEL_KEYS = {
        #         "STREAM_DECK_XL": 32,
        #         "STREAM_DECK": 15,
        #         "STREAM_DECK_MK_2": 15,
        #         "STREAM_DECK_MINI": 6
        #     }
        #     if config["model"] in MAX_STREAM_DECK_MODEL_KEYS:
        #         self.model = config["model"]
        #         self.numkeys = MAX_STREAM_DECK_MODEL_KEYS[config["model"]]
        #         logger.info(f"__init__: stream deck {self.name} model {config['model']} has {self.numkeys} keys")
        #     else:
        #         self.valid = False
        #         logger.error(f"__init__: stream deck has invalid model {config['model']}, cannot use")
        else:
            self.valid = False
            logger.error(f"__init__: cannot determine key count")

        self.brightness = 100
        if "brightness" in config:
            self.brightness = int(config["brightness"])
            if self.device is not None:
                self.device.set_brightness(self.brightness)

        if self.device is not None:
            self.device.set_poll_frequency(POLL_FREQ)

        self.layout = None
        if "layout" in config:
            self.layout = config["layout"]  # config["layout"] may be None to choose no layout
        else:
            self.layout = DEFAULT_LAYOUT
            logger.warning(f"__init__: stream deck has no layout, using default")

        # Add default icon for this deck
        self.icons[self.default_icon_name] = PILHelper.create_image(deck=self.device, background=self.default_icon_color)
        logging.debug(f"__init__: create default {self.default_icon_name} icon")

        if self.valid:
            self.make_icon_for_device()
            self.load()
            self.init()
            self.start()

    def init(self):
        """
        Connects to device and send initial keys.
        """
        if self.home_page is not None:
            self.change_page(self.home_page.name)
        logger.info(f"init: stream deck {self.name} initialized")

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
            logger.warning(f"load: stream deck has no layout folder '{self.layout}', loading default page")
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
                                idx = int(a["index"])
                            else:
                                logger.error(f"load: page {name}: button {a} has no index, ignoring")
                                continue

                            if idx >= self.numkeys:
                                logger.error(f"load: page {name}: button {a} has index out of range of Stream Deck Device (maxkeys={self.numkeys}), ignoring")
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
            logger.info(f"load: deck {self.name} init page {self.home_page.name}")

    def load_default_page(self):
        # Generates an image that is correctly sized to fit across all keys of a given
        #
        # The following two helper functions are stolen from streamdeck example scripts (tiled_image)
        def create_full_deck_sized_image(deck, key_spacing, image_filename):
            key_rows, key_cols = deck.key_layout()
            key_width, key_height = deck.key_image_format()['size']
            spacing_x, spacing_y = key_spacing

            # Compute total size of the full StreamDeck image, based on the number of
            # buttons along each axis. This doesn't take into account the spaces between
            # the buttons that are hidden by the bezel.
            key_width *= key_cols
            key_height *= key_rows

            # Compute the total number of extra non-visible pixels that are obscured by
            # the bezel of the StreamDeck.
            spacing_x *= key_cols - 1
            spacing_y *= key_rows - 1

            # Compute final full deck image size, based on the number of buttons and
            # obscured pixels.
            full_deck_image_size = (key_width + spacing_x, key_height + spacing_y)

            # Resize the image to suit the StreamDeck's full image size. We use the
            # helper function in Pillow's ImageOps module so that the image's aspect
            # ratio is preserved.
            image = None
            if os.path.exists(image_filename):
                image = Image.open(image_filename).convert("RGBA")
            else:
                logger.warning(f"load_default_page: deck {self.name}: no wallpaper image {image_filename} found, using default")
                image = Image.new(mode="RGBA", size=(2000, 2000), color=self.default_icon_color)
                fn = os.path.join(os.path.dirname(__file__), RESOURCES_FOLDER, self.logo)
                if os.path.exists(fn):
                    logo = Image.open(fn).convert("RGBA")
                    image.paste(logo, (500, 500), logo)
                else:
                    logger.warning(f"load_default_page: deck {self.name}: no logo image {fn} found, using default")

            image = ImageOps.fit(image, full_deck_image_size, Image.LANCZOS)
            return image


        # Crops out a key-sized image from a larger deck-sized image, at the location
        # occupied by the given key index.
        def crop_key_image_from_deck_sized_image(deck, image, key_spacing, key):
            key_rows, key_cols = deck.key_layout()
            key_width, key_height = deck.key_image_format()['size']
            spacing_x, spacing_y = key_spacing

            # Determine which row and column the requested key is located on.
            row = key // key_cols
            col = key % key_cols

            # Compute the starting X and Y offsets into the full size image that the
            # requested key should display.
            start_x = col * (key_width + spacing_x)
            start_y = row * (key_height + spacing_y)

            # Compute the region of the larger deck image that is occupied by the given
            # key, and crop out that segment of the full image.
            region = (start_x, start_y, start_x + key_width, start_y + key_height)
            segment = image.crop(region)

            # Create a new key-sized image, and paste in the cropped section of the
            # larger image.
            key_image = PILHelper.create_image(deck)
            key_image.paste(segment)

            return PILHelper.to_native_format(deck, key_image)

        fn = os.path.join(os.path.dirname(__file__), RESOURCES_FOLDER, self.wallpaper)
        key_spacing = (36, 36)
        image = create_full_deck_sized_image(self.device, key_spacing, fn)
        key_images = dict()
        for k in range(self.device.key_count()):
            key_images[k] = crop_key_image_from_deck_sized_image(self.device, image, key_spacing, k)

        with self.device:
            # Draw the individual key images to each of the keys.
            for k in range(self.device.key_count()):
                key_image = key_images[k]
                # Show the section of the main image onto the key.
                self.device.set_key_image(k, key_image)

        # Add index 0 only button:
        page0 = Page(name=DEFAULT_PAGE_NAME, deck=self)
        button0 = BUTTON_TYPES["push"].new(config={
                                                "index": 0,
                                                "name": "X-Plane Map",
                                                "type": "push",
                                                "command": "sim/map/show_current",
                                                "label": "Map",
                                                "icon": self.default_icon_name
                                            }, page=page0)
        page0.add_button(0, button0)
        self.pages = { DEFAULT_PAGE_NAME: page0 }
        self.home_page = None
        self.current_page = page0
        self.device.set_poll_frequency(hz=POLL_FREQ)  # default is 20
        self.device.set_key_callback(self.key_change_callback)
        self.running = True

    def key_change_callback(self, deck, key, state):
        """
        This is the function that is called when a key is pressed.
        """
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
        We could build a set per Stream Deck model rather than stream deck instance...
        """
        if self.device is not None:
            for k, v in self.decks.icons.items():
                self.icons[k] = PILHelper.create_scaled_image(self.device, v, margins=[0, 0, 0, 0])
            logger.info(f"make_icon_for_device: deck {self.name} icons ready")
        else:
            logger.warning(f"make_icon_for_device: deck {self.name} has no device")

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
            self.decks.xp.set_datarefs(self.current_page.datarefs)  # set which datarefs to monitor
            self.current_page.render()
            logger.debug(f"change_page: deck {self.name} ..done")
        else:
            logger.warning(f"change_page: deck {self.name}: page {page} not found")


    def start(self):
        if self.device is not None:
            self.device.set_poll_frequency(hz=POLL_FREQ)  # default is 20
            self.device.set_key_callback(self.key_change_callback)
        logger.info(f"start: deck {self.name} listening for key strokes")


    def set_key_image(self, button: Button): # idx: int, image: str, label: str = None):
        if self.device is None:
            logger.warning("set_key_image: no device")
            return
        image = button.get_image()
        if image is None:
            logger.warning("set_key_image: button returned no image, using default")
            image = self.icons[self.default_icon_name]

        with self.device:
            i = PILHelper.to_native_format(self.device, image)
            self.device.set_key_image(button.index, i)

    def terminate(self):
        with self.device:
            self.device.set_key_callback(None)
            self.device.reset()
            self.device.close()  # terminates the loop.
            self.running = False
        logger.info(f"terminate: deck {self.name} terminated")
