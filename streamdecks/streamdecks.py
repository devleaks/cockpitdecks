import os
import threading
import yaml
import logging

from PIL import Image, ImageDraw, ImageFont
from StreamDeck.DeviceManager import DeviceManager

from .constant import CONFIG_DIR, CONFIG_FILE, EXCLUDE_DECKS, ICONS_FOLDER, FONTS_FOLDER, RESOURCES_FOLDER
from .constant import DEFAULT_ICON_NAME, DEFAULT_ICON_COLOR, DEFAULT_LOGO, DEFAULT_WALLPAPER
from .constant import DEFAULT_SYSTEM_FONT, DEFAULT_LABEL_FONT, DEFAULT_LABEL_SIZE, DEFAULT_LABEL_COLOR
from .constant import has_ext, convert_color

from .streamdeck import Streamdeck

logger = logging.getLogger("Streamdecks")

#

class Streamdecks:
    """
    Contains all stream deck configurations for a given aircraft.
    Is started when aicraft is loaded and aircraft contains CONFIG_DIR folder.
    """
    FLIP_DESCRIPTION = {
        (False, False): "not mirrored",
        (True, False): "mirrored horizontally",
        (False, True): "mirrored vertically",
        (True, True): "mirrored horizontally/vertically"
    }

    def __init__(self, pi, xp):
        self.pi = pi
        self.xp = xp(self)

        self.disabled = False
        self.default_pages = None  # for debugging

        self.devices = []

        self.acpath = None
        self.decks = {}

        self.default_logo = DEFAULT_LOGO
        self.default_wallpaper = DEFAULT_WALLPAPER

        self.fonts = {}
        self.default_label_font = DEFAULT_LABEL_FONT
        self.default_label_size = DEFAULT_LABEL_SIZE
        self.default_label_color = convert_color(DEFAULT_LABEL_COLOR)

        self.icons = {}
        self.default_icon_name = DEFAULT_ICON_NAME
        self.default_icon_color = DEFAULT_ICON_COLOR

        self.init()

    def init(self):
        """
        Loads all Stream Deck devices connected to this computer.
        """
        self.devices = DeviceManager().enumerate()
        logger.info(f"init: found {len(self.devices)} decks")
        for name, device in enumerate(self.devices):
            device.open()
            serial = device.get_serial_number()
            device.close()
            if serial in EXCLUDE_DECKS:
                logger.warning(f"get_device: deck {serial} excluded")
                del self.devices[name]
        logger.info(f"init: using {len(self.devices)} decks")

    def get_device(self, req_serial: str):
        """
        Get a HIDAPI device for the supplied serial number.
        If found, the device is opened and reset and returned open.

        :param      req_serial:  The request serial
        :type       req_serial:  str
        """
        for name, device in enumerate(self.devices):
            device.open()
            serial = device.get_serial_number()
            if serial == req_serial:
                logger.info(f"get_device: deck {name}: opened {device.deck_type()} device (serial number: {device.get_serial_number()}, fw: {device.get_firmware_version()})")
                logger.debug(f"get_device: deck {name}: {device.key_count()} keys, layout  {device.key_layout()[0]}×{device.key_layout()[1]}")
                if device.is_visual():
                    image_format = device.key_image_format()
                    logger.debug(f"get_device: deck {name}: key images: {image_format['size'][0]}x{image_format['size'][1]} pixels, {image_format['format']} format, rotated {image_format['rotation']} degrees, {Streamdecks.FLIP_DESCRIPTION[image_format['flip']]}")
                else:
                    logger.debug(f"get_device: deck {name}: no visual")
                device.reset()
                return device
        logger.warning(f"get_device: deck {req_serial} not found")
        return None

    def load(self, acpath: str):
        """
        Loads stream decks for aircraft in supplied path and start listening for key presses.
        """
        if self.disabled:
            logging.warning(f"load: Streamdecks is disabled")
            return
        # Reset, if new aircraft
        if len(self.decks) > 0:
            self.terminate_this_aircraft()

        self.decks = {}
        self.icons = {}
        # self.fonts = {}
        self.acpath = None

        self.load_defaults()

        if os.path.exists(os.path.join(acpath, CONFIG_DIR)):
            self.acpath = acpath
            self.load_icons()
            self.load_fonts()
            self.create_decks()
            if self.default_pages is not None:
                logging.debug(f"load: default_pages {self.default_pages.keys()}")
                for name, deck in self.decks.items():
                    if name in self.default_pages.keys():
                        if deck.home_page is not None:  # do not refresh default pages
                            deck.change_page(self.default_pages[name])
                self.default_pages = None
        else:
            logging.error(f"load: no Stream Deck folder '{CONFIG_DIR}' in aircraft folder {acpath}")
            self.create_default_decks()
        self.run()

    def load_defaults(self):
        """
        Loads default values for font, icon, etc. They will be used if no layout is found.
        """
        # 1. Loading/creating default icon
        self.icons[self.default_icon_name] = Image.new(mode="RGBA", size=(256, 256), color=DEFAULT_ICON_COLOR)
        logging.debug(f"load_defaults: create default {self.default_icon_name} icon")

        # 2. Load label default font
        if DEFAULT_LABEL_FONT not in self.fonts.keys():
            try:
                test = ImageFont.truetype(DEFAULT_LABEL_FONT, self.default_label_size)
                self.fonts[DEFAULT_LABEL_FONT] = DEFAULT_LABEL_FONT
                self.default_label_font = DEFAULT_LABEL_FONT
            except:
                logging.warning(f"load_defaults: font {DEFAULT_LABEL_FONT} not loaded")
        else:
            logging.debug(f"load_defaults: font {DEFAULT_LABEL_FONT} already loaded")

        if DEFAULT_LABEL_FONT not in self.fonts.keys():
            fn = None
            try:
                fn = os.path.join(os.path.dirname(__file__), RESOURCES_FOLDER, DEFAULT_LABEL_FONT)
                test = ImageFont.truetype(fn, self.default_label_size)
                self.fonts[DEFAULT_LABEL_FONT] = fn
                self.default_label_font = DEFAULT_LABEL_FONT
                logging.debug(f"load_defaults: font {fn} found locally")
            except:
                logging.warning(f"load_defaults: font {fn} not found locally")

        if self.default_label_font is None and len(self.fonts) > 0:
            if DEFAULT_LABEL_FONT in self.fonts.keys():
                self.default_label_font = DEFAULT_LABEL_FONT
            else:  # select first one
                self.default_label_font = list(self.fonts.keys())[0]

        # If no font loaded, try DEFAULT_SYSTEM_FONT:
        if self.default_label_font is None:  # No found loaded? we need at least one:
            if DEFAULT_SYSTEM_FONT not in self.fonts:
                try:
                    test = ImageFont.truetype(DEFAULT_SYSTEM_FONT, self.default_label_size)
                    self.fonts[DEFAULT_SYSTEM_FONT] = DEFAULT_SYSTEM_FONT
                    self.default_label_font = DEFAULT_LABEL_FONT
                except:
                    logging.error(f"load_defaults: font default {DEFAULT_SYSTEM_FONT} not loaded")
            else:
                logging.debug(f"load_defaults: font {DEFAULT_SYSTEM_FONT} already loaded")

        if self.default_label_font is None:
            logging.error(f"load_defaults: no default font")

        # 3. report summary if debugging
        logging.debug(f"load_defaults: default fonts {self.fonts.keys()}, default={self.default_label_font}")
        logging.debug(f"load_defaults: default icons {self.icons.keys()}, default={self.default_icon_name}")

    def create_decks(self):
        fn = os.path.join(self.acpath, CONFIG_DIR, CONFIG_FILE)
        if os.path.exists(fn):
            with open(fn, "r") as fp:
                config = yaml.safe_load(fp)

                self.default_label_font = config.get("default-label-font", DEFAULT_LABEL_FONT)
                self.default_label_size = config.get("default-label-size", DEFAULT_LABEL_SIZE)
                self.default_label_color = config.get("default-label-color", DEFAULT_LABEL_COLOR)
                self.default_icon_name = DEFAULT_ICON_NAME
                self.default_icon_color = config.get("default-icon-color", DEFAULT_ICON_COLOR)
                self.default_logo = config.get("default-wallpaper-logo", DEFAULT_LOGO)
                self.default_wallpaper = config.get("default-wallpaper", DEFAULT_WALLPAPER)

                if "decks" in config:
                    cnt = 0
                    for d in config["decks"]:
                        name = f"Deck {cnt}"
                        if "serial" in d:
                            serial = d["serial"]
                            device = self.get_device(serial)
                            if device is not None:
                                if "name" in d:
                                    name = d["name"]
                                self.decks[name] = Streamdeck(name, d, self, device)
                                cnt = cnt + 1
                                logging.info(f"load: deck {name} loaded")
                            # else:  # warning shown by get_device
                        else:
                            logging.error(f"load: deck {name} has no serial number, ignoring")
                else:
                    logging.warning(f"load: no deck in file {fn}")
        else:
            logging.warning(f"load: no config file {fn}")

    def create_default_decks(self):
        """
        When no Stream Deck definition is found in the aicraft folder, Streamdecks loads
        a default X-Plane logo on all Stream Deck devices. The only active button is index 0,
        which toggle X-Plane map on/off.
        """
        self.acpath = None
        for device in self.devices:
            device.open()
            device.reset()
            name = device.id()
            config = {
                "name": name,
                "model": device.deck_type(),
                "serial": device.get_serial_number(),
                "layout": None,   # Streamdeck will detect None layout and present default deck
                "brightness": 75  # Note: layout=None is not the same as no layout attribute (attribute missing)
            }
            self.decks[name] = Streamdeck(name, config, self, device)

    def load_icons(self):
        # Loading icons
        #
        dn = os.path.join(self.acpath, CONFIG_DIR, ICONS_FOLDER)
        if os.path.exists(dn):
            icons = os.listdir(dn)
            for i in icons:
                if has_ext(i, "png"):
                    fn = os.path.join(dn, i)
                    image = Image.open(fn)
                    self.icons[i] = image
        logging.info(f"load_icons: {len(self.icons)} icons loaded")

    def load_fonts(self):
        # Loading fonts.
        # For custom fonts (fonts found in the fonts config folder),
        # we supply the full path for font definition to ImageFont.
        # For other fonts, we assume ImageFont will search at OS dependent folders or directories.
        # If the font is not found by ImageFont, we ignore it.
        # So self.icons is a list of properly located usable fonts.
        #
        # 1. Load fonts supplied by the user in the configuration
        dn = os.path.join(self.acpath, CONFIG_DIR, FONTS_FOLDER)
        if os.path.exists(dn):
            fonts = os.listdir(dn)
            for i in fonts:
                if has_ext(i, ".ttf") or has_ext(i, ".otf"):
                    if i not in self.fonts.keys():
                        fn = os.path.join(dn, i)
                        try:
                            test = ImageFont.truetype(fn, self.default_label_size)
                            self.fonts[i] = fn
                        except:
                            logging.warning(f"load_fonts: custom font file {fn} not loaded")
                    else:
                        logging.debug(f"load_fonts: font {i} already loaded")

        # 2. Load label default font
        if DEFAULT_LABEL_FONT not in self.fonts.keys():
            if DEFAULT_LABEL_FONT not in self.fonts.keys():
                try:
                    test = ImageFont.truetype(DEFAULT_LABEL_FONT, self.default_label_size)
                    self.fonts[DEFAULT_LABEL_FONT] = DEFAULT_LABEL_FONT
                    self.default_label_font = DEFAULT_LABEL_FONT
                except:
                    logging.warning(f"load_fonts: font {DEFAULT_LABEL_FONT} not loaded")
            else:
                logging.debug(f"load_fonts: font {DEFAULT_LABEL_FONT} already loaded")

        if self.default_label_font is None and len(self.fonts) > 0:
            if DEFAULT_LABEL_FONT in self.fonts.keys():
                self.default_label_font = DEFAULT_LABEL_FONT
            else:  # select first one
                self.default_label_font = list(self.fonts.keys())[0]

        # 3. If no font loaded, try DEFAULT_SYSTEM_FONT:
        if self.default_label_font is None:  # No found loaded? we need at least one:
            if DEFAULT_SYSTEM_FONT not in self.fonts:
                try:
                    test = ImageFont.truetype(DEFAULT_SYSTEM_FONT, self.default_label_size)
                    self.fonts[DEFAULT_SYSTEM_FONT] = DEFAULT_SYSTEM_FONT
                    self.default_label_font = DEFAULT_LABEL_FONT
                except:
                    logging.error(f"load_fonts: font default {DEFAULT_SYSTEM_FONT} not loaded")
            else:
                logging.debug(f"load_fonts: font {DEFAULT_SYSTEM_FONT} already loaded")

        logging.info(f"load_fonts: {len(self.fonts)} fonts loaded, default is {self.default_label_font}")

    def reload_decks(self):
        """
        Development function to reload page yaml without leaving the page
        Should not be used in production...
        """
        logging.info(f"reload_decks: reloading..")
        self.default_pages = {}
        for name, deck in self.decks.items():
            self.default_pages[name] = deck.current_page.name
        self.load(self.acpath)
        logging.info(f"reload_decks: ..done")

    def terminate_this_aircraft(self):
        logging.info(f"terminate_this_aircraft: terminating..")
        for deck in self.decks.values():
            deck.terminate()
        logging.info(f"terminate_this_aircraft: done")

    def terminate_all(self):
        logging.info(f"terminate_all: terminating..")
        self.terminate_this_aircraft()
        if self.xp is not None:
            self.xp.terminate()
            del self.xp
            self.xp = None
        logging.info(f"terminate_all: done")

    def run(self):
        if len(self.decks) > 0:
            self.xp.start()
            logging.info(f"run: active")
            for t in threading.enumerate():
                try:
                    t.join()
                except RuntimeError:
                    pass
            logging.info(f"run: terminated")
        else:
            logging.warning(f"run: no deck")

    # XPPython Plugin Hooks
    #
    def start(self):
        logger.info(f"start: starting..")
        # do nothing, started in when enabled
        logger.info(f"start: done")

    def stop(self):
        logger.info(f"stop: stopping..")
        self.terminate_all()
        logger.info(f"stop: done")

    def enable(self):
        self.load(self.acpath)
        self.disabled = False
        logger.info(f"enable: enabled")

    def disable(self):
        self.terminate_this_aircraft()
        self.disabled = True
        logger.info(f"disable: disabled")


