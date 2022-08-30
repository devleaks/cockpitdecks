import os
import yaml
import logging

from PIL import Image, ImageDraw, ImageFont
from StreamDeck.DeviceManager import DeviceManager

from .constant import CONFIG_DIR, CONFIG_FILE, ICONS_FOLDER, FONTS_FOLDER, DEFAULT_LABEL_FONT, DEFAULT_LABEL_SIZE
from .streamdeck import Streamdeck

logger = logging.getLogger("Streamdecks")


class Streamdecks:
    """
    Contains all streamdecks configurations for a given aircraft.
    Is reset when aicraft changes.
    """
    def __init__(self):
        self.devices = []
        self.loop_running = False

        self.acpath = None
        self.decks = {}
        self.icons = {}
        self.fonts = {}

        self.default_font = None
        self.default_size = 12

        self.init()

    def init(self):
        self.devices = DeviceManager().enumerate()
        logger.info(f"init: found {len(self.devices)} decks")

    def get_deck(self, req_serial: str):
        for name, deck in enumerate(self.devices):
            deck.open()
            deck.reset()
            serial = deck.get_serial_number()
            if serial == req_serial:
                logger.info(f"get_deck: opened {deck.deck_type()} device (serial number: {deck.get_serial_number()}, fw: {deck.get_firmware_version()})")
                logger.info(f"get_deck: deck {name}, {deck.key_count()} keys")
                return deck
        logger.warning(f"get_deck: deck {req_serial} not found")
        return None

    def load(self, acpath: str):
        """
        Loads stream decks for aircraft in supplied path
        """
        self.stop_loop()

        # Reset, if new aircraft
        self.decks = {}
        self.icons = {}
        self.fonts = {}
        self.acpath = None

        if os.path.exists(os.path.join(acpath, CONFIG_DIR)):
            self.acpath = acpath
            self.load_icons()
            self.load_fonts()
            self.create_decks()
            self.start_loop()
        else:
            logging.error(f"load: not Stream Deck folder '{CONFIG_DIR}'' in aircraft folder")

    def create_decks(self):
        fn = os.path.join(self.acpath, CONFIG_DIR, CONFIG_FILE)
        if os.path.exists(fn):
            with open(fn, "r") as fp:
                config = yaml.safe_load(fp)

                self.default_font = config.get("default-label-font", DEFAULT_LABEL_FONT)
                self.default_size = config.get("default-label-size", DEFAULT_LABEL_SIZE)

                if "decks" in config:
                    cnt = 0
                    for d in config["decks"]:
                        name = f"Deck {cnt}"
                        if "serial" in d:
                            serial = d["serial"]
                            device = self.get_deck(serial)
                            if "name" in d:
                                name = d["name"]
                            self.decks[name] = Streamdeck(name, d, self, device)
                            cnt = cnt + 1
                            logging.info(f"load: deck {name} loaded")
                        else:
                            logging.error(f"load: deck {name} has no serial number, ignoring")
                else:
                    logging.warning(f"load: no deck in config file {fn}")
        else:
            logging.warning(f"load: no config file {fn}")


    def load_icons(self):
        # Loading icons
        #
        dn = os.path.join(self.acpath, CONFIG_DIR, ICONS_FOLDER)
        if os.path.exists(dn):
            icons = os.listdir(dn)
            for i in icons:
                if i.endswith(".png") or i.endswith(".PNG"):
                    fn = os.path.join(dn, i)
                    self.icons[i] = Image.open(fn)

                # # Load a custom TrueType font and use it to overlay the key index, draw key
                # # label onto the image a few pixels from the bottom of the key.
                # draw = ImageDraw.Draw(image)

                # global DEFAULT_FONT
                # if label_text:
                #     if only_uppercase and not label_text.isupper():
                #         print("WARN: label {} is not upper case only, "
                #               "converting to upper (to disable this check out 'config.yaml'".format(label_text))
                #         label_text = label_text.upper()
                #     draw.text((image.width / 2, image.height - 8), text=label_text, font=DEFAULT_FONT, anchor="ms", fill="white")
        logging.info(f"load: {len(self.icons)} icons loaded")

    def load_fonts(self):
        # Loading fonts
        #
        dn = os.path.join(self.acpath, CONFIG_DIR, FONTS_FOLDER)
        if os.path.exists(dn):
            fonts = os.listdir(dn)
            for i in fonts:
                if i.endswith(".ttf") or i.endswith(".otf"):
                    self.fonts[i] = os.path.join(dn, i)
        logging.info(f"load: {len(self.fonts)} fonts loaded")

    def loop(self):
        for deck in self.decks:
            deck.update()

    def start_loop(self):
        self.loop_running = True
        logging.info(f"start_loop: started")

    def stop_loop(self):
        self.loop_running = False
        logging.info(f"stop_loop: stopped")
