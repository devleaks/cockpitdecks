# Main container for all decks
#
import os
import threading
import yaml
import logging
import pickle

from PIL import Image, ImageFont

from .constant import CONFIG_DIR, CONFIG_FILE, SECRET_FILE, EXCLUDE_DECKS, ICONS_FOLDER, FONTS_FOLDER, RESOURCES_FOLDER
from .constant import DEFAULT_ICON_NAME, DEFAULT_ICON_COLOR, DEFAULT_LOGO, DEFAULT_WALLPAPER, ANNUNCIATOR_STYLE, INIT_PAGE
from .constant import DEFAULT_SYSTEM_FONT, DEFAULT_LABEL_FONT, DEFAULT_LABEL_SIZE, DEFAULT_LABEL_COLOR, COCKPIT_COLOR
from .color import convert_color

from .devices import DECK_TYPES
from .streamdeck import FLIP_DESCRIPTION


logger = logging.getLogger("Cockpit")
# logger.setLevel(logging.DEBUG)


def has_ext(name: str, ext: str):
    rext = ext if not ext.startswith(".") else ext[1:]  # remove leading period from extension if any
    narr = name.split(".")
    return (len(narr) > 1) and (narr[-1].lower() == rext.lower())


class Cockpit:
    """
    Contains all stream deck configurations for a given aircraft.
    Is started when aicraft is loaded and aircraft contains CONFIG_DIR folder.
    """
    def __init__(self, xp):
        self.xp = xp(self)
        self._config = None

        self.disabled = False
        self.default_pages = None  # for debugging

        self.devices = []

        self.acpath = None
        self.cockpit = {}  # all decks: { deckname: deck }

        self.default_config = None
        self.default_logo = DEFAULT_LOGO
        self.default_wallpaper = DEFAULT_WALLPAPER

        self.fonts = {}
        self.default_label_font = DEFAULT_LABEL_FONT
        self.default_label_size = DEFAULT_LABEL_SIZE
        self.default_label_color = convert_color(DEFAULT_LABEL_COLOR)

        self.icon_folder = None
        self.icons = {}
        self.default_icon_name = DEFAULT_ICON_NAME
        self.default_icon_color = DEFAULT_ICON_COLOR
        self.fill_empty_keys = True
        self.empty_key_fill_color = None
        self.empty_key_fill_icon = None
        self.annunciator_style = ANNUNCIATOR_STYLE
        self.cockpit_color = COCKPIT_COLOR
        self.default_home_page_name = INIT_PAGE
        self.init()

    def init(self):
        """
        Loads all Stream Deck devices connected to this computer.
        """
        self.scan_devices()


    def inspect(self):
        """
        This function is called on all instances of Deck.
        """
        logger.info("Cockpitdecks -- Statistics")

        logger.info(f"Threads: {[(t.name,t.isDaemon(),t.is_alive()) for t in threading.enumerate()]}")

        # for v in self.cockpit.values():
        #     v.inspect()


    def scan_devices(self):
        for decktype, builder in DECK_TYPES.items():
            decks = builder[1]().enumerate()
            logger.info(f"init: found {len(decks)} {decktype}")
            for name, device in enumerate(decks):
                device.open()
                serial = device.get_serial_number()
                device.close()
                if serial in EXCLUDE_DECKS:
                    logger.warning(f"init: deck {serial} excluded")
                    del decks[name]
                self.devices.append({
                    "type": decktype,
                    "device": device,
                    "serial_number": serial
                })
            logger.info(f"init: using {len(decks)} {decktype}")


    def get_device(self, req_serial: str, req_type: str):
        """
        Get a HIDAPI device for the supplied serial number.
        If found, the device is opened and reset and returned open.

        :param      req_serial:  The request serial
        :type       req_serial:  str
        """
        for deck in self.devices:
            if deck["serial_number"] == req_serial:
                device = deck["device"]
                device.open()
                if device.is_visual():
                    image_format = device.key_image_format()
                    logger.debug(f"get_device: deck {deck['serial_number']}: key images: {image_format['size'][0]}x{image_format['size'][1]} pixels, {image_format['format']} format, rotated {image_format['rotation']} degrees, {FLIP_DESCRIPTION[image_format['flip']] if image_format['flip'] is not None else 'None'}")
                else:
                    logger.debug(f"get_device: deck {deck['serial_number']}: no visual")
                device.reset()
                return device
        logger.warning(f"get_device: deck {req_serial} not found")
        return None

    def load(self, acpath: str):
        """
        Loads decks for aircraft in supplied path and start listening for key presses.
        """
        self.load_aircraft(acpath)
        self.run()

    def load_aircraft(self, acpath: str):
        """
        Loads decks for aircraft in supplied path.
        """
        if self.disabled:
            logger.warning(f"load: Cockpit is disabled")
            return
        # Reset, if new aircraft
        if len(self.cockpit) > 0:
            self.terminate_this_aircraft()

        self.cockpit = {}
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
                logger.debug(f"load: default_pages {self.default_pages.keys()}")
                for name, deck in self.cockpit.items():
                    if name in self.default_pages.keys():
                        if deck.home_page is not None:  # do not refresh default pages
                            deck.change_page(self.default_pages[name])
                self.default_pages = None
        else:
            logger.error(f"load: no Stream Deck folder '{CONFIG_DIR}' in aircraft folder {acpath}")
            self.create_default_decks()

    def load_defaults(self):
        """
        Loads default values for font, icon, etc. They will be used if no layout is found.
        """
        # 0. Some variables defaults?
        fn = os.path.join(os.path.dirname(__file__), RESOURCES_FOLDER, CONFIG_FILE)
        if os.path.exists(fn):
            with open(fn, "r") as fp:
                self.default_config = yaml.safe_load(fp)
                logger.debug(f"load_defaults: loaded default config {fn}")
        if self.default_config is not None:
            self.default_logo = self.default_config.get("default-wallpaper-logo", DEFAULT_LOGO)
            self.default_wallpaper = self.default_config.get("default-wallpaper", DEFAULT_WALLPAPER)
            self.default_label_font = self.default_config.get("default-label-font", DEFAULT_LABEL_FONT)
            self.default_label_size = self.default_config.get("default-label-size", DEFAULT_LABEL_SIZE)
            self.default_label_color = self.default_config.get("default-label-color", convert_color(DEFAULT_LABEL_COLOR))
            self.default_icon_color = self.default_config.get("default-icon-color", convert_color(DEFAULT_ICON_COLOR))
            self.empty_key_fill_color = self.default_config.get("fill-empty-keys")
            self.cockpit_color = self.default_config.get("cockpit-color", COCKPIT_COLOR)
            self.default_home_page_name = self.default_config.get("default-homepage-name", INIT_PAGE)

        # 1. Creating default icon
        self.icons[self.default_icon_name] = Image.new(mode="RGBA", size=(256, 256), color=DEFAULT_ICON_COLOR)
        logger.debug(f"load_defaults: create default {self.default_icon_name} icon")

        # 2. Load label default font
        # 2.1 Try system fonts first
        if DEFAULT_LABEL_FONT not in self.fonts.keys():
            try:
                test = ImageFont.truetype(DEFAULT_LABEL_FONT, self.default_label_size)
                self.fonts[DEFAULT_LABEL_FONT] = DEFAULT_LABEL_FONT
                self.default_label_font = DEFAULT_LABEL_FONT
            except:
                logger.debug(f"load_defaults: font {DEFAULT_LABEL_FONT} not found on computer")
        else:
            logger.debug(f"load_defaults: font {DEFAULT_LABEL_FONT} already loaded")

        # 2.2 Try to load from streamdecks resources folder
        if DEFAULT_LABEL_FONT not in self.fonts.keys():
            fn = None
            try:
                fn = os.path.join(os.path.dirname(__file__), RESOURCES_FOLDER, DEFAULT_LABEL_FONT)
                test = ImageFont.truetype(fn, self.default_label_size)
                self.fonts[DEFAULT_LABEL_FONT] = fn
                self.default_label_font = DEFAULT_LABEL_FONT
                logger.debug(f"load_defaults: font {fn} found locally")
            except:
                logger.warning(f"load_defaults: font {fn} not found locally or on computer")

        # 2.3 Set defaults from what we have so far
        if self.default_label_font is None and len(self.fonts) > 0:
            if DEFAULT_LABEL_FONT in self.fonts.keys():
                self.default_label_font = DEFAULT_LABEL_FONT
            else:  # select first one
                self.default_label_font = list(self.fonts.keys())[0]

        # If we still haven't found a font...
        # 3. ... try to load "system font" from system
        if self.default_label_font is None:  # No found loaded? we need at least one:
            if DEFAULT_SYSTEM_FONT not in self.fonts:
                try:
                    test = ImageFont.truetype(DEFAULT_SYSTEM_FONT, self.default_label_size)
                    self.fonts[DEFAULT_SYSTEM_FONT] = DEFAULT_SYSTEM_FONT
                    self.default_label_font = DEFAULT_LABEL_FONT
                except:
                    logger.error(f"load_defaults: font default {DEFAULT_SYSTEM_FONT} not loaded")
            else:
                logger.debug(f"load_defaults: font {DEFAULT_SYSTEM_FONT} already loaded")

        if self.default_label_font is None:
            logger.error(f"load_defaults: no default font")

        # 4. report summary if debugging
        logger.debug(f"load_defaults: default fonts {self.fonts.keys()}, default={self.default_label_font}")
        logger.debug(f"load_defaults: default icons {self.icons.keys()}, default={self.default_icon_name}")

    def create_decks(self):
        fn = os.path.join(self.acpath, CONFIG_DIR, CONFIG_FILE)
        sn = os.path.join(self.acpath, CONFIG_DIR, SECRET_FILE)
        serial_numbers = {}
        if os.path.exists(sn):
            with open(sn, "r") as fp:
                serial_numbers = yaml.safe_load(fp)

        if os.path.exists(fn):
            with open(fn, "r") as fp:
                config = yaml.safe_load(fp)
                logger.debug(f"create_decks: loaded config {fn}")

                self._config = config
                self.default_label_font = config.get("default-label-font", DEFAULT_LABEL_FONT)
                self.default_label_size = config.get("default-label-size", DEFAULT_LABEL_SIZE)
                self.default_label_color = config.get("default-label-color", DEFAULT_LABEL_COLOR)
                self.default_icon_name = DEFAULT_ICON_NAME
                self.default_icon_color = config.get("default-icon-color", DEFAULT_ICON_COLOR)
                self.default_logo = config.get("default-wallpaper-logo", DEFAULT_LOGO)
                self.default_wallpaper = config.get("default-wallpaper", DEFAULT_WALLPAPER)
                self.empty_key_fill_color = config.get("fill-empty-keys")
                self.cockpit_color = config.get("cockpit-color", COCKPIT_COLOR)

                if "decks" in config:
                    cnt = 0
                    for deck_config in config["decks"]:
                        name = deck_config.get("name", f"Deck {cnt}")

                        disabled = deck_config.get("disabled")
                        if type(disabled) == str and disabled.upper() in ["YES", "TRUE"] or disabled:
                            logger.info(f"create_decks: deck {name} disabled, ignoring")
                            continue

                        decktype = deck_config.get("type")
                        if decktype not in DECK_TYPES.keys():
                            logger.warning(f"create_decks: invalid deck type {decktype}, ignoring")
                            continue

                        serial = deck_config.get("serial")
                        if serial is None:  # get it from the secret file
                            serial = serial_numbers[name] if name in serial_numbers.keys() else None

                        if serial is not None:
                            device = self.get_device(req_serial=serial, req_type=decktype)
                            if device is not None:
                                #
                                deck_config["serial"] = serial
                                if name not in self.cockpit.keys():
                                    self.cockpit[name] = DECK_TYPES[decktype][0](name=name, config=deck_config, cockpit=self, device=device)
                                    cnt = cnt + 1
                                    logger.info(f"load: deck {decktype} {name} added")
                                else:
                                    logger.warning(f"create_decks: deck {name} already exist, ignoring")
                        else:
                            logger.error(f"load: deck {decktype} {name} has no serial number, ignoring")
                else:
                    logger.warning(f"load: no deck in file {fn}")
        else:
            logger.warning(f"load: no config file {fn}")

    def create_default_decks(self):
        """
        When no deck definition is found in the aicraft folder, Cockpit loads
        a default X-Plane logo on all deck devices. The only active button is index 0,
        which toggle X-Plane map on/off.
        """
        self.acpath = None

        # {
        #     "type": decktype,
        #     "device": device,
        #     "serial_number": serial
        # }
        for deck in self.devices:
            decktype = deck.get("type")
            if decktype not in DECK_TYPES.keys():
                logger.warning(f"create_decks: invalid deck type {decktype}, ignoring")
                continue
            device = deck["device"]
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
            self.cockpit[name] = DECK_TYPES[decktype][0](name, config, self, device)

    # #########################################################
    # Cockpit data caches
    #
    def load_icons(self):
        # Loading icons
        #
        dn = os.path.join(self.acpath, CONFIG_DIR, ICONS_FOLDER)
        if os.path.exists(dn):
            self.icon_folder = dn
            cache = os.path.join(dn, "_icon_cache.pickle")
            if os.path.exists(cache):
                with open(cache, "rb") as fp:
                    self.icons = pickle.load(fp)
                logger.info(f"load_icons: {len(self.icons)} icons loaded from cache")
            else:
                icons = os.listdir(dn)
                for i in icons:
                    if has_ext(i, "png"):  # later, might load JPG as well.
                        fn = os.path.join(dn, i)
                        image = Image.open(fn)
                        self.icons[i] = image
                with open(cache, "wb") as fp:
                    pickle.dump(self.icons, fp)
                logger.info(f"load_icons: {len(self.icons)} icons loaded")

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
                            logger.warning(f"load_fonts: custom font file {fn} not loaded")
                    else:
                        logger.debug(f"load_fonts: font {i} already loaded")

        # 2. Load label default font
        if DEFAULT_LABEL_FONT not in self.fonts.keys():
            if DEFAULT_LABEL_FONT not in self.fonts.keys():
                try:
                    test = ImageFont.truetype(DEFAULT_LABEL_FONT, self.default_label_size)
                    self.fonts[DEFAULT_LABEL_FONT] = DEFAULT_LABEL_FONT
                    self.default_label_font = DEFAULT_LABEL_FONT
                except:
                    logger.warning(f"load_fonts: font {DEFAULT_LABEL_FONT} not loaded")
            else:
                logger.debug(f"load_fonts: font {DEFAULT_LABEL_FONT} already loaded")

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
                    logger.error(f"load_fonts: font default {DEFAULT_SYSTEM_FONT} not loaded")
            else:
                logger.debug(f"load_fonts: font {DEFAULT_SYSTEM_FONT} already loaded")

        logger.info(f"load_fonts: {len(self.fonts)} fonts loaded, default is {self.default_label_font}")

    # #########################################################
    # Cockpit start/stop/reload procedures
    #
    def reload_decks(self):
        """
        Development function to reload page yaml without leaving the page
        Should not be used in production...
        """
        logger.info(f"reload_decks: reloading..")
        self.default_pages = {}  # {deck_name: currently_loaded_page_name}
        for name, deck in self.cockpit.items():
            self.default_pages[name] = deck.current_page.name
        self.load_aircraft(self.acpath)  # will terminate it before loading again
        logger.info(f"reload_decks: ..done")

    def terminate_this_aircraft(self):
        logger.info(f"terminate_this_aircraft: terminating..")
        for deck in self.cockpit.values():
            deck.terminate()
        if not self.xp.use_flight_loop:
            logger.info(f"terminate_this_aircraft: {len(threading.enumerate())} threads")
            logger.info(f"terminate_this_aircraft: {[t.name for t in threading.enumerate()]}")
        logger.info(f"terminate_this_aircraft: ..done")

    def start_this_aircraft(self):
        logger.info(f"start_this_aircraft: starting..")
        for deck in self.cockpit.values():
            deck.start()
        if not self.xp.use_flight_loop:
            logger.info(f"start_this_aircraft: {len(threading.enumerate())} threads")
            logger.info(f"start_this_aircraft: {[t.name for t in threading.enumerate()]}")
        logger.info(f"start_this_aircraft: ..done")

    def terminate_all(self):
        logger.info(f"terminate_all: terminating..")
        self.terminate_this_aircraft()
        if self.xp is not None:
            self.xp.terminate()
            del self.xp
            self.xp = None
            logger.info(f"terminate_all: ..xp deleted..")
        logger.info(f"terminate_all: ..done")
        left = len(threading.enumerate())
        if left > 1:  # [MainThread]
            logger.error(f"terminate_all: {left} threads remaining")
            logger.error(f"terminate_all: {[t.name for t in threading.enumerate()]}")

    def run(self):
        if len(self.cockpit) > 0:
            self.xp.start()
            logger.info(f"run: active")
            if not self.xp.use_flight_loop:
                logger.info(f"run: {len(threading.enumerate())} threads")
                logger.info(f"run: {[t.name for t in threading.enumerate()]}")
                for t in threading.enumerate():
                    try:
                        t.join()
                    except RuntimeError:
                        pass
                logger.info(f"run: terminated")
        else:
            logger.warning(f"run: no deck")

    # #########################################################
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

