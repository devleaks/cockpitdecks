# Aircraft configuration: Loads main config.yaml file
# and instanciate decks.
# Link deck to device and start operation with it.
#
import logging
import os
import threading
import pickle

from PIL import Image, ImageFont
from cairosvg import svg2png

from cockpitdecks import (
    # Constants, keywords
    AIRCRAFT_ASSET_PATH,
    COCKPITDECKS_ASSET_PATH,
    CONFIG_FILE,
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
    OBSERVABLES_FILE,
    RESOURCES_FOLDER,
    SECRET_FILE,
    SOUNDS_FOLDER,
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


class Aircraft:
    """
    Contains all deck configurations for a given aircraft.
    Is started when aicraft is loaded and aircraft contains CONFIG_FOLDER folder.
    """

    def __init__(self, cockpit: "Cockpit"):
        self.cockpit = cockpit

        self._config = {}  # content of aircraft/deckconfig/config.yaml
        self._secret = {}  # content of aircraft/deckconfig/secret.yaml

        # "Aircraft" name or model...
        self.name = "Aircraft"
        self.icao = "ZZZZ"

        self._acpath = None
        self._acname = ""
        self._acliverypath = None
        self._acliveryname = None
        self._ac_running = False

        # Decks
        self.decks = {}  # all decks: { deckname: deck }
        self.virtual_decks = {}
        self.virtual_decks_added = False

        # Content
        self._ac_fonts = {}
        self._ac_sounds = {}
        self._ac_icons = {}
        self._ac_observables: Observables | None = None

        # Internal variables
        self._aircraft_variable_names = set()
        self._livery_config = {}  # content of <livery path>/deckconfig.yaml, to change color for example, to match livery!

        self.default_pages = None  # current pages on decks when reloading

    @property
    def acpath(self):
        return self._acpath

    @acpath.setter
    def acpath(self, acpath: str | None):
        self._acpath = acpath
        logger.info(f"aircraft path set to {acpath}")

    def is_running(self) -> bool:
        return self._ac_running

    # Shortcuts
    @property
    def sim(self):
        return self.cockpit.sim

    @property
    def all_deck_drivers(self):
        return self.cockpit.all_deck_drivers

    @property
    def devices(self):
        return self.cockpit.devices

    @property
    def deck_types(self):
        return self.cockpit.deck_types

    @property
    def virtual_deck_types(self):
        return self.cockpit.virtual_deck_types

    @property
    def named_colors(self):
        return self.cockpit.named_colors

    @property
    def theme(self):
        return self.cockpit.theme

    @theme.setter
    def theme(self, theme: str):
        self.cockpit.theme = theme

    def get_attribute(self, attribute: str, default=None, silence: bool = True):
        return self.cockpit.get_attribute(attribute=attribute, default=default, silence=silence)

    @property
    def fonts(self):
        return self._ac_fonts

    @property
    def sounds(self):
        return self._ac_sounds

    @property
    def icons(self):
        return self._ac_icons

    @property
    def observables(self):
        return self._ac_observables

    # Attributes
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

    def get_variables(self) -> set:
        """Returns the list of datarefs for which the cockpit wants to be notified."""
        return self._aircraft_variable_names

    # Initialisation, setup
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

    # #########################################################
    # Aircraft resources
    #
    def load_ac_resources(self):
        # currently, nothing is not with this config, but it is loaded if it exists
        self.load_livery_config()
        self.load_ac_deck_types()
        self.load_ac_fonts()
        self.load_ac_icons()
        self.load_ac_sounds()
        self.load_ac_observables()
        self.cockpit.add_resources(aircraft=self)

    def load_livery_config(self):
        # currently, nothing is not with this config, but it is loaded if it exists
        if self._acliverypath is not None and self._acliverypath != "":
            fn = os.path.join(self._acliverypath, CONFIG_FOLDER, CONFIG_FILE)
            if os.path.exists(fn):
                self._livery_config = Config(filename=fn)
                logger.info(f"loaded livery configuration from {fn}, currently unused...")
            else:
                logger.debug("livery has no configuration")
            return
        if self.acpath is not None and self._acliveryname is not None and self._acliveryname != "":
            fn = os.path.join(self.acpath, "liveries", self._acliveryname, CONFIG_FOLDER, CONFIG_FILE)
            if os.path.exists(fn):
                self._livery_config = Config(filename=fn)
                logger.info(f"loaded livery configuration from {fn}, currently unused...")
            else:
                logger.debug("livery has no configuration")
        else:
            logger.info("no livery path")

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

    def load_ac_observables(self):
        fn = os.path.abspath(os.path.join(self.acpath, CONFIG_FOLDER, RESOURCES_FOLDER, OBSERVABLES_FILE))
        if os.path.exists(fn):
            config = {}
            with open(fn, "r") as fp:
                config = yaml.load(fp)
            self._ac_observables = Observables(config=config, simulator=self.sim)
            logger.info(f"loaded {len(self._ac_observables.observables)} aircraft observables")

    # #########################################################
    # Utility functions for path manipulation
    #
    @staticmethod
    def get_livery_from_livery_path(path: str) -> str:
        return os.path.basename(os.path.normpath(path))

    @staticmethod
    def get_aircraft_path_from_livery_path(path: str) -> str:
        # Path is like Aircraft/Extra Aircraft/ToLiss A321/liveries/F Airways (OO-PMA)/
        return os.path.normpath(os.path.join(path, "..", ".."))

    @staticmethod
    def get_aircraft_name_from_livery_path(path: str) -> str:
        # Path is like Aircraft/Extra Aircraft/ToLiss A321/liveries/F Airways (OO-PMA)/
        return os.path.split(Aircraft.get_aircraft_path_from_livery_path(path=path))[1]

    @staticmethod
    def get_aircraft_name_from_aircraft_path(path: str) -> str:
        # Path is like Aircraft/Extra Aircraft/ToLiss A321/
        return os.path.basename(path)

    def change_livery(self, path) -> bool:
        if self._acliverypath is not None and self._acliverypath == path:
            logger.info(f"livery unchanged ({self._acliverypath})")
            return False
        oldlivery = self._acliveryname
        self._acliverypath = path
        self._acliveryname = Aircraft.get_livery_from_livery_path(path)
        self.load_livery_config()
        if oldlivery is None:
            logger.info(f"installed livery {self._acliveryname}")
            return False
        logger.info(f"changed livery from {oldlivery} to {self._acliveryname}")
        return True

    # #########################################################
    # Load, start and terminates
    #
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
        self.virtual_decks = {}

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
            device = self.cockpit.get_device(req_driver=deck_driver, req_serial=serial)
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
                    self.decks[name] = self.all_deck_drivers[deck_driver][0](name=name, config=deck_config, cockpit=self.cockpit, device=device)
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
                        self.virtual_decks[name] = deck_config | {
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

    def start(self, acpath: str):
        """
        Loads decks for aircraft in supplied path.
        First unloads a previously loaded aircraft if any
        """
        if acpath is None:
            logger.warning("no new aircraft path to load, not unloading current one")
            return

        if self.is_running:
            self.terminate()

        logger.info(f"starting aircraft {os.path.basename(acpath)} " + "✈ " * 30)  # unicode ✈ (U+2708)
        self.acpath = None

        # Note: Unfortunately, on first start, we cannot install a livery
        #       So we will not detect if we really change it.

        if acpath is not None and os.path.exists(os.path.join(acpath, CONFIG_FOLDER)):
            self.acpath = acpath
            self._acname = Aircraft.get_aircraft_name_from_aircraft_path(acpath)
            logger.info(f"aircraft name set to {self._acname}")

            self.load_ac_deck_types()
            self.scan_web_decks()

            if len(self.devices) == 0:
                logger.warning("no device")
                return

            self.load_ac_resources()
            self.create_decks()
            self.load_pages()
            self._ac_running = True
        else:
            if acpath is None:
                logger.error(f"no aircraft folder")
            elif not os.path.exists(acpath):
                logger.error(f"no aircraft folder {acpath}")
            else:
                logger.error(f"no Cockpitdecks folder '{CONFIG_FOLDER}' in aircraft folder {acpath}")
            self.create_default_decks()
        logger.info(f"..aircraft {os.path.basename(acpath)} started")

    def terminate(self):
        if not self.is_running():
            logger.info("aircraft not running, no termination necessary")
            return
        logger.info("terminating aircraft..")
        drefs = {d.name: d.value() for d in self.cockpit.variable_database.database.values()}  #  if d.is_internal
        fn = "datarefs-log.yaml"
        with open(fn, "w") as fp:
            yaml.dump(drefs, fp)
            logger.debug(f"..simulator data values saved in {fn} file")
        logger.info("..terminating decks..")
        self._ac_running = False
        for deck in self.decks.values():
            deck.terminate()
        logger.info("..terminating web decks..")
        self.remove_web_decks()
        logger.info("..removing aircraft resources..")
        self.decks = {}
        self._ac_fonts = {}
        self._ac_icons = {}
        self._ac_sounds = {}
        self._ac_observables = None
        self.cockpit.remove_aircraft_resources()
        logger.info("..remaining threads..")
        nt = threading.enumerate()
        if len(nt) > 1:
            logger.info(f"{len(nt)} threads")
            logger.info(f"{[t.name for t in nt]}")
        logger.info(f"..aircraft {os.path.basename(self.acpath)} terminated " + "✈ " * 30)
