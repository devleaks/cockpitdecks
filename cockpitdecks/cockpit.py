# Main container for all decks
#
import os
import glob
import threading
import logging
import pickle
from queue import Queue
import pkg_resources

from PIL import Image, ImageFont

from cockpitdecks import __version__, LOGFILE, FORMAT
from cockpitdecks import ID_SEP, SPAM, SPAM_LEVEL, ROOT_DEBUG
from cockpitdecks import CONFIG_FOLDER, CONFIG_FILE, SECRET_FILE, EXCLUDE_DECKS, ICONS_FOLDER, FONTS_FOLDER, RESOURCES_FOLDER
from cockpitdecks import DEFAULT_SYSTEM_FONT, DEFAULT_LABEL_FONT, DEFAULT_LABEL_SIZE, DEFAULT_LABEL_COLOR, DEFAULT_LABEL_POSITION
from cockpitdecks import DEFAULT_ICON_NAME, DEFAULT_ICON_COLOR, DEFAULT_ICON_TEXTURE, DEFAULT_LOGO, DEFAULT_WALLPAPER
from cockpitdecks import DEFAULT_ANNUNCIATOR_COLOR, ANNUNCIATOR_STYLES, DEFAULT_ANNUNCIATOR_STYLE, HOME_PAGE
from cockpitdecks import COCKPIT_COLOR, COCKPIT_TEXTURE
from cockpitdecks import Config
from cockpitdecks.deck import DECKS_FOLDER
from cockpitdecks.resources.color import convert_color, has_ext
from cockpitdecks.simulator import DatarefListener
from cockpitdecks.decks import DECK_TYPES

logging.addLevelName(SPAM_LEVEL, SPAM)
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

if LOGFILE is not None:
    formatter = logging.Formatter(FORMAT)
    handler = logging.FileHandler(LOGFILE, mode="a")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class DeckTemplate(Config):
    """reads and parse deck template file"""

    def __init__(self, filename: str) -> None:
        Config.__init__(self, filename=filename)

    def icon_size(self, name: str = None):
        if name is not None:
            pass
        return (0, 0)


class CockpitBase:
    """As used in Simulator

    [description]
    """

    def __init__(self):
        pass

    def set_logging_level(self, name):
        if name in self._debug:
            l = logging.getLogger(name)
            if l is not None:
                l.setLevel(logging.DEBUG)
                l.info(f"set_logging_level: {name} set to debug")
            else:
                logger.warning(f"logger {name} not found")

    def reload_pages(self):
        pass


class Cockpit(DatarefListener, CockpitBase):
    """
    Contains all deck configurations for a given aircraft.
    Is started when aicraft is loaded and aircraft contains CONFIG_FOLDER folder.
    """

    def __init__(self, simulator):
        CockpitBase.__init__(self)
        DatarefListener.__init__(self)
        self._debug = ROOT_DEBUG.split(",")  # comma separated list of module names like cockpitdecks.page or cockpitdeck.button_ext

        self._config = None  # content of aircraft/deckconfig/config.yaml
        self.default_config = None  # content of resources/config.yaml

        self.name = "Cockpitdecks"
        self.icao = "ZZZZ"

        self.sim = simulator(self)

        self.disabled = False
        self.default_pages = None  # for debugging

        self.has_reload = False
        self.reload_loop_run = False
        self.reload_loop_thread = None
        self.reload_queue = Queue()

        self.devices = []

        self.acpath = None
        self.cockpit = {}  # all decks: { deckname: deck }
        self.deck_profiles = {}

        self.default_logo = DEFAULT_LOGO
        self.default_wallpaper = DEFAULT_WALLPAPER

        self.fonts = {}
        self.default_font = None
        self.default_label_font = DEFAULT_LABEL_FONT
        self.default_label_size = DEFAULT_LABEL_SIZE
        self.default_label_color = convert_color(DEFAULT_LABEL_COLOR)
        self.default_label_position = DEFAULT_LABEL_POSITION

        self.icon_folder = None
        self.icons = {}
        self.cache_icon = False
        self.default_icon_name = DEFAULT_ICON_NAME
        self.default_icon_color = convert_color(DEFAULT_ICON_COLOR)
        self.default_icon_texture = DEFAULT_ICON_TEXTURE
        self.default_annun_texture = None
        self.default_annun_color = convert_color(DEFAULT_ANNUNCIATOR_COLOR)

        self.fill_empty_keys = True
        self.annunciator_style = DEFAULT_ANNUNCIATOR_STYLE
        self.cockpit_color = convert_color(COCKPIT_COLOR)
        self.cockpit_texture = COCKPIT_TEXTURE

        self.default_home_page_name = HOME_PAGE

        self.busy_reloading = False

        self.init()

    def init(self):
        """
        Loads all devices connected to this computer.
        """
        self.load_deck_profiles()
        self.scan_devices()

    def get_id(self):
        return self.name

    def get_button_value(self, name):
        a = name.split(ID_SEP)
        if len(a) > 0:
            if a[0] == self.name:
                if a[1] in self.cockpit.keys():
                    return self.cockpit[a[1]].get_button_value(ID_SEP.join(a[1:]))
                else:
                    logger.warning(f"so such deck {a[1]}")
            else:
                logger.warning(f"no such cockpit {a[0]}")
        else:
            logger.warning(f"invalid name {name}")
        return None

    def inspect(self, what: str = None):
        """
        This function is called on all instances of Deck.
        """
        logger.info(f"Cockpitdecks Rel. {__version__} -- {what}")

        if "thread" in what:
            logger.info(f"{[(t.name,t.isDaemon(),t.is_alive()) for t in threading.enumerate()]}")
        elif what.startswith("datarefs"):
            self.inspect_datarefs(what)
        elif what == "monitored":
            self.inspect_monitored(what)
        else:
            for v in self.cockpit.values():
                v.inspect(what)

    def inspect_datarefs(self, what: str = None):
        if what.startswith("datarefs"):
            for dref in self.sim.all_datarefs.values():
                logger.info(f"{dref.path} = {dref.value()} ({len(dref.listeners)})")
                if what.endswith("listener"):
                    for l in dref.listeners:
                        logger.info(f"  {l.name}")
        else:
            logger.info(f"to do")

    def inspect_monitored(self, what: str = None):
        for dref in self.sim.datarefs.values():
            logger.info(f"{dref}")

    def scan_devices(self):
        if len(DECK_TYPES) == 0:
            logger.error(f"no driver")
            return
        logger.info(
            f"drivers installed for {', '.join([f'{decktype} {pkg_resources.get_distribution(decktype).version}' for decktype in DECK_TYPES.keys()])}; scanning.."
        )
        for decktype, builder in DECK_TYPES.items():
            decks = builder[1]().enumerate()
            logger.info(f"found {len(decks)} {decktype}")  # " ({decktype} {pkg_resources.get_distribution(decktype).version})")
            for name, device in enumerate(decks):
                device.open()
                serial = device.get_serial_number()
                device.close()
                if serial in EXCLUDE_DECKS:
                    logger.warning(f"deck {serial} excluded")
                    del decks[name]
                self.devices.append({"type": decktype, "device": device, "serial_number": serial})
            logger.debug(f"using {len(decks)} {decktype}")
        logger.debug(f"..scanned")

    def get_device(self, req_serial: str, req_type: str):
        """
        Get a HIDAPI device for the supplied serial number.
        If found, the device is opened and reset and returned open.

        :param    req_serial:  The request serial
        :type      req_serial:  str
        """
        # No serial, return deck if only one deck of that type
        if req_serial is None:
            i = 0
            good = None
            for deck in self.devices:
                if deck["type"] == req_type:
                    good = deck
                    i = i + 1
            if i == 1 and good is not None:
                logger.debug(f"only one deck of type {req_type}, returning it")
                device = good["device"]
                device.open()
                if device.is_visual():
                    image_format = device.key_image_format()
                    logger.debug(
                        f"key images: {image_format['size'][0]}x{image_format['size'][1]} pixels, {image_format['format']} format, rotated {image_format['rotation']} degrees"
                    )
                else:
                    logger.debug(f"no visual")
                device.reset()
                return device
            else:
                if i > 1:
                    logger.warning(f"more than one deck of type {req_type}, no serial to disambiguate")
            return None
        ## Got serial, search for it
        for deck in self.devices:
            if deck["serial_number"] == req_serial:
                device = deck["device"]
                device.open()
                if device.is_visual():
                    image_format = device.key_image_format()
                    logger.debug(
                        f"key images: {image_format['size'][0]}x{image_format['size'][1]} pixels, {image_format['format']} format, rotated {image_format['rotation']} degrees"
                    )
                else:
                    logger.debug(f"no visual")
                device.reset()
                return device
        logger.warning(f"deck {req_serial} not found")
        return None

    def start_aircraft(self, acpath: str):
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
            logger.warning(f"Cockpitdecks is disabled")
            return
        # Reset, if new aircraft
        if len(self.cockpit) > 0:
            self.terminate_aircraft()
            self.sim.clean_datarefs_to_monitor()
            logger.warning(f"{os.path.basename(self.acpath)} unloaded")

        if len(self.devices) == 0:
            logger.warning(f"no device")
            return

        self.cockpit = {}
        self.icons = {}
        # self.fonts = {}
        self.acpath = None

        self.load_defaults()

        if acpath is not None and os.path.exists(os.path.join(acpath, CONFIG_FOLDER)):
            self.acpath = acpath
            self.load_icons()
            self.load_fonts()
            self.create_decks()
            self.load_pages()
        else:
            if acpath is None:
                logger.error(f"no aircraft folder")
            elif not os.path.exists(acpath):
                logger.error(f"no aircraft folder {acpath}")
            else:
                logger.error(f"no Cockpitdecks folder '{CONFIG_FOLDER}' in aircraft folder {acpath}")
            self.create_default_decks()

    def load_pages(self):
        if self.default_pages is not None:
            logger.debug(f"default_pages {self.default_pages.keys()}")
            for name, deck in self.cockpit.items():
                if name in self.default_pages.keys():
                    if self.default_pages[name] in deck.pages.keys() and deck.home_page is not None:  # do not refresh if no home page loaded...
                        deck.change_page(self.default_pages[name])
                    else:
                        deck.change_page()
            self.default_pages = None
        else:
            for deck in self.cockpit.values():
                deck.change_page()

    def reload_pages(self):
        for name, deck in self.cockpit.items():
            deck.reload_page()

    def load_defaults(self):
        """
        Loads default values for font, icon, etc. They will be used if no layout is found.
        """

        def locate_font(fontname: str) -> str:
            if fontname in self.fonts.keys():
                logger.debug(f"font {fontname} already loaded")
                return fontname

            # 1. Try "system" font
            try:
                test = ImageFont.truetype(fontname, self.default_label_size)
                logger.debug(f"font {fontname} found in computer system fonts")
                return fontname
            except:
                logger.debug(f"font {fontname} not found in computer system fonts")

            # 2. Try font in resources folder
            fn = None
            try:
                fn = os.path.join(os.path.dirname(__file__), RESOURCES_FOLDER, fontname)
                test = ImageFont.truetype(fn, self.default_label_size)
                logger.debug(f"font {fontname} found locally ({RESOURCES_FOLDER} folder)")
                return fn
            except:
                logger.debug(f"font {fontname} not found locally ({RESOURCES_FOLDER} folder)")

            # 3. Try font in resources/fonts folder
            fn = None
            try:
                fn = os.path.join(os.path.dirname(__file__), RESOURCES_FOLDER, FONTS_FOLDER, fontname)
                test = ImageFont.truetype(fn, self.default_label_size)
                logger.debug(f"font {fontname} found locally ({FONTS_FOLDER} folder)")
                return fn
            except:
                logger.debug(f"font {fontname} not found locally ({FONTS_FOLDER} folder)")

            logger.debug(f"font {fontname} not found")
            return None

        # 0. Some variables defaults
        fn = os.path.join(os.path.dirname(__file__), RESOURCES_FOLDER, CONFIG_FILE)
        self.default_config = Config(fn)

        # Load global defaults from resources/config.yaml file or use application default
        self._debug = self.default_config.get("debug", ",".join(self._debug)).split(",")
        self.set_logging_level(__name__)

        self.sim.set_roundings(self.default_config.get("dataref-roundings", {}))
        self.sim.set_dataref_frequencies(self.default_config.get("dataref-fetch-frequencies", {}))

        self.default_logo = self.default_config.get("default-logo", DEFAULT_LOGO)
        self.default_wallpaper = self.default_config.get("default-wallpaper", DEFAULT_WALLPAPER)
        self.default_label_font = self.default_config.get("default-label-font", DEFAULT_LABEL_FONT)
        self.default_label_size = self.default_config.get("default-label-size", DEFAULT_LABEL_SIZE)
        self.default_label_color = self.default_config.get("default-label-color", convert_color(DEFAULT_LABEL_COLOR))
        self.default_label_position = self.default_config.get("default-label-position", DEFAULT_LABEL_POSITION)
        self.cache_icon = self.default_config.get("cache-icon", self.cache_icon)
        self.default_icon_name = DEFAULT_ICON_NAME
        self.default_icon_texture = self.default_config.get("default-icon-texture", DEFAULT_ICON_TEXTURE)
        self.default_icon_color = self.default_config.get("default-icon-color", DEFAULT_ICON_COLOR)
        self.default_icon_color = convert_color(self.default_icon_color)
        self.default_annun_texture = self.default_config.get("default-annunciator-texture")
        self.default_annun_color = self.default_config.get("default-annunciator-color", DEFAULT_ANNUNCIATOR_COLOR)
        self.default_annun_color = convert_color(self.default_annun_color)
        self.annunciator_style = self.default_config.get("annunciator-style", DEFAULT_ANNUNCIATOR_STYLE.value)
        self.annunciator_style = ANNUNCIATOR_STYLES(self.annunciator_style)
        self.cockpit_texture = self.default_config.get("cockpit-texture", COCKPIT_TEXTURE)
        self.cockpit_color = self.default_config.get("cockpit-color", COCKPIT_COLOR)
        self.cockpit_color = convert_color(self.cockpit_color)
        self.default_home_page_name = self.default_config.get("default-homepage-name", HOME_PAGE)
        #
        #
        # DO NOT FORGET SET DEFAULTS IN create_decks()
        #
        #

        # 1. Load global icons
        #   (They are never cached when loaded without aircraft.)
        rf = os.path.join(os.path.dirname(__file__), RESOURCES_FOLDER, ICONS_FOLDER)
        if os.path.exists(rf):
            icons = os.listdir(rf)
            for i in icons:
                if has_ext(i, "png"):  # later, might load JPG as well.
                    fn = os.path.join(rf, i)
                    image = Image.open(fn)
                    self.icons[i] = image

        # 2. Finding a default font for Pillow
        #   WE MUST find a default, system font at least

        # 2.1 We try the requested "default label font"
        tryed_our_default = self.default_label_font == DEFAULT_LABEL_FONT
        if self.default_label_font not in self.fonts.keys():
            f = locate_font(self.default_label_font)
            if f is not None:  # found one, perfect
                self.fonts[self.default_label_font] = f
                self.default_font = f
                logger.debug(f"default label font set to {self.default_label_font}")
            else:  # if we are here, self.default_label_font is not found, we must find another one
                self.default_label_font = None

        # 2.2 We try our "default provided label font"
        if self.default_label_font is None and not tryed_our_default:
            f = locate_font(DEFAULT_LABEL_FONT)
            if f is not None:  # found it, perfect
                self.default_label_font = DEFAULT_LABEL_FONT
                self.fonts[DEFAULT_LABEL_FONT] = f
                self.default_font = f
                logger.debug(f"default label font set to {DEFAULT_LABEL_FONT}")
            # if we are here, self.default_label_font is not found, we must find another one

        # 2.3 We try the "default system font"
        f = locate_font(DEFAULT_SYSTEM_FONT)
        if f is not None:  # found it, perfect, keep it as default font for all purposes
            self.fonts[DEFAULT_SYSTEM_FONT] = f
            self.default_font = f
            logger.debug(f"default font set to {DEFAULT_SYSTEM_FONT}")
            if self.default_label_font is None:  # additionnally, if we don't have a default label font, use it
                self.default_label_font = DEFAULT_SYSTEM_FONT
                logger.debug(f"default label font set to {DEFAULT_SYSTEM_FONT}")

        if self.default_label_font is None and len(self.fonts) > 0:
            first_one = list(self.fonts.keys())[0]
            self.default_label_font = first_one
            self.default_font = first_one
            logger.debug(f"no default font found, using first available font")

        if self.default_label_font is None:
            logger.error(f"no default font")

        # 4. report summary if debugging
        logger.debug(f"default fonts {self.fonts.keys()}, default={self.default_font}, default label={self.default_label_font}")

    def create_decks(self):
        sn = os.path.join(self.acpath, CONFIG_FOLDER, SECRET_FILE)
        serial_numbers = Config(sn)
        fn = os.path.join(self.acpath, CONFIG_FOLDER, CONFIG_FILE)
        self._config = Config(fn)
        if self._config.is_valid():
            #
            #
            # DO NOT FORGET SET DEFAULTS IN load_defaults()
            #
            #
            self.default_logo = self._config.get("default-logo", self.default_logo)
            self.default_wallpaper = self._config.get("default-wallpaper", self.default_wallpaper)
            self.default_label_font = self._config.get("default-label-font", self.default_label_font)
            self.default_label_size = self._config.get("default-label-size", self.default_label_size)
            self.default_label_color = self._config.get("default-label-color", self.default_label_color)
            self.default_label_color = convert_color(self.default_label_color)
            self.default_label_position = self._config.get("default-label-position", self.default_label_position)
            self.default_icon_texture = self._config.get("default-icon-texture", self.default_icon_texture)
            self.default_icon_color = self._config.get("default-icon-color", self.default_icon_color)
            self.default_icon_color = convert_color(self.default_icon_color)
            self.default_annun_texture = self._config.get("default-annunciator-texture", self.default_annun_texture)
            self.default_annun_color = self._config.get("default-annunciator-color", self.default_annun_color)
            self.default_annun_color = convert_color(self.default_annun_color)
            self.annunciator_style = self._config.get("annunciator-style", self.annunciator_style)
            self.annunciator_style = ANNUNCIATOR_STYLES(self.annunciator_style)
            self.cockpit_texture = self._config.get("cockpit-texture", self.cockpit_texture)
            self.cockpit_color = self._config.get("cockpit-color", self.cockpit_color)
            self.cockpit_color = convert_color(self.cockpit_color)
            self.default_home_page_name = self.default_config.get("default-homepage-name", self.default_home_page_name)

            logger.debug(f"label font={self.default_label_font}, logo={self.default_logo}, wallpaper={self.default_wallpaper}, texture={self.cockpit_texture}")
            decks = self._config.get("decks")
            if decks is not None:
                deck_type_count = {}
                for deck_config in decks:
                    ty = deck_config.get("type")
                    if ty is not None:
                        if ty not in deck_type_count:
                            deck_type_count[ty] = 0
                        deck_type_count[ty] = deck_type_count[ty] + 1

                cnt = 0
                for deck_config in decks:
                    name = deck_config.get("name", f"Deck {cnt}")

                    disabled = deck_config.get("disabled")
                    if type(disabled) != bool:
                        if type(disabled) == str:
                            disabled = disabled.upper() in ["YES", "TRUE"]
                        elif type(disabled) in [int, float]:
                            disabled = int(disabled) != 0
                    if disabled:
                        logger.info(f"deck {name} disabled, ignoring")
                        continue

                    decktype = deck_config.get("type")
                    if decktype not in DECK_TYPES.keys():
                        logger.warning(f"invalid deck type {decktype}, ignoring")
                        continue

                    serial = deck_config.get("serial")
                    if serial is None:  # get it from the secret file
                        serial = serial_numbers[name] if name in serial_numbers.keys() else None

                    # if serial is not None:
                    device = self.get_device(req_serial=serial, req_type=decktype)
                    if device is not None:
                        #
                        deck_config["model"] = device.deck_type()
                        if serial is None:
                            if deck_type_count[decktype] > 1:
                                logger.warning(f"only one deck of that type but more than one configuration in config.yaml for decks of that type, ignoring")
                                continue
                            deck_config["serial"] = device.get_serial_number()
                            logger.info(f"deck {decktype} {name} has serial {deck_config['serial']}")
                        else:
                            deck_config["serial"] = serial
                        if name not in self.cockpit.keys():
                            self.cockpit[name] = DECK_TYPES[decktype][0](name=name, config=deck_config, cockpit=self, device=device)
                            cnt = cnt + 1
                            logger.info(f"deck {decktype} {name} added")
                        else:
                            logger.warning(f"deck {name} already exist, ignoring")
                    # else:
                    #    logger.error(f"deck {decktype} {name} has no serial number, ignoring")
            else:
                logger.warning(f"no deck in config file {fn}")
        else:
            logger.warning(f"no config file {fn}")

    def create_default_decks(self):
        """
        When no deck definition is found in the aicraft folder, Cockpit loads
        a default X-Plane logo on all deck devices. The only active button is index 0,
        which toggle X-Plane map on/off.
        """
        self.acpath = None

        # {
        #    "type": decktype,
        #    "device": device,
        #    "serial_number": serial
        # }
        for deck in self.devices:
            decktype = deck.get("type")
            if decktype not in DECK_TYPES.keys():
                logger.warning(f"invalid deck type {decktype}, ignoring")
                continue
            device = deck["device"]
            device.open()
            device.reset()
            name = device.id()
            config = {
                "name": name,
                "model": device.deck_type(),
                "serial": device.get_serial_number(),
                "layout": None,  # Streamdeck will detect None layout and present default deck
                "brightness": 75,  # Note: layout=None is not the same as no layout attribute (attribute missing)
            }
            self.cockpit[name] = DECK_TYPES[decktype][0](name, config, self, device)

    # #########################################################
    # Cockpit data caches
    #
    def load_deck_profiles(self):
        folder = os.path.join(os.path.dirname(__file__), RESOURCES_FOLDER, DECKS_FOLDER)
        for profile in glob.glob(os.path.join(folder, "*.yaml")):
            data = DeckTemplate(profile)
            name = data.get("name")
            if name is not None:
                self.deck_profiles[name] = data
            else:
                logger.warning(f"ignoring unnamed deck {profile}")
        logger.info(f"loaded {len(self.deck_profiles)} deck profiles ({list(self.deck_profiles.keys())})")

    def get_deck_profile(self, name: str):
        return self.deck_profiles.get(name)

    def load_icons(self):
        # Loading icons
        #
        dn = os.path.join(self.acpath, CONFIG_FOLDER, ICONS_FOLDER)
        if os.path.exists(dn):
            self.icon_folder = dn
            cache = os.path.join(dn, "_icon_cache.pickle")
            if os.path.exists(cache) and self.cache_icon:
                with open(cache, "rb") as fp:
                    self.icons = pickle.load(fp)
                logger.info(f"{len(self.icons)} icons loaded from cache")
            else:
                # # Global, resource folder icons
                # #                                   # #
                # # THEY ARE NOW LOADED IN LOAD_DEFAULTS # #
                # #                                   # #
                # rf = os.path.join(os.path.dirname(__file__), RESOURCES_FOLDER, ICONS_FOLDER)
                # if os.path.exists(rf):
                #    icons = os.listdir(rf)
                #    for i in icons:
                #        if has_ext(i, "png"):  # later, might load JPG as well.
                #            fn = os.path.join(rf, i)
                #            image = Image.open(fn)
                #            self.icons[i] = image

                # Aircraft specific folder icons
                icons = os.listdir(dn)
                for i in icons:
                    if has_ext(i, "png"):  # later, might load JPG as well.
                        fn = os.path.join(dn, i)
                        image = Image.open(fn)
                        self.icons[i] = image

                if self.cache_icon:  # we cache both folders of icons
                    with open(cache, "wb") as fp:
                        pickle.dump(self.icons, fp)
                    logger.info(f"{len(self.icons)} icons cached")
                else:
                    logger.info(f"{len(self.icons)} icons loaded")

    def load_fonts(self):
        # Loading fonts.
        # For custom fonts (fonts found in the fonts config folder),
        # we supply the full path for font definition to ImageFont.
        # For other fonts, we assume ImageFont will search at OS dependent folders or directories.
        # If the font is not found by ImageFont, we ignore it.
        # So self.icons is a list of properly located usable fonts.
        #
        # 1. Load fonts supplied by Cockpitdeck in its resource folder
        rn = os.path.join(os.path.dirname(__file__), RESOURCES_FOLDER, FONTS_FOLDER)
        if os.path.exists(rn):
            fonts = os.listdir(rn)
            for i in fonts:
                if has_ext(i, ".ttf") or has_ext(i, ".otf"):
                    if i not in self.fonts.keys():
                        fn = os.path.join(rn, i)
                        try:
                            test = ImageFont.truetype(fn, self.default_label_size)
                            self.fonts[i] = fn
                        except:
                            logger.warning(f"default font file {fn} not loaded")
                    else:
                        logger.debug(f"font {i} already loaded")

        # 2. Load fonts supplied by the user in the configuration
        dn = os.path.join(self.acpath, CONFIG_FOLDER, FONTS_FOLDER)
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
                            logger.warning(f"custom font file {fn} not loaded")
                    else:
                        logger.debug(f"font {i} already loaded")

        # 3. DEFAULT_LABEL_FONT and DEFAULT_SYSTEM_FONT loaded in load_defaults()

        logger.info(f"{len(self.fonts)} fonts loaded, default label font={self.default_label_font}")

    # #########################################################
    # Cockpit start/stop/reload procedures
    #
    # Note: Reloading the deck is done from a separate (dedicated) thread through a queue.
    #
    # The reason is that the reload is provoked by a keypress which is handled in a callback
    # from a deck thread. On reload, the deck will be stopped, initialized, and restarted
    # leading somehow in the destruction of the objects that had created the thread.
    # When pressing a new button, callback would terminate Cockpitdeck.
    # To prevent that, the callback just enqueue a request to perform a reload and exits right away.
    # We do the reload from another thread, external to the callback,
    # that cleanly stops, initializes, and restarts the deck.
    #
    # Note: Only started if has_reload is True. has_reload is set if a Reload button activation is configured.
    #      (Otherwise there is no need to start the reload loop since nothing can provoke it.)
    #
    def start_reload_loop(self):
        if not self.has_reload:
            logger.warning(f"no reload button detected, not starting")
            return
        if not self.reload_loop_run:
            self.reload_loop_thread = threading.Thread(target=self.reload_loop)
            self.reload_loop_thread.name = f"Cockpit::reloader"
            self.reload_loop_run = True
            self.reload_loop_thread.start()
            logger.debug(f"started")
        else:
            logger.warning(f"already running")

    def reload_loop(self):
        while self.reload_loop_run:
            e = self.reload_queue.get()  # blocks infinitely here
            if e == "reload":
                self.reload_decks(just_do_it=True)
            elif e == "stop":
                self.stop_decks(just_do_it=True)
        logger.debug(f"ended")

    def end_reload_loop(self):
        if self.reload_loop_run:
            self.reload_loop_run = False
            self.reload_queue.put("wake up!")  # to unblock the Queue.get()
            # self.reload_loop_thread.join()
            logger.debug(f"stopped")
        else:
            logger.warning(f"not running")

    def reload_decks(self, just_do_it: bool = False):
        """
        Development function to reload page yaml without leaving the page
        Should not be used in production...
        """
        # A security... if we get called we must ensure reloader is running...
        if not self.reload_loop_run:
            logger.warning(f"reload loop not running. Starting..")
            self.has_reload = True
            self.start_reload_loop()
        if just_do_it:
            logger.info(f"reloading decks..")
            self.busy_reloading = True
            self.default_pages = {}  # {deck_name: currently_loaded_page_name}
            for name, deck in self.cockpit.items():
                self.default_pages[name] = deck.current_page.name
            self.load_aircraft(self.acpath)  # will terminate it before loading again
            self.busy_reloading = False
            logger.info(f"..done")
        else:
            self.reload_queue.put("reload")
            logger.debug(f"enqueued")

    def stop_decks(self, just_do_it: bool = False):
        """
        Stop decks gracefully. Since it also terminates self.reload_loop_thread we cannot wait for it
        since we are called from it ... So we just tell it to terminate.
        """
        if just_do_it:
            logger.info(f"stopping decks..")
            self.stop()
        else:
            self.reload_queue.put("stop")
            logger.debug(f"enqueued")

    def dataref_changed(self, dataref):
        """
        This gets called when dataref AIRCRAFT_DATAREF is changed, hence a new aircraft has been loaded.
        """
        v = dataref.value()
        if v is not None and v == 1:
            logger.info(f"current aircraft loaded {dataref.path}={dataref.value()}")
        else:
            logger.info(f"new aircraft loaded {dataref.path}={dataref.value()}")

    def terminate_aircraft(self):
        logger.info(f"terminating..")
        for deck in self.cockpit.values():
            deck.terminate()
        self.cockpit = {}
        nt = len(threading.enumerate())
        if not self.sim.use_flight_loop and nt > 1:
            logger.info(f"{nt} threads")
            logger.info(f"{[t.name for t in threading.enumerate()]}")
        logger.info(f"..done")

    def terminate_devices(self):
        for deck in self.devices:
            decktype = deck.get("type")
            if decktype not in DECK_TYPES.keys():
                logger.warning(f"invalid deck type {decktype}, ignoring")
                continue
            device = deck["device"]
            DECK_TYPES[decktype][0].terminate_device(device, deck["serial_number"])

    def terminate_all(self, threads: int = 1):
        logger.info(f"terminating..")
        # Terminate decks
        self.terminate_aircraft()
        # Terminate dataref collection
        if self.sim is not None:
            logger.info("..terminating connection to simulator..")
            self.sim.terminate()
            logger.debug("..deleting connection to simulator..")
            del self.sim
            self.sim = None
            logger.debug("..connection to simulator deleted..")
        # Terminate reload loop
        if self.reload_loop_run:
            self.end_reload_loop()
        logger.info(f"..terminating devices..")
        self.terminate_devices()
        logger.info(f"..done")
        left = len(threading.enumerate())
        if left > threads:  # [MainThread and spinner]
            logger.error(f"{left} threads remaining")
            logger.error(f"{[t.name for t in threading.enumerate()]}")

    def run(self):
        if len(self.cockpit) > 0:
            # Each deck should have been started
            # Start reload loop
            logger.info(f"starting..")
            self.sim.connect()
            logger.info(f"..connect to simulator loop started..")
            self.start_reload_loop()
            logger.info(f"..reload loop started..")
            if not self.sim.use_flight_loop:
                logger.info(f"{len(threading.enumerate())} threads")
                logger.info(f"{[t.name for t in threading.enumerate()]}")
                logger.info(f"..started")
                logger.info(f"serving {self.name}")
                for t in threading.enumerate():
                    try:
                        t.join()
                    except RuntimeError:
                        pass
                logger.info(f"terminated")
        else:
            logger.warning(f"no deck")
            if self.acpath is not None:
                self.terminate_all()

    # #########################################################
    # XPPython Plugin Hooks
    #
    def start(self):
        logger.info(f"starting..")
        # do nothing, started in when enabled
        logger.info(f"done")

    def stop(self):
        logger.info(f"stopping..")
        self.terminate_all()
        logger.info(f"done")

    def enable(self):
        self.load(self.acpath)
        self.disabled = False
        logger.info(f"enabled")

    def disable(self):
        self.terminate_aircraft()
        self.disabled = True
        logger.info(f"disabled")
