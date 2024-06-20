# Main container for all decks
#
import os
import glob
import threading
import logging
import pickle
import json
import pkg_resources
from datetime import datetime
from queue import Queue

from PIL import Image, ImageFont
from cairosvg import svg2png

from cockpitdecks import __version__, __NAME__, LOGFILE, FORMAT
from cockpitdecks import ID_SEP, SPAM, SPAM_LEVEL, ROOT_DEBUG
from cockpitdecks import CONFIG_FOLDER, CONFIG_FILE, SECRET_FILE, EXCLUDE_DECKS, ICONS_FOLDER, FONTS_FOLDER, RESOURCES_FOLDER, DECKS_FOLDER
from cockpitdecks import Config, CONFIG_KW, COCKPITDECKS_DEFAULT_VALUES, VIRTUAL_DECK_DRIVER
from cockpitdecks.resources.color import convert_color, has_ext, add_ext
from cockpitdecks.simulator import DatarefListener
from cockpitdecks.decks import DECK_DRIVERS
from cockpitdecks.decks.resources import DeckType

# from cockpitdecks.webdeckproxyapp import app

logging.addLevelName(SPAM_LEVEL, SPAM)
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

if LOGFILE is not None:
    formatter = logging.Formatter(FORMAT)
    handler = logging.FileHandler(LOGFILE, mode="a")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class CockpitBase:
    """As used in Simulator"""

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

        self._defaults = COCKPITDECKS_DEFAULT_VALUES
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

        # Main event look
        self.event_loop_run = False
        self.event_loop_thread = None
        self.event_queue = Queue()
        self._stats = {}

        # Virtual deck
        self.rcv_loop_run = False
        self.rcv_event = None
        self.rcv_thread = None

        self.devices = []

        self.acpath = None
        self.cockpit = {}  # all decks: { deckname: deck }
        self.deck_types = {}
        self.deck_types_new = {}
        self.virtual_deck_types = {}
        self.virtual_deck_list = {}
        self.virtual_decks_added = False

        self.vd_ws_conn = {}
        self.vd_errs = []

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
        def theme_only(a: str) -> bool:
            return a.endswith("color") or a.endswith("texture")

        if attribute.startswith("default-") or attribute.startswith("cockpit-"):
            prefix = self._config.get("cockpit-theme")  # prefix = "dark-"  #
            if prefix is not None and prefix not in ["default", "cockpit"] and not attribute.startswith(prefix):
                newattr = "-".join([prefix, attribute])
                val = self.get_attribute(attribute=newattr, silence=silence)
                if val is not None:
                    logger.debug(f"{attribute}, {newattr}, {val}")
                    return self.is_color_attribute(attribute=attribute, value=val)
                if theme_only(attribute):  # a theme exist, do not try without theme
                    if not silence:
                        logger.debug(f"themed attribute {newattr} not found, cannot try without theme")
                    return None
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
        """Scan for hardware devices"""
        if len(DECK_DRIVERS) == 0:
            logger.error(f"no driver")
            return
        logger.info(
            f"drivers installed for {', '.join([f'{deck_driver} {pkg_resources.get_distribution(deck_driver).version}' for deck_driver in DECK_DRIVERS.keys() if deck_driver != VIRTUAL_DECK_DRIVER])}; scanning.."
        )
        dependencies = [f"{v[0].DRIVER_NAME}>={v[0].MIN_DRIVER_VERSION}" for k, v in DECK_DRIVERS.items() if k != VIRTUAL_DECK_DRIVER]
        logger.debug(f"dependencies: {dependencies}")
        pkg_resources.require(dependencies)

        for deck_driver, builder in DECK_DRIVERS.items():
            if deck_driver == VIRTUAL_DECK_DRIVER:
                # will be added later, when we have acpath set, in add virtual_decks()
                continue
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
                self.devices.append(
                    {
                        CONFIG_KW.DRIVER.value: deck_driver,
                        CONFIG_KW.DEVICE.value: device,
                        CONFIG_KW.SERIAL.value: serial,
                    }
                )
            logger.debug(f"using {len(decks)} {deck_driver}")
        logger.debug(f"..scanned")

    def get_device(self, req_serial: str, req_driver: str):
        """
        Get a hardware device for the supplied serial number.
        If found, the device is opened and reset and returned open.

        :param    req_serial:  The request serial
        :type      req_serial:  str
        """
        # No serial, return deck if only one deck of that type
        if req_serial is None:
            i = 0
            good = None
            for deck in self.devices:
                if deck[CONFIG_KW.DRIVER.value] == req_driver:
                    good = deck
                    i = i + 1
            if i == 1 and good is not None:
                logger.debug(f"only one deck of type {req_driver}, returning it")
                device = good[CONFIG_KW.DEVICE.value]
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
                for deck in self.devices:
                    if deck[CONFIG_KW.DRIVER.value] == req_driver:
                        print(deck)
            return None
        ## Got serial, search for it
        for deck in self.devices:
            if deck[CONFIG_KW.SERIAL.value] == req_serial:
                device = deck[CONFIG_KW.DEVICE.value]
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

    def start_aircraft(self, acpath: str, release: bool = False):
        """
        Loads decks for aircraft in supplied path and start listening for key presses.
        """
        self.load_aircraft(acpath)
        self.run(release)

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

        self.cockpit = {}
        self.icons = {}
        # self.fonts = {}
        self.acpath = None

        self.load_defaults()

        if acpath is not None and os.path.exists(os.path.join(acpath, CONFIG_FOLDER)):
            self.acpath = acpath
            self.scan_virtual_decks()

            if len(self.devices) == 0:
                logger.warning(f"no device")
                return

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

    def scan_virtual_decks(self):
        """Virtual decks are declared in the cockpit configuration
        Therefore it is necessary to have an aircraft folder.

        [description]
        """
        if self.acpath is None:
            logger.warning(f"no aircraft folder, cannot load virtual decks")
            return
        if self.virtual_decks_added:
            logger.info(f"virtual decks already added")
            return
        cnt = 0
        builder = DECK_DRIVERS.get(VIRTUAL_DECK_DRIVER)
        decks = builder[1]().enumerate(acpath=self.acpath)
        logger.info(f"found {len(decks)} virtual deck(s)")
        for name, device in decks.items():
            serial = device.get_serial_number()
            if serial in EXCLUDE_DECKS:
                logger.warning(f"deck {serial} excluded")
                del decks[name]
            logger.info(f"added virtual deck {name}, serial {serial})")
            self.devices.append(
                {
                    CONFIG_KW.DRIVER.value: VIRTUAL_DECK_DRIVER,
                    CONFIG_KW.DEVICE.value: device,
                    CONFIG_KW.SERIAL.value: serial,
                }
            )
            cnt = cnt + 1
        self.virtual_decks_added = True
        logger.debug(f"added {cnt} virtual decks")

    def remove_virtual_decks(self):
        if not self.virtual_decks_added:
            logger.info(f"virtual decks not added")
            return
        to_remove = []
        for device in self.devices:
            if device.get(CONFIG_KW.DRIVER.value) == VIRTUAL_DECK_DRIVER:
                to_remove.append(device)
        for device in to_remove:
            self.devices.remove(device)
        self.virtual_decks_added = False
        logger.debug(f"removed {len(to_remove)} virtual decks")

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

        # init
        deck_count_by_type = {ty.get(CONFIG_KW.NAME.value): 0 for ty in self.deck_types.values()}
        # tally
        for deck in decks:
            ty = deck.get(CONFIG_KW.TYPE.value)
            if ty in deck_count_by_type:
                deck_count_by_type[ty] = deck_count_by_type[ty] + 1
            else:
                deck_count_by_type[ty] = 1

        cnt = 0
        self.virtual_deck_list = {}

        for deck_config in decks:
            name = deck_config.get(CONFIG_KW.NAME.value, f"Deck {cnt}")

            disabled = deck_config.get(CONFIG_KW.DISABLED.value)
            if type(disabled) != bool:
                if type(disabled) == str:
                    disabled = disabled.upper() in ["YES", "TRUE"]
                elif type(disabled) in [int, float]:
                    disabled = int(disabled) != 0
            if disabled:
                logger.info(f"deck {name} disabled, ignoring")
                continue

            deck_type = deck_config.get(CONFIG_KW.TYPE.value)
            if deck_type not in self.deck_types.keys():
                logger.warning(f"invalid deck type {deck_type}, ignoring")
                continue

            deck_driver = self.deck_types[deck_type][CONFIG_KW.DRIVER.value]
            if deck_driver not in DECK_DRIVERS.keys():
                logger.warning(f"invalid deck driver {deck_driver}, ignoring")
                continue

            serial = deck_config.get(CONFIG_KW.SERIAL.value)
            if serial is None:  # get it from the secret file
                serial = serial_numbers.get(name)

            # if serial is not None:
            device = self.get_device(req_serial=serial, req_driver=deck_driver)
            if device is not None:
                #
                if serial is None:
                    if deck_count_by_type[deck_type] > 1:
                        logger.warning(
                            f"only one deck of that type but more than one configuration in config.yaml for decks of that type and no serial number, ignoring"
                        )
                        continue
                    deck_config[CONFIG_KW.SERIAL.value] = device.get_serial_number()
                    logger.info(f"deck {deck_type} {name} has serial {deck_config[CONFIG_KW.SERIAL.value]}")
                else:
                    deck_config[CONFIG_KW.SERIAL.value] = serial
                if name not in self.cockpit.keys():
                    self.cockpit[name] = DECK_DRIVERS[deck_driver][0](name=name, config=deck_config, cockpit=self, device=device)
                    if deck_driver == VIRTUAL_DECK_DRIVER:
                        self.virtual_deck_list[name] = deck_config | {
                            "deck-type-desc": self.deck_types.get(deck_type).store,
                            "deck-type-flat": self.deck_types.get(deck_type).desc(),
                        }
                        # web decks need to have a decor
                        # decor = deck_config.get(CONFIG_KW.DECOR.value)
                        # if decor is None:
                        #     deck_config = deck_config | {CONFIG_KW.DECOR.value: {"background": "", "offset": [0, 0], "spacing": [0, 0]}}
                        #     logger.debug(f"deck {name} added neutral decor")
                    cnt = cnt + 1
                    logger.info(f"deck {name} added ({deck_type}, driver {deck_driver})")
                else:
                    logger.warning(f"deck {name} already exist, ignoring")
            # else:
            #    logger.error(f"deck {deck_type} {name} has no serial number, ignoring")
        # Temporary solution to hand over web decks
        # with open("vdecks.json", "w") as fp:
        #     json.dump(self.virtual_deck_list, fp, indent=2)

    def create_default_decks(self):
        """
        When no deck definition is found in the aicraft folder, Cockpit loads
        a default X-Plane logo on all deck devices. The only active button is index 0,
        which toggle X-Plane map on/off.
        """
        self.acpath = None

        # {
        #    CONFIG_KW.TYPE.value: decktype,
        #    CONFIG_KW.DEVICE.value: device,
        #    CONFIG_KW.SERIAL.value: serial
        # }
        for deck in self.devices:
            deckdriver = deck.get(CONFIG_KW.DRIVER.value)
            if deckdriver not in DECK_DRIVERS.keys():
                logger.warning(f"invalid deck driver {deckdriver}, ignoring")
                continue
            device = deck[CONFIG_KW.DEVICE.value]
            device.open()
            device.reset()
            name = device.id()
            config = {
                CONFIG_KW.NAME.value: name,
                CONFIG_KW.TYPE.value: device.deck_type(),
                CONFIG_KW.SERIAL.value: device.get_serial_number(),
                CONFIG_KW.LAYOUT.value: None,  # Streamdeck will detect None layout and present default deck
                "brightness": 75,  # Note: layout=None is not the same as no layout attribute (attribute missing)
            }
            self.cockpit[name] = DECK_DRIVERS[deckdriver][0](name, config, self, device)

    # #########################################################
    # Cockpit data caches
    #
    def load_deck_types(self):
        for deck_type in DeckType.list():
            data = DeckType(deck_type)
            self.deck_types[data.name] = data
            if data.is_virtual_deck():
                self.virtual_deck_types[data.name] = data.get_virtual_deck_layout()
        logger.info(f"loaded {len(self.deck_types)} deck types ({', '.join(self.deck_types.keys())}), {len(self.virtual_deck_types)} are virtual deck types")

    def get_deck_type(self, name: str):
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
                    elif has_ext(i, "svg"):  # Wow.
                        fn = os.path.join(dn, i)
                        fout = fn.replace(".svg", ".png")
                        svg2png(url=fn, write_to=fout)
                        image = Image.open(fout)
                        self.icons[i] = image

                if cache_icon:  # we cache both folders of icons
                    with open(cache, "wb") as fp:
                        pickle.dump(self.icons, fp)
                    logger.info(f"{len(self.icons)} icons cached")
                else:
                    logger.info(f"{len(self.icons)} icons loaded")

    def get_icon(self, candidate_icon):
        icon = None
        for ext in [".png", ".jpg", ".jpeg"]:
            fn = add_ext(candidate_icon, ext)
            if icon is None and fn in self.icons.keys():
                logger.debug(f"Cockpit: icon {fn} found")
                return fn
        logger.warning(f"Cockpit: icon not found {candidate_icon}, available={self.icons.keys()}")
        return None

    def get_icon_image(self, icon):
        if icon not in self.icons:
            logger.warning(f"Cockpit: icon not found {icon}, available={self.icons.keys()}")
        return self.icons.get(icon)

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
    # Cockpit start/stop/event/reload procedures
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
    def start_event_loop(self):
        if not self.event_loop_run:
            self.event_loop_thread = threading.Thread(target=self.event_loop, name=f"Cockpit::event_loop")
            self.event_loop_run = True
            self.event_loop_thread.start()
            logger.debug(f"started")
        else:
            logger.warning(f"already running")

    def event_loop(self):
        def add_event(s: str):
            if s in self._stats:
                self._stats[s] = self._stats[s] + 1
            else:
                self._stats[s] = 1

        logger.debug("starting event loop..")

        while self.event_loop_run:

            e = self.event_queue.get()  # blocks infinitely here

            if type(e) is str:
                if e == "terminate":
                    self.stop_event_loop()
                elif e == "reload":
                    self.reload_decks(just_do_it=True)
                elif e == "stop":
                    self.stop_decks(just_do_it=True)
                add_event(e)
                continue

            try:
                logger.debug(f"doing {e}..")
                add_event(type(e).__name__)
                e.run(just_do_it=True)
                logger.debug(f"..done without error")
            except:
                logger.warning(f"..done with error", exc_info=True)

        logger.debug(f".. event loop ended")

    def stop_event_loop(self):
        if self.event_loop_run:
            self.event_loop_run = False
            self.event_queue.put("terminate")  # to unblock the Queue.get()
            # self.event_loop_thread.join()
            logger.debug(f"stopped")
            logger.info("event processing stats: " + json.dumps(self._stats, indent=2))
        else:
            logger.warning(f"not running")

    # #########################################################
    # Cockpit start/stop/handle procedures for virtual decks
    #
    def has_virtual_decks(self) -> bool:
        for device in self.devices:
            if device.get(CONFIG_KW.DRIVER.value) == VIRTUAL_DECK_DRIVER:
                return True
        return False

    def get_web_decks(self):
        # Not all virtual decks are web decks
        webdeck_list = {}
        for name, deck in self.virtual_deck_list.items():
            if CONFIG_KW.LAYOUT.value in deck:  # has a decor, must be a web deck
                webdeck_list[name] = deck
        # add default values
        return webdeck_list

    def get_web_deck_description(self, deck):
        # Not all virtual decks are web decks
        res = self.virtual_deck_list.get(deck)
        return res if CONFIG_KW.LAYOUT.value in res else None

    def get_web_deck_defaults(self):
        return self.get_attribute("virtual-deck-defaults")

    def handle_code(self, code: int, name: str):
        logger.debug(f"received code {name}:{code}")
        if code == 1:
            deck = self.cockpit.get(name)
            if deck is None:
                logger.warning(f"handle code: deck {name} not found (code {code})")
                return
            deck.add_client()
            logger.debug(f"{name} opened")
            deck.reload_page()
            logger.debug(f"{name} reloaded")
        if code == 2:
            deck = self.cockpit.get(name)
            if deck is None:
                logger.warning(f"handle code: deck {name} not found (code {code})")
                return
            deck.remove_client()
            logger.debug(f"{name} closed")
        elif code in [4, 5]:
            payload = {"code": code, "deck": name, "meta": {"ts": datetime.now().timestamp()}}
            self.send(deck=self.name, payload=payload)

    def process_event(self, deck_name, key, event, data):
        deck = self.cockpit.get(deck_name)
        logger.debug(f"received {deck_name}: key={key}, event={event}")
        if deck is None:
            logger.warning(f"handle event: deck {deck_name} not found")
            return
        if deck.deck_type.is_virtual_deck():
            deck.key_change_callback(deck=deck, key=key, state=event, data=data)
        else:
            deck.key_change_callback(deck=deck, key=key, state=event)

    # #########################################################
    # Other
    #
    def reload_decks(self, just_do_it: bool = False):
        """
        Development function to reload page yaml without leaving the page
        Should not be used in production...
        """
        # A security... if we get called we must ensure reloader is running...
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
            self.event_queue.put("reload")
            logger.debug(f"enqueued")

    def stop_decks(self, just_do_it: bool = False):
        """
        Stop decks gracefully. Since it also terminates self.event_loop_thread we cannot wait for it
        since we are called from it ... So we just tell it to terminate.
        """
        if just_do_it:
            logger.info(f"stopping decks..")
            self.terminate_all()
        else:
            self.event_queue.put("stop")
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
        self.remove_virtual_decks()
        self.cockpit = {}
        nt = len(threading.enumerate())
        if nt > 1:
            logger.info(f"{nt} threads")
            logger.info(f"{[t.name for t in threading.enumerate()]}")
        logger.info(f"..done")

    def terminate_devices(self):
        for deck in self.devices:
            deck_driver = deck.get(CONFIG_KW.DRIVER.value)
            if deck_driver not in DECK_DRIVERS.keys():
                logger.warning(f"invalid deck type {deck_driver}, ignoring")
                continue
            device = deck[CONFIG_KW.DEVICE.value]
            DECK_DRIVERS[deck_driver][0].terminate_device(device, deck[CONFIG_KW.SERIAL.value])

    def terminate_all(self, threads: int = 1):
        logger.info(f"terminating..")
        # Stop processing events
        if self.event_loop_run:
            self.stop_event_loop()
            logger.info(f"..event loop stopped..")
        # Terminate decks
        self.terminate_aircraft()
        logger.info(f"..aircraft terminated..")
        # Terminate dataref collection
        if self.sim is not None:
            logger.info("..terminating connection to simulator..")
            self.sim.terminate()
            logger.debug("..deleting connection to simulator..")
            del self.sim
            self.sim = None
            logger.debug("..connection to simulator deleted..")
        logger.info(f"..terminating devices..")
        self.terminate_devices()
        logger.info(f"..done")
        left = len(threading.enumerate())
        if left > threads:  # [MainThread and spinner]
            logger.error(f"{left} threads remaining")
            logger.error(f"{[t.name for t in threading.enumerate()]}")
        # logger.info(self._reqdfts)

    def run(self, release: bool = False):
        if len(self.cockpit) > 0:
            # Each deck should have been started
            # Start reload loop
            logger.info(f"starting..")
            self.sim.connect()
            logger.info(f"..connect to simulator loop started..")
            self.start_event_loop()
            logger.info(f"..event loop started..")
            if self.has_virtual_decks():
                self.handle_code(code=4, name="init")  # wake up proxy
            logger.info(f"{len(threading.enumerate())} threads")
            logger.info(f"{[t.name for t in threading.enumerate()]}")
            logger.info(f"(note: threads named 'Thread-? (_read)' are Elgato Stream Deck serial port readers)")
            logger.info(f"..started")
            if not release or not self.has_virtual_decks():
                logger.info(f"serving {self.name}")
                for t in threading.enumerate():
                    try:
                        t.join()
                    except RuntimeError:
                        pass
                logger.info("terminated")
            logger.info(f"serving {self.name} (released)")
        else:
            logger.warning(f"no deck")
            if self.acpath is not None:
                self.terminate_all()

    def err_clear(self):
        self.vd_errs = []

    def register_deck(self, deck: str, websocket):
        if deck not in self.vd_ws_conn:
            self.vd_ws_conn[deck] = []
            logger.debug(f"{deck}: new registration")
            self.handle_code(1, deck)
        self.vd_ws_conn[deck].append(websocket)
        logger.debug(f"{deck}: registration added ({len(self.vd_ws_conn[deck])})")

    def is_closed(self, ws):
        return ws.__dict__.get("environ").get("werkzeug.socket").fileno() < 0  # there must be a better way to do this...

    def remove(self, websocket):
        # we unfortunately have to scan all decks to find the ws to remove
        #
        for deck in self.vd_ws_conn:
            remove = []
            for ws in deck:
                if ws == websocket:
                    remove.append(websocket)
            for ws in remove:
                deck.remove(ws)
        for deck in self.vd_ws_conn:
            if len(self.vd_ws_conn[deck]) == 0:
                self.handle_code(2, deck)

    def send(self, deck, payload):
        client_list = self.vd_ws_conn.get(deck)
        closed_ws = []
        if client_list is not None:
            for ws in client_list:  # send to each instance of this deck connected to this websocket server
                if self.is_closed(ws):
                    closed_ws.append(ws)
                    continue
                ws.send(json.dumps(payload))
                logger.debug(f"sent for {deck}")
            if len(closed_ws) > 0:
                for ws in closed_ws:
                    client_list.remove(ws)
        else:
            if deck not in self.vd_errs:
                logger.warning(f"no client for {deck}")
                self.vd_errs.append(deck)
