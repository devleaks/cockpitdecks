import os
import logging
import yaml
import threading

from time import sleep

from enum import Enum

from PIL import Image, ImageDraw, ImageFont, ImageOps
from StreamDeck.ImageHelpers import PILHelper

from .constant import DEFAULT_LAYOUT, CONFIG_DIR, INIT_PAGE, DEFAULT_LABEL_FONT, WALLPAPER, MONITORING_POLL
from .button import Button, BUTTON_TYPES

logger = logging.getLogger("Streamdeck")
loggerPage = logging.getLogger("Page")


class Page:
    """
    A Page is a collection of buttons.
    """

    def __init__(self, name: str):
        self.name = name
        self.buttons = {}

    def add_button(self, idx: int, button: Button):
        if idx in self.buttons.keys():
            loggerPage.error(f"add_button: button index {idx} already defined, ignoring {button.name}")
            return
        self.buttons[idx] = button
        loggerPage.debug(f"add_button: page {self.name}: button {button.name} {idx} added")

    def update(self, force: bool = False):
        for button in self.buttons.values():
            button.update(force)

    def activate(self, idx: int):
        if idx in self.buttons.keys():
            self.buttons[idx].activate()
        else:
            loggerPage.error(f"activate: page {self.name}: invalid button index {idx}")


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
        self.home_page = None
        self.current_page = None
        self.previous_page = None
        self.valid = True
        self.running = False
        self.monitoring_thread = None

        if "serial" in config:
            self.serial = config["serial"]
        else:
            self.valid = False
            logger.error(f"__init__: stream deck has no serial number, cannot use")


        if device is not None:
            self.numkeys = device.key_count()
            logger.info(f"__init__: stream deck {self.name} has {self.numkeys} keys")
        elif "model" in config:
            MAX_STREAM_DECK_MODEL_KEYS = {
                "STREAM_DECK_XL": 32,
                "STREAM_DECK": 15,
                "STREAM_DECK_MK_2": 15,
                "STREAM_DECK_MINI": 6
            }
            if config["model"] in MAX_STREAM_DECK_MODEL_KEYS:
                self.model = config["model"]
                self.numkeys = MAX_STREAM_DECK_MODEL_KEYS[config["model"]]
                logger.info(f"__init__: stream deck {self.name} model {config['model']} has {self.numkeys} keys")
            else:
                self.valid = False
                logger.error(f"__init__: stream deck has invalid model {config['model']}, cannot use")
        else:
            self.valid = False
            logger.error(f"__init__: stream deck has no model, cannot use")

        self.brightness = 100
        if "brightness" in config:
            self.brightness = int(config["brightness"])
            if self.device is not None:
                self.device.set_brightness(30)

        if self.device is not None:
            self.device.set_poll_frequency(10)

        self.layout = None
        if "layout" in config:
            self.layout = config["layout"]
        else:
            self.layout = DEFAULT_LAYOUT
            logger.warning(f"__init__: stream deck has no layout, using default")

        if self.valid:
            self.make_icon_for_device()
            self.load()
            self.init()
            self.start()

    def init(self):
        """
        Connects to device and send initial keys.
        """
        self.change_page(self.home_page.name)
        logger.info(f"init: stream deck {self.name} initialized")


    def load(self):
        """
        Loads Streamdeck pages during configuration
        """
        BUTTONS = "buttons"
        if self.layout is None:
            self.load_default_page()
            return

        dn = os.path.join(self.decks.acpath, CONFIG_DIR, self.layout)
        if not os.path.exists(dn):
            self.valid = False
            logger.error(f"__init__: stream deck has no layout folder {self.layout}, cannot load")
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

                        this_page = Page(name)
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
                                button = BUTTON_TYPES[bty].new(config=a, deck=self)
                                this_page.add_button(idx, button)
                            else:
                                logger.error(f"load: page {name}: button {a} invalid button type {bty}, ignoring")

                        logger.info(f"load: page {name} added (from file {fn})")
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
            image = Image.open(image_filename).convert("RGBA")
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

        fn = os.path.join(os.path.dirname(__file__), WALLPAPER)
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
        DEFAULT_PAGE_NAME = "X-Plane"
        this_page = Page(DEFAULT_PAGE_NAME)
        button0 = BUTTON_TYPES["single"].new(config={ "index": 0,
                                                      "name": "X-Plane Map",
                                                      "type": "single",
                                                      "command": "sim/map/show_current",
                                                      "label": "Map",
                                                      "icon": "icon.png"
                                                    }, deck=self)
        this_page.add_button(0, button0)
        self.pages = { DEFAULT_PAGE_NAME: this_page }
        self.home_page = self.pages[DEFAULT_PAGE_NAME]
        self.device.set_key_callback(self.key_change_callback)
        self.running = True

    def key_change_callback(self, deck, key, state):
        """
        This is the function that is called when a key is pressed.
        """
        logger.debug(f"key_change_callback: Deck {deck.id()} Key {key} = {state}")
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
        if page in self.pages.keys():
            self.previous_page = self.current_page
            self.current_page = self.pages[page]
            self.update(force=True)
            logger.debug(f"change_page: deck {self.name} ..done")
        else:
            logger.warning(f"change_page: deck {self.name}: page {page} not found")

    def update(self, force: bool = False):
        logger.debug(f"change_page: deck {self.name} update to page {self.current_page.name}")
        self.current_page.update(force)

    def start(self):
        if self.device is not None:
            self.device.set_key_callback(self.key_change_callback)
            self.running = True
            self.monitoring_thread = threading.Thread(target=self.monitor)
            self.monitoring_thread.start()

        logger.info(f"start: deck {self.name} listening for key strokes")

    def monitor(self):
        """
        Function submitted as a thread to monitor button data changes in the simulator
        """
        logger.info(f"monitor: deck {self.name} started")
        while self.running:
            self.update()
            sleep(MONITORING_POLL)
            logger.debug(f"monitor: deck {self.name} updated")
        logger.info(f"monitor: deck {self.name} terminated")

    def set_key_image(self, button: Button): # idx: int, image: str, label: str = None):
        if self.device is None:
            logger.warning("set_key_image: no device")
            return
        image = button.get_image()

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
