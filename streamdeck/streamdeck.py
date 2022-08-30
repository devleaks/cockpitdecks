import os
import logging
import yaml

from enum import Enum

from PIL import Image, ImageDraw, ImageFont
from StreamDeck.ImageHelpers import PILHelper

from .constant import DEFAULT_LAYOUT, CONFIG_DIR, INIT_PAGE, DEFAULT_LABEL_FONT
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

    def init(self):
        """
        Connects to device and send initial keys.
        """
        self.change_page(self.home_page)
        logger.info(f"init: stream deck {self.name} initialized")


    def load(self):
        """
        Loads Streamdeck pages during configuration
        """
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

                        if not "actions" in pc:
                            logger.error(f"load: {fn} has no action")
                            continue

                        if "name" in pc:
                            name = pc["name"]

                        this_page = Page(name)
                        self.pages[name] = this_page

                        for a in pc["actions"]:
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

    def make_icon_for_device(self):
        if self.device is not None:
            for k, v in self.decks.icons.items():
                self.icons[k] = PILHelper.create_scaled_image(self.device, v, margins=[0, 0, 0, 0])
            logger.info(f"make_icon_for_device: deck {self.name} icons ready")
        else:
            logger.warning(f"make_icon_for_device: deck {self.name} has no device")


    def change_page(self, page: Page):
        self.previous_page = self.current_page
        self.current_page = page
        self.update(force=True)

    def update(self, force: bool = False):
        self.current_page.update(force)

    def button_pressed(self, idx: int):
        if idx >= 0 and idx < self.numkeys and idx:
            self.current_page.activate(idx)

    def set_key_image(self, button: Button): # idx: int, image: str, label: str = None):
        if self.device is None:
            logger.warning("set_key_image: no device")
            return

        if button.icon not in self.icons.keys():
            logger.warning(f"set_key_image: no icon {button.icon} for button {button.name}")
            return

        image = self.icons[button.icon]

        # if button.label is not None:  # overlay label on top of image
        #     font_file_name = DEFAULT_LABEL_FONT
        #     if self.decks.default_font in self.decks.fonts.keys():
        #         font_file_name = self.decks.fonts[self.decks.default_font]
        #     print(">>>>>>>>>>>>>>>", font_file_name, self.decks.default_font, self.decks.fonts.keys())
        #     draw = ImageDraw.Draw(image)
        #     font = ImageFont.truetype(font_file_name, self.decks.default_size)
        #     draw.text((image.width / 2, image.height - 5), text=button.label, font=font, anchor="ms", fill="white")

        with self.device:
            i = PILHelper.to_native_format(self.device, image)
            self.device.set_key_image(button.index, i)
