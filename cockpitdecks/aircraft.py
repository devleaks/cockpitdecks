# Aircraft configuration
#
from __future__ import annotations
import logging
import os
import threading
import pickle

from typing import Dict, Tuple

from PIL import Image, ImageFont
from cairosvg import svg2png

from cockpitdecks import (
    # Constants, keywords
    AIRCRAFT_ASSET_PATH,
    AIRCRAFT_CHANGE_MONITORING_DATAREF,
    COCKPITDECKS_ASSET_PATH,
    CONFIG_FILE,
    CONFIG_FILENAME,
    CONFIG_FOLDER,
    CONFIG_KW,
    DECK_KW,
    DECK_TYPES,
    DECKS_FOLDER,
    DEFAULT_LABEL_SIZE,
    DEFAULT_FREQUENCY,
    DEFAULT_LAYOUT,
    EXCLUDE_DECKS,
    FONTS_FOLDER,
    ICONS_FOLDER,
    ID_SEP,
    NAMED_COLORS,
    OBSERVABLES_FILE,
    RESOURCES_FOLDER,
    SECRET_FILE,
    SOUNDS_FOLDER,
    SPAM,
    SPAM_LEVEL,
    VIRTUAL_DECK_DRIVER,
    # Classes
    Config,
    yaml,
)
from cockpitdecks.resources.color import has_ext
from cockpitdecks.resources.intvariables import INTERNAL_DATAREF

from cockpitdecks.observable import Observables

from cockpitdecks.decks.resources import DeckType

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


# #################################
#
# Global constants
#
# IMPORTANT: These are rendez-vous point for JavaScript code
# If changed here, please adjust JavaScript Code too.
#
DECK_TYPE_ORIGINAL = "deck-type-desc"
DECK_TYPE_DESCRIPTION = "deck-type-flat"

# Aircraft change detection
# Why livery? because this dataref is an o.s. PATH! So it contains not only the livery
# (you may want to change your cockpit texture to a pinky one for this Barbie Livery)
# but also the aircraft. So in 1 dataref, 2 informations: aircraft and livery!
RELOAD_ON_LIVERY_CHANGE = False
INTERNAL_AIRCRAFT_CHANGE_DATAREF = "_livery"  # dataref name is data:_livery

# Little internal kitchen for internal datarefs
AIRCRAF_CHANGE_SIMULATOR_DATA = {CONFIG_KW.STRING_PREFIX.value + AIRCRAFT_CHANGE_MONITORING_DATAREF}


class Aircraft:
    """
    Contains all deck configurations for a given aircraft.
    Is started when aicraft is loaded and aircraft contains CONFIG_FOLDER folder.
    """

    def __init__(self, acpath: str, cockpit: "Cockpit"):
        self.cockpit = cockpit

        self._config = {}  # content of aircraft/deckconfig/config.yaml
        self._secret = {}  # content of aircraft/deckconfig/secret.yaml

        # "Aircraft" name or model...
        self._ac_ready = False
        self.name = "Aircraft"
        self.icao = "ZZZZ"

        # Decks
        self.decks = {}  # all decks: { deckname: deck }
        self.virtual_deck_list = {}
        self.virtual_decks_added = False

        # Content
        self._ac_fonts = {}
        self._ac_sounds = {}
        self._ac_icons = {}
        self._ac_observables = []

        # Internal variables
        self._livery_dataref = None  # self.sim.get_internal_variable(INTERNAL_AIRCRAFT_CHANGE_DATAREF, is_string=True)
        self._acname = ""
        self._livery_path = ""
        self._livery_config = {}  # content of <livery path>/deckconfig.yaml, to change color for example, to match livery!

        self.default_pages = None  # current pages on decks when reloading

        self.acpath = acpath

        self.init()  # this will install all available simulators

    @property
    def acpath(self):
        return self._acpath

    @acpath.setter
    def acpath(self, acpath: str | None):
        self._acpath = acpath
        logger.info(f"aircraft path set to {acpath}")

    def aircraft_ready(self) -> bool:
        return self._ac_ready

    def init(self):
        if self.acpath is not None:
            self.load_ac_resources()

    def get_button_value(self, name):
        a = name.split(ID_SEP)
        if len(a) > 0:
            if a[0] == self.name:
                if a[1] in self.decks.keys():
                    return self.decks[a[1]].get_button_value(ID_SEP.join(a[1:]))
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
        for v in self.decks.values():
            v.inspect(what)

    def load_pages(self):
        if self.default_pages is not None:
            logger.debug(f"default_pages {self.default_pages.keys()}")
            for name, deck in self.decks.items():
                if name in self.default_pages.keys():
                    if self.default_pages[name] in deck.pages.keys() and deck.home_page is not None:  # do not refresh if no home page loaded...
                        deck.change_page(self.default_pages[name])
                    else:
                        deck.change_page()
            self.default_pages = None
        else:
            for deck in self.decks.values():
                deck.change_page()

    def reload_pages(self):
        self.inc(INTERNAL_DATAREF.COCKPITDECK_RELOADS.value)
        for name, deck in self.decks.items():
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
                test = ImageFont.truetype(fontname, self.get_attribute("label-size", DEFAULT_LABEL_SIZE))
                logger.debug(f"font {fontname} found in computer system fonts")
                return fontname
            except:
                logger.debug(f"font {fontname} not found in computer system fonts")

            # 2. Try font in resources folder
            fn = None
            try:
                fn = os.path.join(os.path.dirname(__file__), RESOURCES_FOLDER, fontname)
                test = ImageFont.truetype(fn, self.get_attribute("label-size", DEFAULT_LABEL_SIZE))
                logger.debug(f"font {fontname} found locally ({RESOURCES_FOLDER} folder)")
                return fn
            except:
                logger.debug(f"font {fontname} not found locally ({RESOURCES_FOLDER} folder)")

            # 3. Try font in resources/fonts folder
            fn = None
            try:
                fn = os.path.join(os.path.dirname(__file__), RESOURCES_FOLDER, FONTS_FOLDER, fontname)
                test = ImageFont.truetype(fn, self.get_attribute("label-size", DEFAULT_LABEL_SIZE))
                logger.debug(f"font {fontname} found locally ({FONTS_FOLDER} folder)")
                return fn
            except:
                logger.debug(f"font {fontname} not found locally ({FONTS_FOLDER} folder)")

            logger.debug(f"font {fontname} not found")
            return None

        # Load global defaults from resources/config.yaml file or use application default
        fn = os.path.join(os.path.dirname(__file__), RESOURCES_FOLDER, CONFIG_FILE)
        self._resources_config = Config(fn)
        if not self._resources_config.is_valid():
            logger.error(f"configuration file {fn} is not valid")

        self._debug = self._resources_config.get("debug", ",".join(self._debug)).split(",")
        self.set_logging_level(__name__)

        if self.sim is not None:
            self.sim.set_simulator_variable_roundings(self._resources_config.get("dataref-roundings", {}))
            self.sim.set_simulator_variable_frequencies(simulator_variable_frequencies=self._resources_config.get("dataref-fetch-frequencies", {}))

        # XXX
        # Check availability of expected default fonts
        dftname = self.get_attribute("icon-name")
        if dftname in self.icons.keys():
            logger.debug(f"default icon name {dftname} found")
        else:
            logger.warning(f"default icon name {dftname} not found")

        # Default font for Pillow
        #   WE MUST find a default, system font at least
        default_label_font = self.get_attribute("label-font")
        if default_label_font is not None:
            if default_label_font not in self._cd_fonts.keys():
                f = locate_font(default_label_font)
                if f is not None:  # found one, perfect
                    self._cd_fonts[default_label_font] = f
                    self.set_default("default-font", default_label_font)
                    logger.debug(f"default font set to {default_label_font}")
                    logger.debug(f"default label font set to {default_label_font}")
                    logger.info(f"added default label font {default_label_font}")
            else:
                logger.debug(f"default label font is {default_label_font}")
        else:
            logger.warning("no default label font specified")

        default_system_font = self.get_attribute("system-font")
        if default_system_font is not None:
            if default_system_font not in self._cd_fonts.keys():
                f = locate_font(default_system_font)
                if f is not None:  # found it, perfect, keep it as default font for all purposes
                    self._cd_fonts[default_system_font] = f
                    self.set_default("default-font", default_system_font)
                    logger.debug(f"default font set to {default_system_font}")
                    if default_label_font is None:  # additionnally, if we don't have a default label font, use it
                        self.set_default("default-label-font", default_system_font)
                        logger.debug(f"default label font set to {default_system_font}")
                    logger.info(f"added default system font {default_system_font}")
            else:
                logger.debug(f"default system font is {default_system_font}")
        else:
            logger.warning("no default system font specified")

        # rebuild font list
        self.fonts = self._cd_fonts | self._ac_fonts

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

    def scan_web_decks(self):
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
        virtual_deck_types = {d.name: d for d in filter(lambda d: d.is_virtual_deck(), self.deck_types.values())}
        builder = self.all_deck_drivers.get(VIRTUAL_DECK_DRIVER)
        decks = builder[1]().enumerate(acpath=self.acpath, virtual_deck_types=virtual_deck_types)
        logger.info(f"found {len(decks)} virtual deck(s)")
        for name, device in decks.items():
            serial = device.get_serial_number()
            if serial in EXCLUDE_DECKS:
                logger.warning(f"deck {serial} excluded")
                del decks[name]
            logger.info(f"added virtual deck {name}, type {device.virtual_deck_config.get('type', 'type-not-found')}, serial {serial})")
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

    def remove_web_decks(self):
        if not self.virtual_decks_added:
            logger.info("virtual decks not added")
            return
        to_remove = []
        for device in self.devices:
            if device.get(CONFIG_KW.DRIVER.value) == VIRTUAL_DECK_DRIVER:
                to_remove.append(device)
        for device in to_remove:
            self.devices.remove(device)
        self.virtual_decks_added = False
        logger.info(f"removed {len(to_remove)} virtual decks")

    def create_decks(self):
        fn = os.path.join(self.acpath, CONFIG_FOLDER, CONFIG_FILE)
        self._config = Config(fn)
        if not self._config.is_valid():
            logger.warning(f"no config file {fn} or file is invalid")
            return
        self.named_colors.update(self._config.get(CONFIG_KW.NAMED_COLORS.value, {}))
        if (n := len(self.named_colors)) > 0:
            logger.info(f"{n} named colors ({', '.join(self.named_colors)})")

        before = self.theme
        theme = self.get_attribute(CONFIG_KW.COCKPIT_THEME.value)
        if self.theme is None:
            self.theme = theme
        elif self.theme in ["", "default", "cockpit"]:
            self.theme = theme
        logger.info(f"theme is {self.theme} (was {before})")

        sn = os.path.join(self.acpath, CONFIG_FOLDER, SECRET_FILE)
        serial_numbers = Config(sn)
        if not serial_numbers.is_valid():
            self._secret = {}
            logger.warning(f"secret file {sn} is not valid")
        else:
            self._secret = serial_numbers

        # 1. Adjust some settings in global config file.
        if self.sim is not None:
            self.sim.set_simulator_variable_roundings(self._config.get("dataref-roundings", {}))
            self.sim.set_simulator_variable_frequencies(simulator_variable_frequencies=self._config.get("dataref-fetch-frequencies", {}))
            self.sim.DEFAULT_REQ_FREQUENCY = self._config.get("dataref-fetch-frequency", DEFAULT_FREQUENCY)

        # 2. Create decks
        decks = self._config.get(CONFIG_KW.DECKS.value)
        if decks is None:
            logger.warning(f"no deck in config file {fn}")
            return

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
            if type(disabled) is not bool:
                if type(disabled) is str:
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

            deck_driver = self.deck_types[deck_type].get(CONFIG_KW.DRIVER.value)
            if deck_driver not in self.all_deck_drivers.keys():
                logger.warning(f"invalid deck driver {deck_driver}, ignoring")
                continue

            serial = deck_config.get(CONFIG_KW.SERIAL.value)
            if serial is None:
                if deck_driver == VIRTUAL_DECK_DRIVER:
                    serial = name
                else:  # get it from the secret file
                    serial = serial_numbers.get(name)

            # if serial is not None:
            device = self.get_device(req_driver=deck_driver, req_serial=serial)
            if device is not None:
                #
                if serial is None:
                    if deck_count_by_type[deck_type] > 1:
                        logger.warning(
                            "only one deck of that type but more than one configuration in config.yaml for decks of that type and no serial number, ignoring"
                        )
                        continue
                    deck_config[CONFIG_KW.SERIAL.value] = device.get_serial_number()  # issue: might return None?
                    logger.info(f"deck {deck_type} {name} has serial {deck_config[CONFIG_KW.SERIAL.value]}")
                else:
                    deck_config[CONFIG_KW.SERIAL.value] = serial
                if name not in self.decks.keys():
                    self.decks[name] = self.all_deck_drivers[deck_driver][0](name=name, config=deck_config, cockpit=self, device=device)
                    if deck_driver == VIRTUAL_DECK_DRIVER:
                        deck_flat = self.deck_types.get(deck_type).desc()
                        if DECK_KW.BACKGROUND.value in deck_flat and DECK_KW.IMAGE.value in deck_flat[DECK_KW.BACKGROUND.value]:
                            background = deck_flat[DECK_KW.BACKGROUND.value]
                            fn = background[DECK_KW.IMAGE.value]
                            if self.deck_types.get(deck_type)._aircraft:
                                if not fn.startswith(AIRCRAFT_ASSET_PATH):
                                    background[DECK_KW.IMAGE.value] = AIRCRAFT_ASSET_PATH + fn
                            else:
                                if not fn.startswith(COCKPITDECKS_ASSET_PATH):
                                    background[DECK_KW.IMAGE.value] = COCKPITDECKS_ASSET_PATH + fn
                        self.virtual_deck_list[name] = deck_config | {
                            DECK_TYPE_ORIGINAL: self.deck_types.get(deck_type).store,
                            DECK_TYPE_DESCRIPTION: deck_flat,
                        }
                    cnt = cnt + 1
                    deck_layout = deck_config.get(DECK_KW.LAYOUT.value, DEFAULT_LAYOUT)
                    logger.info(f"deck {name} added ({deck_type}, driver {deck_driver}, layout {deck_layout})")
                else:
                    logger.warning(f"deck {name} already exist, ignoring")
            else:
                logger.error(f"deck {deck_type} {name} has no device, ignoring")

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
            if deckdriver not in self.all_deck_drivers.keys():
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
            self.decks[name] = self.all_deck_drivers[deckdriver][0](name, config, self, device)

    # #########################################################
    # Cockpit data caches
    #
    def load_ac_deck_types(self):
        aircraft_deck_types = os.path.abspath(os.path.join(self.acpath, CONFIG_FOLDER, RESOURCES_FOLDER, DECKS_FOLDER, DECK_TYPES))
        added = []
        for deck_type in DeckType.list(aircraft_deck_types):
            b = os.path.basename(deck_type)
            if b in [CONFIG_FILE, "designer.yaml"]:
                continue
            try:
                data = DeckType(deck_type)
                data._aircraft = True  # mark as non-system deck type
                self.deck_types[data.name] = data
                if data.is_virtual_deck():
                    self.virtual_deck_types[data.name] = data.get_virtual_deck_layout()
                added.append(data.name)
            except ValueError:
                logger.warning(f"could not load deck type {deck_type}, ignoring")
        logger.info(f"added {len(added)} aircraft deck types ({', '.join(added)})")

    def load_ac_resources(self):
        # currently, nothing is not with this config, but it is loaded if it exists
        livery = self.cockpit._livery_dataref.value()
        if self.acpath is not None and livery is not None and livery != "":
            fn = os.path.join(self.acpath, "liveries", livery, CONFIG_FOLDER, CONFIG_FILE)
            if os.path.exists(fn):
                self._livery_config = Config(filename=fn)
                logger.info(f"loaded livery configuration from {fn}")
            else:
                logger.info("livery has no configuration")
        else:
            logger.info("no livery path")
        self.load_ac_deck_types()
        self.load_ac_fonts()
        self.load_ac_icons()
        self.load_ac_sounds()
        self.load_ac_observables()

    def load_ac_icons(self):
        # Loading aircraft icons
        #
        cache_icon = self.get_attribute("cache-icon")
        dn = os.path.join(self.acpath, CONFIG_FOLDER, RESOURCES_FOLDER, ICONS_FOLDER)
        if os.path.exists(dn):
            cache = os.path.join(dn, "_icon_cache.pickle")
            if os.path.exists(cache) and cache_icon:
                with open(cache, "rb") as fp:
                    self._ac_icons = pickle.load(fp)
                logger.info(f"{len(self._ac_icons)} aircraft icons loaded from cache")
            else:
                icons = os.listdir(dn)
                for i in icons:
                    fn = os.path.join(dn, i)
                    if has_ext(i, "png"):  # later, might load JPG as well.
                        image = Image.open(fn)
                        self._ac_icons[i] = image
                    elif has_ext(i, "svg"):  # Wow.
                        try:
                            fn = os.path.join(dn, i)
                            fout = fn.replace(".svg", ".png")
                            svg2png(url=fn, write_to=fout)
                            image = Image.open(fout)
                            self._ac_icons[i] = image
                        except:
                            logger.warning(f"could not load icon {fn}")
                            pass  # no cairosvg

                if cache_icon:  # we cache both folders of icons
                    with open(cache, "wb") as fp:
                        pickle.dump(self._ac_icons, fp)
                    logger.info(f"{len(self._ac_icons)} aircraft icons cached")
                else:
                    logger.info(f"{len(self._ac_icons)} aircraft icons loaded")

        self.icons = self._cd_icons | self._ac_icons
        logger.info(f"{len(self.icons)} icons available")

        dftname = self.get_attribute("icon-name")
        if dftname in self.icons.keys():
            logger.debug(f"default icon name {dftname} found")
        else:
            logger.warning(f"default icon name {dftname} not found")  # that's ok

    def load_ac_fonts(self):
        # Loading fonts.
        # For custom fonts (fonts found in the fonts config folder),
        # we supply the full path for font definition to ImageFont.
        # For other fonts, we assume ImageFont will search at OS dependent folders or directories.
        # If the font is not found by ImageFont, we ignore it.
        # So self.icons is a list of properly located usable fonts.
        #
        dn = os.path.join(self.acpath, CONFIG_FOLDER, RESOURCES_FOLDER, FONTS_FOLDER)
        if os.path.exists(dn):
            fonts = os.listdir(dn)
            for i in fonts:
                if has_ext(i, ".ttf") or has_ext(i, ".otf"):
                    if i not in self._ac_fonts.keys():
                        fn = os.path.join(dn, i)
                        try:
                            test = ImageFont.truetype(fn, self.get_attribute("label-size", DEFAULT_LABEL_SIZE))
                            self._ac_fonts[i] = fn
                        except:
                            logger.warning(f"aircraft font file {fn} not loaded")
                    else:
                        logger.debug(f"aircraft font {i} already loaded")

        logger.info(f"{len(self._ac_fonts)} aircraft fonts loaded")
        self.fonts = self._cd_fonts | self._ac_fonts
        logger.info(f"{len(self.fonts)} fonts available")

    def load_ac_sounds(self):
        # Loading sounds.
        #
        dn = os.path.join(self.acpath, CONFIG_FOLDER, RESOURCES_FOLDER, SOUNDS_FOLDER)
        if os.path.exists(dn):
            sounds = os.listdir(dn)
            for i in sounds:
                if has_ext(i, ".wav") or has_ext(i, ".mp3"):
                    if i not in self._ac_sounds.keys():
                        fn = os.path.join(dn, i)
                        try:
                            with open(fn, mode="rb") as file:  # b is important -> binary
                                self._ac_sounds[i] = file.read()
                        except:
                            logger.warning(f"custom sound file {fn} not loaded")
                    else:
                        logger.debug(f"sound {i} already loaded")

        logger.info(f"{len(self._ac_sounds)} aircraft sounds loaded")
        self.sounds = self._cd_sounds | self._ac_sounds
        logger.info(f"{len(self.sounds)} sounds available")

    def load_ac_observables(self):
        fn = os.path.abspath(os.path.join(self.acpath, CONFIG_FOLDER, RESOURCES_FOLDER, OBSERVABLES_FILE))
        if os.path.exists(fn):
            config = {}
            with open(fn, "r") as fp:
                config = yaml.load(fp)
            self._ac_observables = Observables(config=config, simulator=self.sim)
            self.observables = {o.name: o for o in self._cd_observables.observables} | {o.name: o for o in self._ac_observables.observables}
            logger.info(f"loaded {len(self._ac_observables.observables)} aircraft observables")
            logger.info(f"{len(self.observables)} observables")

    # #########################################################
    # Other
    #
    def reload_deck(self, deck_name: str, just_do_it: bool = False):
        """
        Development function to reload page yaml without leaving the page
        for one deck only .Should not be used in production.
        """
        # A security... if we get called we must ensure reloader is running...
        if just_do_it:
            deck = self.decks.get(deck_name)
            if deck is None:
                logger.info(f"deck {deck_name} not found")
                return
            logger.info(f"reloading deck {deck.name}..")
            self.busy_reloading = True
            self.default_pages = {}  # {deck_name: currently_loaded_page_name}
            if deck.current_page is not None:
                self.default_pages[deck.name] = deck.current_page.name

            # self.load_aircraft(self.acpath)  # will terminate it before loading again
            logger.debug("..terminating current version..")
            deck.terminate()
            logger.debug("..creating new version..")
            name = deck.name
            # find deck in config.yaml.decks
            deck_config = None
            all_decks = self._config.get(CONFIG_KW.DECKS.value)
            i = 0
            while deck_config is None and i < len(all_decks):
                if all_decks[i].get(CONFIG_KW.NAME.value, "") == name:
                    deck_config = all_decks[i]
                i = i + 1
            if deck_config is None:
                logger.info(f"deck {deck_name} not found in cockpit")
                return
            # get details
            serial = deck_config.get(CONFIG_KW.SERIAL.value)
            deck_type = deck_config.get(CONFIG_KW.TYPE.value)
            if deck_type not in self.deck_types.keys():
                logger.warning(f"invalid deck type {deck_type}, ignoring")
                return
            deck_driver = self.deck_types[deck_type].get(CONFIG_KW.DRIVER.value)
            device = self.get_device(req_driver=deck_driver, req_serial=serial)
            # recreate
            deck = self.all_deck_drivers[deck_driver][0](name=name, config=deck_config, cockpit=self, device=device)
            del self.decks[name]
            self.decks[name] = deck

            # reload
            if self.default_pages[name] in deck.pages.keys() and deck.home_page is not None:
                deck.change_page(self.default_pages[name])
                self.default_pages = {}
            else:
                deck.change_page()

            self.busy_reloading = False
            logger.info("..done")
        else:
            self.event_queue.put(f"reload:{deck_name}")
            logger.info("enqueued")

    def reload_decks(self, just_do_it: bool = False):
        """
        Development function to reload page yaml without leaving the page
        Should not be used in production...
        """
        # A security... if we get called we must ensure reloader is running...
        if just_do_it:
            logger.info("reloading decks..")
            self.busy_reloading = True
            self.default_pages = {}  # {deck_name: currently_loaded_page_name}
            for name, deck in self.decks.items():
                if deck.current_page is not None:
                    self.default_pages[name] = deck.current_page.name
            self.load_aircraft(self.acpath)  # will terminate it before loading again
            self.busy_reloading = False
            logger.info("..done")
        else:
            self.event_queue.put("reload")
            logger.debug("enqueued")

    def stop_decks(self, just_do_it: bool = False):
        """
        Stop decks gracefully. Since it also terminates self.event_loop_thread we cannot wait for it
        since we are called from it ... So we just tell it to terminate.
        """
        if just_do_it:
            logger.info("stopping decks..")
            self.terminate_all()
        else:
            self.event_queue.put("stop")
            logger.debug("enqueued")

    def get_livery(self, path: str) -> str:
        return os.path.basename(os.path.normpath(path))

    def get_aircraft_home(self, path: str) -> str:
        return os.path.normpath(os.path.join(path, "..", ".."))

    def get_aircraft_name_from_livery_path(self, path: str) -> str:
        # Path is like Aircraft/Extra Aircraft/ToLiss A321/liveries/F Airways (OO-PMA)/
        return os.path.split(os.path.normpath(os.path.join(path, "..", "..")))[1]

    def get_aircraft_name_from_aircraft_path(self, path: str) -> str:
        # Path is like Aircraft/Extra Aircraft/ToLiss A321/
        return os.path.basename(path)

    def get_aircraft_path(self, aircraft) -> str | None:
        for base in self.cockpit.cockpitdecks_path.split(":"):
            ac = os.path.join(base, aircraft)
            if os.path.exists(ac) and os.path.isdir(ac):
                ac_cfg = os.path.join(ac, CONFIG_FOLDER)
                if os.path.exists(ac_cfg) and os.path.isdir(ac_cfg):
                    logger.info(f"aircraft path found in COCKPITDECKS_PATH: {ac}, with deckconfig")
                    return ac
        logger.info(f"aircraft {aircraft} not found in COCKPITDECKS_PATH={self.cockpit.cockpitdecks_path}")
        return None

    # #########################################################
    # Load, start and terminates
    #
    def start_aircraft(self, acpath: str, release: bool = False, mode: int = 0):
        """
        Loads decks for aircraft in supplied path and start listening for key presses.
        """
        self.mode = mode
        self.load_aircraft(acpath)

    def load_aircraft(self, acpath: str | None):
        """
        Loads decks for aircraft in supplied path.
        First unloads a previously loaded aircraft if any
        """
        if self.disabled:
            logger.warning("Cockpitdecks is disabled")
            return
        if acpath is None:
            logger.warning("no new aircraft path to load, not unloading current one")
            return
        # Reset, if new aircraft
        if len(self.decks) > 0:
            self.terminate_aircraft()
            # self.sim.clean_datarefs_to_monitor()
            logger.debug(f"{os.path.basename(self.acpath)} unloaded")

        if self.sim is None:
            logger.info("..starting simulator..")
            self.sim = self._simulator(self, self._environ)
        else:
            logger.debug("simulator already running")

        if not self._device_scanned:
            self.scan_devices()

        logger.info(f"starting aircraft {os.path.basename(acpath)} " + "✈ " * 30)  # unicode ✈ (U+2708)
        self.acpath = None

        if acpath is not None and os.path.exists(os.path.join(acpath, CONFIG_FOLDER)):
            self.acpath = acpath
            self._acname = self.get_aircraft_name_from_aircraft_path(acpath)
            logger.info(f"aircraft name set to {self._acname}")

            self.load_aircraft_deck_types()
            self.scan_web_decks()

            if len(self.devices) == 0:
                logger.warning("no device")
                return

            self.load_ac_resources()
            self.create_decks()
            self.load_pages()
            self._ac_ready = True
        else:
            if acpath is None:
                logger.error(f"no aircraft folder")
            elif not os.path.exists(acpath):
                logger.error(f"no aircraft folder {acpath}")
            else:
                logger.error(f"no Cockpitdecks folder '{CONFIG_FOLDER}' in aircraft folder {acpath}")
            self.create_default_decks()
        logger.info(f"..aircraft {os.path.basename(acpath)} started")

    def change_aircraft(self):
        data = self.sim.all_simulator_variable.get(AIRCRAFT_CHANGE_MONITORING_DATAREF)
        if data is None:
            logger.warning(f"no dataref {AIRCRAFT_CHANGE_MONITORING_DATAREF}, ignoring")
            return

        value = data.value()
        if value is None or type(value) is not str:
            logger.warning(f"livery path invalid value {value}, ignoring")
            return

        if self._livery_path == value:
            logger.info(f"livery path unchanged {self._livery_path}")
            return

        if self.mode > 0 and not RELOAD_ON_LIVERY_CHANGE:
            logger.info("Cockpitdecks in demontration mode or aircraft fixed, aircraft not adjusted")
            return

        acname = self.get_aircraft_name_from_livery_path(value)
        new_livery = self.get_livery(value)
        if self.mode > 0 and RELOAD_ON_LIVERY_CHANGE:  # only change livery and reloads
            if self._acname != acname:
                # ac has changed, refused
                logger.info("Cockpitdecks in demontration mode or aircraft fixed, aircraft not adjusted")
                return
            # ac has not changed, livery has
            logger.info("Cockpitdecks in demontration mode or aircraft fixed, aircraft not adjusted but livery changed")
            self._livery_path = value
            # Adjustment of livery
            old_livery = self._livery_dataref.value()
            if old_livery is None:
                self._livery_dataref.update_value(new_value=new_livery, cascade=True)
                logger.info(f"initial aircraft livery set to {new_livery}")
            elif old_livery != new_livery:
                self._livery_dataref.update_value(new_value=new_livery, cascade=True)
                logger.info(f"new aircraft livery {new_livery} (former was {old_livery})")
            self.reload_decks()
            return

        if self._acname != acname:
            # change livery
            self._livery_path = value
            old_livery = self._livery_dataref.value()
            if old_livery is None or old_livery == "":
                self._livery_dataref.update_value(new_value=new_livery, cascade=True)
                logger.info(f"initial aircraft livery set to {new_livery}")
            else:
                self._livery_dataref.update_value(new_value=new_livery, cascade=True)
                logger.info(f"new aircraft livery {new_livery} (former was {old_livery})")
            # change aircraft
            old_acname = self._acname
            self._acname = acname
            logger.info(f"aircraft name set to {self._acname}")
            new_ac = self.get_aircraft_path(self._acname)
            if new_ac is not None and self.acpath != new_ac:
                logger.debug(f"aircraft path: current {self.acpath}, new {new_ac} (former was {old_acname})")
                logger.info(f"livery changed to {new_livery}, aircraft changed to {new_ac}, loading new aircraft")
                self.load_aircraft(acpath=new_ac)
        else:
            logger.info(f"aircraft unchanged ({self._acname}, {self.acpath})")

    def terminate_aircraft(self):
        logger.info("terminating aircraft..")
        drefs = {d.name: d.value() for d in self.sim.all_simulator_variable.values()}  #  if d.is_internal
        fn = "datarefs-log.yaml"
        with open(fn, "w") as fp:
            yaml.dump(drefs, fp)
            logger.debug(f"..simulator data values saved in {fn} file")
        logger.info("..terminating decks..")
        self._ac_ready = False
        for deck in self.decks.values():
            deck.terminate()
        logger.info("..terminating web decks..")
        self.remove_web_decks()
        logger.info("..removing aircraft resources..")
        self.decks = {}
        self._ac_fonts = {}
        self._ac_icons = {}
        self._ac_sounds = {}
        self._ac_observables = {}
        nt = threading.enumerate()
        if len(nt) > 1:
            logger.info(f"{len(nt)} threads")
            logger.info(f"{[t.name for t in nt]}")
        logger.info(f"..aircraft {os.path.basename(self.acpath)} terminated " + "✈ " * 30)
