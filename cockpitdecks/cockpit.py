# Main container for all decks
#
import os
import glob
import threading
import logging
import pickle
import pkg_resources
from queue import Queue

from PIL import Image, ImageFont

from cockpitdecks import __version__, LOGFILE, FORMAT
from cockpitdecks import ID_SEP, SPAM, SPAM_LEVEL, ROOT_DEBUG
from cockpitdecks import CONFIG_FOLDER, CONFIG_FILE, SECRET_FILE, EXCLUDE_DECKS, ICONS_FOLDER, FONTS_FOLDER, RESOURCES_FOLDER
from cockpitdecks import Config, KW, GLOBAL_DEFAULTS
from cockpitdecks.resources.color import convert_color, has_ext
from cockpitdecks.simulator import DatarefListener
from cockpitdecks.deck import DECKS_FOLDER, DeckType
from cockpitdecks.decks import DECK_DRIVERS

logging.addLevelName(SPAM_LEVEL, SPAM)
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

if LOGFILE is not None:
    formatter = logging.Formatter(FORMAT)
    handler = logging.FileHandler(LOGFILE, mode="a")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class CockpitBase:
    """As used in Simulator

    [description]
    """

    def __init__(self):
        self._debug = ROOT_DEBUG.split(",")  # comma separated list of module names like cockpitdecks.page or cockpitdeck.button_ext
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

        self._defaults = GLOBAL_DEFAULTS
        self._reqdfts = set()
        self._config = {}  # content of aircraft/deckconfig/config.yaml
        self._resources_config = {}  # content of resources/config.yaml
        self.theme = None
        self._dark = False

        self.name = "Cockpitdecks"  # "Aircraft" name or model...
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
        self.deck_types = {}

        self.fonts = {}

        self.icon_folder = None
        self.icons = {}
        self.default_icon_name = None

        self.fill_empty_keys = True

        self.busy_reloading = False

        self.init()

    def init(self):
        """
        Loads all devices connected to this computer.
        """
        self.load_deck_types()
        self.scan_devices()

    def get_id(self):
        return self.name

    def set_default(self, dflt, value):
        ATTRNAME = "_defaults"
        if not hasattr(self, ATTRNAME):
            setattr(self, ATTRNAME, dict())
        ld = getattr(self, ATTRNAME)
        if isinstance(ld, dict):
            ld[dflt] = value
        logger.debug(f"set default {dflt} to {value}")

    def defaults_prefix(self):
        return "dark-default-" if self._dark else "default-"

    def is_color_attribute(self, attribute, value):
        # will need refinements
        if "color" in attribute:
            # logger.debug(f"converted color attribute {attribute}")
            return convert_color(value)
        return value

    def get_attribute(self, attribute: str, silence: bool = False):
        # Attempts to provide a dark/light theme alternative, fall back on light(=normal)
        if attribute.startswith("default-") or attribute.startswith("cockpit-"):
            prefix = self._config.get("cockpit-theme")  # prefix = "dark-"  #
            if prefix is not None and prefix not in ["default", "cockpit"] and not attribute.startswith(prefix):
                newattr = "-".join([prefix, attribute])
                val = self.get_attribute(attribute=newattr, silence=silence)
                if val is not None:
                    logger.debug(f"{attribute}, {newattr}, {val}")
                    return self.is_color_attribute(attribute=attribute, value=val)
                # else, no attribute named by newattr, just try plain attr name
        # Normal ops
        self._reqdfts.add(attribute)  # internal stats
        if attribute in self._config.keys():
            return self.is_color_attribute(attribute=attribute, value=self._config.get(attribute))
        if attribute in self._resources_config.keys():
            return self.is_color_attribute(attribute=attribute, value=self._resources_config.get(attribute))
        ATTRNAME = "_defaults"
        if hasattr(self, ATTRNAME):
            ld = getattr(self, ATTRNAME)
            if isinstance(ld, dict):
                if attribute in ld.keys():
                    return self.is_color_attribute(attribute=attribute, value=ld.get(attribute))
        if not silence and "-" in attribute and attribute.split("-")[-1] not in ["font", "size", "color", "position", "texture"]:
            logger.warning(f"no attribute {attribute}")
        return None

    def is_dark(self):
        # Could also determine this from simulator time...
        # Always evaluates cockpit attribute since its value can be updated
        # by page changes
        #
        # Note: Theming could be extended to any "string" like:
        #
        # cockpit-theme: barbie
        #
        # and defaults as
        #
        # barbie-default-label-color: pink
        #
        val = self.get_attribute("cockpit-theme")
        self._dark = val is not None and val in ["dark", "night"]
        return self._dark

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

    def inspect(self, what: str | None = None):
        """
        This function is called on all instances of Deck.
        """
        logger.info(f"Cockpitdecks Rel. {__version__} -- {what}")

        if what is not None and "thread" in what:
            logger.info(f"{[(t.name,t.isDaemon(),t.is_alive()) for t in threading.enumerate()]}")
        elif what is not None and what.startswith("datarefs"):
            self.inspect_datarefs(what)
        elif what == "monitored":
            self.inspect_monitored(what)
        else:
            for v in self.cockpit.values():
                v.inspect(what)

    def inspect_datarefs(self, what: str | None = None):
        if what is not None and what.startswith("datarefs"):
            for dref in self.sim.all_datarefs.values():
                logger.info(f"{dref.path} = {dref.value()} ({len(dref.listeners)})")
                if what.endswith("listener"):
                    for l in dref.listeners:
                        logger.info(f"  {l.name}")
        else:
            logger.info(f"to do")

    def inspect_monitored(self, what: str | None = None):
        for dref in self.sim.datarefs.values():
            logger.info(f"{dref}")

    def scan_devices(self):
        if len(DECK_DRIVERS) == 0:
            logger.error(f"no driver")
            return
        logger.info(
            f"drivers installed for {', '.join([f'{deck_driver} {pkg_resources.get_distribution(deck_driver).version}' for deck_driver in DECK_DRIVERS.keys()])}; scanning.."
        )
        for deck_driver, builder in DECK_DRIVERS.items():
            decks = builder[1]().enumerate()
            logger.info(f"found {len(decks)} {deck_driver}")  # " ({deck_driver} {pkg_resources.get_distribution(deck_driver).version})")
            for name, device in enumerate(decks):
                device.open()
                serial = device.get_serial_number()
                device.close()
                if serial in EXCLUDE_DECKS:
                    logger.warning(f"deck {serial} excluded")
                    del decks[name]
                logger.debug(f"added {type(device).__name__} (driver {deck_driver}, serial {serial[:3]}{'*'*max(1,len(serial))})")
                self.devices.append({KW.DRIVER.value: deck_driver, KW.DEVICE.value: device, KW.SERIAL.value: serial})
            logger.debug(f"using {len(decks)} {deck_driver}")
        logger.debug(f"..scanned")

    def get_device(self, req_serial: str, req_driver: str):
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
                if deck[KW.DRIVER.value] == req_driver:
                    good = deck
                    i = i + 1
            if i == 1 and good is not None:
                logger.debug(f"only one deck of type {req_driver}, returning it")
                device = good[KW.DEVICE.value]
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
                    logger.warning(f"more than one deck of type {req_driver}, no serial to disambiguate")
            return None
        ## Got serial, search for it
        for deck in self.devices:
            if deck[KW.SERIAL.value] == req_serial:
                device = deck[KW.DEVICE.value]
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

        def locate_font(fontname: str) -> str | None:
            if fontname in self.fonts.keys():
                logger.debug(f"font {fontname} already loaded")
                return fontname

            # 1. Try "system" font
            try:
                test = ImageFont.truetype(fontname, self.get_attribute("default-label-size"))
                logger.debug(f"font {fontname} found in computer system fonts")
                return fontname
            except:
                logger.debug(f"font {fontname} not found in computer system fonts")

            # 2. Try font in resources folder
            fn = None
            try:
                fn = os.path.join(os.path.dirname(__file__), RESOURCES_FOLDER, fontname)
                test = ImageFont.truetype(fn, self.get_attribute("default-label-size"))
                logger.debug(f"font {fontname} found locally ({RESOURCES_FOLDER} folder)")
                return fn
            except:
                logger.debug(f"font {fontname} not found locally ({RESOURCES_FOLDER} folder)")

            # 3. Try font in resources/fonts folder
            fn = None
            try:
                fn = os.path.join(os.path.dirname(__file__), RESOURCES_FOLDER, FONTS_FOLDER, fontname)
                test = ImageFont.truetype(fn, self.get_attribute("default-label-size"))
                logger.debug(f"font {fontname} found locally ({FONTS_FOLDER} folder)")
                return fn
            except:
                logger.debug(f"font {fontname} not found locally ({FONTS_FOLDER} folder)")

            logger.debug(f"font {fontname} not found")
            return None

        # 0. Some variables defaults
        fn = os.path.join(os.path.dirname(__file__), RESOURCES_FOLDER, CONFIG_FILE)
        self._resources_config = Config(fn)

        # Load global defaults from resources/config.yaml file or use application default
        self._debug = self._resources_config.get("debug", ",".join(self._debug)).split(",")
        self.set_logging_level(__name__)

        self.sim.set_roundings(self._resources_config.get("dataref-roundings", {}))
        self.sim.set_dataref_frequencies(self._resources_config.get("dataref-fetch-frequencies", {}))

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

        # 1.2 Do we have a default icon with proper name?
        dftname = self.get_attribute("default-icon-name")
        if dftname in self.icons.keys():
            logger.debug(f"default icon name {dftname} found")
        else:
            logger.warning(f"default icon name {dftname} not found")

        # 2. Finding a default font for Pillow
        #   WE MUST find a default, system font at least

        # 2.1 We try the requested "default label font"
        default_label_font = self.get_attribute("default-label-font")
        if default_label_font is not None and default_label_font not in self.fonts.keys():
            f = locate_font(default_label_font)
            if f is not None:  # found one, perfect
                self.fonts[default_label_font] = f
                self.set_default("default-font", default_label_font)
                logger.debug(f"default font set to {default_label_font}")
                logger.debug(f"default label font set to {default_label_font}")

        # 2.3 We try the "default system font"
        default_system_font = self.get_attribute("default-system-font")
        if default_system_font is not None:
            f = locate_font(default_system_font)
            if f is not None:  # found it, perfect, keep it as default font for all purposes
                self.fonts[default_system_font] = f
                self.set_default("default-font", default_system_font)
                logger.debug(f"default font set to {default_system_font}")
                if default_label_font is None:  # additionnally, if we don't have a default label font, use it
                    self.set_default("default-label-font", default_system_font)
                    logger.debug(f"default label font set to {default_system_font}")

        if default_label_font is None and len(self.fonts) > 0:
            first_one = list(self.fonts.keys())[0]
            self.set_default("default-label-font", first_one)
            self.set_default("default-font", first_one)
            logger.debug(f"no default font found, using first available font ({first_one})")

        if default_label_font is None:
            logger.error(f"no default font")

        # 4. report summary if debugging
        logger.debug(
            f"default fonts {self.fonts.keys()}, default={self.get_attribute('default-font')}, default label={self.get_attribute('default-label-font')}"
        )

    def create_decks(self):
        fn = os.path.join(self.acpath, CONFIG_FOLDER, CONFIG_FILE)
        self._config = Config(fn)
        if not self._config.is_valid():
            logger.warning(f"no config file {fn}")
            return
        sn = os.path.join(self.acpath, CONFIG_FOLDER, SECRET_FILE)
        serial_numbers = Config(sn)

        decks = self._config.get("decks")
        if decks is None:
            logger.warning(f"no deck in config file {fn}")
            return

        logger.info(f"cockpit is {'dark' if self.is_dark() else 'light'}, theme is {self.get_attribute('cockpit-theme')}")  # debug?

        deck_count_by_type = {}
        for deck_type in self.deck_types.values():
            ty = deck_type.get(KW.TYPE.value)
            if ty is not None:
                if ty not in deck_count_by_type:
                    deck_count_by_type[ty] = 0
                deck_count_by_type[ty] = deck_count_by_type[ty] + 1

        cnt = 0
        for deck_config in decks:
            name = deck_config.get(KW.NAME.value, f"Deck {cnt}")

            disabled = deck_config.get(KW.DISABLED.value)
            if type(disabled) != bool:
                if type(disabled) == str:
                    disabled = disabled.upper() in ["YES", "TRUE"]
                elif type(disabled) in [int, float]:
                    disabled = int(disabled) != 0
            if disabled:
                logger.info(f"deck {name} disabled, ignoring")
                continue

            deck_type = deck_config.get(KW.TYPE.value)
            if deck_type not in self.deck_types.keys():
                logger.warning(f"invalid deck type {deck_type}, ignoring")
                continue

            deck_driver = self.deck_types[deck_type][KW.DRIVER.value]
            if deck_driver not in DECK_DRIVERS.keys():
                logger.warning(f"invalid deck driver {deck_driver}, ignoring")
                continue

            serial = deck_config.get(KW.SERIAL.value)
            if serial is None:  # get it from the secret file
                serial = serial_numbers[name] if name in serial_numbers.keys() else None

            # if serial is not None:
            device = self.get_device(req_serial=serial, req_driver=deck_driver)
            if device is not None:
                #
                deck_config[KW.MODEL.value] = device.deck_type()
                if serial is None:
                    if deck_count_by_type[deck_type] > 1:
                        logger.warning(
                            f"only one deck of that type but more than one configuration in config.yaml for decks of that type and no serial number, ignoring"
                        )
                        continue
                    deck_config[KW.SERIAL.value] = device.get_serial_number()
                    logger.info(f"deck {deck_type} {name} has serial {deck_config[KW.SERIAL.value]}")
                else:
                    deck_config[KW.SERIAL.value] = serial
                if name not in self.cockpit.keys():
                    self.cockpit[name] = DECK_DRIVERS[deck_driver][0](name=name, config=deck_config, cockpit=self, device=device)
                    cnt = cnt + 1
                    logger.info(f"deck {name} added ({deck_type}, driver {deck_driver})")
                else:
                    logger.warning(f"deck {name} already exist, ignoring")
            # else:
            #    logger.error(f"deck {deck_type} {name} has no serial number, ignoring")

    def create_default_decks(self):
        """
        When no deck definition is found in the aicraft folder, Cockpit loads
        a default X-Plane logo on all deck devices. The only active button is index 0,
        which toggle X-Plane map on/off.
        """
        self.acpath = None

        # {
        #    KW.TYPE.value: decktype,
        #    KW.DEVICE.value: device,
        #    KW.SERIAL.value: serial
        # }
        for deck in self.devices:
            decktype = deck.get(KW.TYPE.value)
            if decktype not in DECK_DRIVERS.keys():
                logger.warning(f"invalid deck type {decktype}, ignoring")
                continue
            device = deck[KW.DEVICE.value]
            device.open()
            device.reset()
            name = device.id()
            config = {
                KW.NAME.value: name,
                KW.MODEL.value: device.deck_type(),
                KW.SERIAL.value: device.get_serial_number(),
                KW.LAYOUT.value: None,  # Streamdeck will detect None layout and present default deck
                "brightness": 75,  # Note: layout=None is not the same as no layout attribute (attribute missing)
            }
            self.cockpit[name] = DECK_DRIVERS[decktype][0](name, config, self, device)

    # #########################################################
    # Cockpit data caches
    #
    def load_deck_types(self):
        folder = os.path.join(os.path.dirname(__file__), RESOURCES_FOLDER, DECKS_FOLDER)
        for deck_type in glob.glob(os.path.join(folder, "*.yaml")):
            data = DeckType(deck_type)
            name = data.get(KW.TYPE.value)
            if name is not None:
                self.deck_types[name] = data
            else:
                logger.warning(f"ignoring unnamed deck {deck_type}")
        logger.info(f"loaded {len(self.deck_types)} deck types ({list(self.deck_types.keys())})")

    def get_deck_type_description(self, name: str):
        return self.deck_types.get(name)

    def load_icons(self):
        # Loading icons
        #
        cache_icon = self.get_attribute("cache-icon")
        dn = os.path.join(self.acpath, CONFIG_FOLDER, RESOURCES_FOLDER, ICONS_FOLDER)
        if os.path.exists(dn):
            self.icon_folder = dn
            cache = os.path.join(dn, "_icon_cache.pickle")
            if os.path.exists(cache) and cache_icon:
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

                if cache_icon:  # we cache both folders of icons
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
                            test = ImageFont.truetype(fn, self.get_attribute("default-label-size"))
                            self.fonts[i] = fn
                        except:
                            logger.warning(f"default font file {fn} not loaded")
                    else:
                        logger.debug(f"font {i} already loaded")

        # 2. Load fonts supplied by the user in the configuration
        dn = os.path.join(self.acpath, CONFIG_FOLDER, RESOURCES_FOLDER, FONTS_FOLDER)
        if os.path.exists(dn):
            fonts = os.listdir(dn)
            for i in fonts:
                if has_ext(i, ".ttf") or has_ext(i, ".otf"):
                    if i not in self.fonts.keys():
                        fn = os.path.join(dn, i)
                        try:
                            test = ImageFont.truetype(fn, self.get_attribute("default-label-size"))
                            self.fonts[i] = fn
                        except:
                            logger.warning(f"custom font file {fn} not loaded")
                    else:
                        logger.debug(f"font {i} already loaded")

        # 3. DEFAULT_LABEL_FONT and DEFAULT_SYSTEM_FONT loaded in load_defaults()

        logger.info(
            f"{len(self.fonts)} fonts loaded, default font={self.get_attribute('default-font')}, default label font={self.get_attribute('default-label-font')}"
        )

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
            self.terminate_all()
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
            deck_driver = deck.get(KW.DRIVER.value)
            if deck_driver not in DECK_DRIVERS.keys():
                logger.warning(f"invalid deck type {deck_driver}, ignoring")
                continue
            device = deck[KW.DEVICE.value]
            DECK_DRIVERS[deck_driver][0].terminate_device(device, deck[KW.SERIAL.value])

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
        # logger.info(self._reqdfts)

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
                logger.info(f"(note: threads named 'Thread-? (_read)' are Elgato Stream Deck serial port readers)")
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
