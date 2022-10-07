# Elgato Streamdeck deck
#
import os
import logging
import yaml
import threading
import pickle

from time import sleep

from enum import Enum

from PIL import Image, ImageFont, ImageOps
from StreamDeck.ImageHelpers import PILHelper

from .constant import CONFIG_DIR, RESOURCES_FOLDER, INIT_PAGE, DEFAULT_LAYOUT
from .constant import convert_color
from .button import Button, STREAM_DECK_BUTTON_TYPES
from .page import Page
from .deck import Deck

logger = logging.getLogger("Streamdeck")
logger.setLevel(logging.INFO)

DEFAULT_PAGE_NAME = "X-Plane"
POLL_FREQ = 5  # default is 20
FLIP_DESCRIPTION = {
    (False, False): "not mirrored",
    (True, False): "mirrored horizontally",
    (False, True): "mirrored vertically",
    (True, True): "mirrored horizontally/vertically"
}

class Streamdeck(Deck):
    """
    Loads the configuration of a Stream Deck.
    A Streamdeck has a collection of Pages, and knows which one is currently being displayed.
    """

    def __init__(self, name: str, config: dict, cockpit: "Cockpit", device = None):

        Deck.__init__(self, name=name, config=config, cockpit=cockpit, device=device)

        self.pil_helper = PILHelper

        self.monitoring_thread = None
        self.valid = True

        if self.device is not None:
            self.device.set_poll_frequency(POLL_FREQ)

        if self.valid:
            self.make_default_icon()
            self.make_icon_for_device()
            self.load()
            self.init()
            self.start()

    def load(self):
        """
        Loads Streamdeck pages during configuration
        """
        YAML_BUTTONS_KW = "buttons"  # keywork in yaml file
        if self.layout is None:
            self.load_default_page()
            return

        dn = os.path.join(self.cockpit.acpath, CONFIG_DIR, self.layout)
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
                        page_config = yaml.safe_load(fp)

                        if not YAML_BUTTONS_KW in page_config:
                            logger.error(f"load: {fn} has no action")
                            continue

                        if "name" in page_config:
                            name = page_config["name"]

                        this_page = Page(name, page_config, self)

                        this_page.fill_empty = page_config["fill-empty-keys"] if "fill-empty-keys" in page_config else self.fill_empty
                        self.pages[name] = this_page

                        for a in page_config[YAML_BUTTONS_KW]:
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

                            if bty in STREAM_DECK_BUTTON_TYPES.keys():
                                button = STREAM_DECK_BUTTON_TYPES[bty].new(config=a, page=this_page)
                                this_page.add_button(idx, button)
                            else:
                                logger.error(f"load: page {name}: button {a} invalid button type {bty}, ignoring")

                        logger.info(f"load: page {name} added (from file {fn.replace(self.cockpit.acpath, '... ')})")
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
        page_config = {
            "name": DEFAULT_PAGE_NAME
        }
        page0 = Page(name=DEFAULT_PAGE_NAME, config=page_config, deck=self)
        button0 = STREAM_DECK_BUTTON_TYPES["push"].new(config={
                                                "index": 0,
                                                "name": "X-Plane Map",
                                                "type": "push",
                                                "command": "sim/map/show_current",
                                                "label": "Map",
                                                "icon": self.default_icon_name
                                            }, page=page0)
        page0.add_button(button0.index, button0)
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
        if key in self.current_page.buttons.keys():
            self.current_page.buttons[key].activate(state)

    def create_icon_for_key(self, button, colors):
        return self.pil_helper.create_image(deck=self.device, background=colors)

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
