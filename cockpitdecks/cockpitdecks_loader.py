# Main container for all decks
#
from __future__ import annotations
import sys
import logging
import os
import io
import glob
import base64
import threading
import pickle
import json
import itertools

from queue import Queue
from typing import Dict, Tuple, Set
from datetime import datetime

import importlib
import pkgutil

# External packages
from packaging.requirements import Requirement

from PIL import Image, ImageFont

from cairosvg import svg2png

# Internal packages
from cockpitdecks import __version__, LOGFILE, FORMAT
from cockpitdecks import (
    # Constants, keywords
    AIRCRAFT_ASSET_PATH,
    AIRCRAFT_CHANGE_MONITORING,
    AIRCRAFT_ICAO_MONITORING,
    LIVERY_CHANGE_MONITORING,
    ASSETS_FOLDER,
    COCKPITDECKS_ASSET_PATH,
    COCKPITDECKS_DEFAULT_VALUES,
    CONFIG_FILE,
    CONFIG_FILENAME,
    CONFIG_FOLDER,
    CONFIG_KW,
    DECK_ACTIONS,
    DECK_FEEDBACK,
    DECK_IMAGES,
    DECKS_FOLDER,
    DEFAULT_ATTRIBUTE_NAME,
    DEFAULT_ATTRIBUTE_PREFIX,
    DESIGNER_EXTENSION,
    COCKPITDECKS_INTERNAL_EXTENSIONS,
    ENVIRON_KW,
    EXCLUDE_DECKS,
    FONTS_FOLDER,
    ICONS_FOLDER,
    ID_SEP,
    OBSERVABLES_FILE,
    PERMANENT_COCKPITDECKS_NAMED_COLORS,
    PERMANENT_COCKPITDECKS_VARIABLE_NAMES,
    RESOURCES_FOLDER,
    RELOAD_ON_LIVERY_CHANGE,
    RELOAD_ON_ICAO_CHANGE,
    ROOT_DEBUG,
    SECRET_FILE,
    SOUNDS_FOLDER,
    SPAM,
    SPAM_LEVEL,
    VIRTUAL_DECK_DRIVER,
    # Classes
    Config,
    yaml,
)
from cockpitdecks.constant import TYPES_FOLDER
from cockpitdecks.resources.color import convert_color, has_ext, add_ext
from cockpitdecks.variable import Variable, VariableFactory, InternalVariable, VariableDatabase, InternalVariableType
from cockpitdecks.activity import ActivityDatabase, Activity, ActivityFactory
from cockpitdecks.simulator import Simulator
from cockpitdecks.observable import Observables, Observable
from cockpitdecks.decks.virtualdeck import VirtualDeck

#
# imports all known decks, DO NO REMOVE import
#
#
import cockpitdecks.decks

#
#

from cockpitdecks.deck import Deck
from cockpitdecks.decks.resources import DeckType
from cockpitdecks.buttons.activation import Activation
from cockpitdecks.buttons.representation import Representation, HardwareRepresentation
from cockpitdecks.aircraft import Aircraft
from cockpitdecks.cockpit import CockpitBase

# #################################
#
# Logging
#
logging.addLevelName(SPAM_LEVEL, SPAM)
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

if LOGFILE is not None:
    formatter = logging.Formatter(FORMAT)
    handler = logging.FileHandler(LOGFILE, mode="a")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

#
# ################################################


class CockpitdecksLoader(CockpitBase):
    """
    Common instances shared by all aircrafts/decks.
    Loads and starts a particular aircraft if requested.
    Main entry points to initialize, start (run()) and stop (terminate()) Cockpitdecks.
    """

    def __init__(self, environ: Config | dict):
        CockpitBase.__init__(self)

        self._startup_time = datetime.now()

        self.name = "CockpitdecksLoader"

        # Extensions (loaded, found, and "manually" added)
        self.extension_paths = environ.get(ENVIRON_KW.COCKPITDECKS_EXTENSION_PATH.value, set())
        if type(self.extension_paths) is str:
            if ":" in self.extension_paths:
                self.extension_paths = self.extension_paths.split(":")
            else:
                self.extension_paths = {self.extension_paths}
        self.extension_paths = set(self.extension_paths)

        self.all_extensions = environ.get(ENVIRON_KW.COCKPITDECKS_EXTENSION_NAME.value, set())
        if type(self.all_extensions) is str:
            self.all_extensions = {self.all_extensions}
        self.all_extensions = set(self.all_extensions)
        self.all_extensions.update(COCKPITDECKS_INTERNAL_EXTENSIONS)

        self.cockpitdecks_path = environ.get(ENVIRON_KW.COCKPITDECKS_PATH.value)

        # What's available
        self.all_deck_drivers = {}  # Dict[str, Device], one day
        self.all_simulators: Dict[str, Simulator] = {}
        self.all_activations: Dict[str, Activation] = {}
        self.all_representations: Dict[str, Representation] = {}
        self.all_hardware_representations: Dict[str, Representation] = {}

        # Defaults and config
        self._environ = environ

        self._defaults = COCKPITDECKS_DEFAULT_VALUES
        self._resources_config = {}  # content of resources/config.yaml
        self._reqdfts = set()

        self._livery_config = {}  # content of <livery path>/deckconfig.yaml, to change color for example, to match livery!

        # Decks
        self.deck_types = {}
        self.deck_types_new = {}
        self.virtual_deck_types = {}

        # Devices
        self.devices = []
        self._device_scanned = False

        # Virtual/Web devices
        self.vd_ws_conn = {}
        self.vd_errs = []

        # Global parameters that affect colors and deck LCD backlight
        self.global_luminosity = 1.0
        self.global_brightness = 1.0

        # Content (global, cockpit level)
        # Cockpit is permanent | Aircraft are changing
        self._fonts = {}
        self._sounds = {}
        self._icons = {}
        self._observables: Observables | None = None  # loaded from file

        self._permanent_observables = {}  # Subclasses of Observables, static, fixed after extension load

        # Cockpitdecks will listen to these variables as "rendez-vous" points
        # to be updated by extensions and other parties to "notify" Cockpitdecks of changes
        self._permanent_variable_names = PERMANENT_COCKPITDECKS_VARIABLE_NAMES
        self._permanent_variables = {}

        self.named_colors = PERMANENT_COCKPITDECKS_NAMED_COLORS
        self.theme = None

        self.fonts = {}
        self.sounds = {}
        self.icons = {}

        # Databases
        self.variable_database = VariableDatabase()
        self.activity_database = ActivityDatabase()
        self.observable_database: Dict[str, Observable] = {}

        # Main event look
        self.event_loop_run = False
        self.event_loop_thread = None
        self.event_queue = Queue()

        # Simulator
        self._simulator_name = environ.get(ENVIRON_KW.SIMULATOR_NAME.value)
        self._simulator = None
        self.sim: Simulator | None = None

        # "Aircraft" name or model...
        self.aircraft = Aircraft(cockpit=self)
        self.running = False  # flag to prevent multiple start/stop

        # Internal variables
        self.reload_operation = threading.Lock()

        self.default_pages = None  # current pages on decks when reloading
        self.client_list = None
        self.mode = 0  # CD_MODE: NORMAL = 0 (normal operation), DEMO = 1 (no aircraft, do not change aircraft), FIXED = 2 (do not change aircraft)

        self.activate_designer = False

        self.init()  # this will install all available simulators

    def get_id(self):
        return self.name

    # From the separation between cockpit/aircraft
    @property
    def decks(self):
        return self.aircraft.decks

    @property
    def virtual_decks(self):
        return self.aircraft.virtual_decks

    @property
    def _config(self):
        return self.aircraft._config

    @property
    def _secret(self):
        return self.aircraft._secret

    # Init, setup
    @staticmethod
    def all_subclasses(cls) -> list:
        """Returns the list of all subclasses.

        Recurses through all sub-sub classes

        Returns:
            [list]: list of all subclasses

        Raises:
            ValueError: If invalid class found in recursion (types, etc.)
        """
        if cls is type:
            raise ValueError("Invalid class - 'type' is not a class")
        subclasses = set()
        stack = []
        try:
            stack.extend(cls.__subclasses__())
        except (TypeError, AttributeError) as ex:
            raise ValueError("Invalid class" + repr(cls)) from ex
        while stack:
            sub = stack.pop()
            subclasses.add(sub)
            try:
                stack.extend(s for s in sub.__subclasses__() if s not in subclasses)
            except (TypeError, AttributeError):
                continue
        return list(subclasses)

    def add_extensions(self, trace_ext_loading: bool = False):
        # https://stackoverflow.com/questions/3365740/how-to-import-all-submodules
        def import_submodules(package, recursive=True):
            """Import all submodules of a module, recursively, including subpackages

            :param package: package (name or actual module)
            :type package: str | module
            :rtype: dict[str, types.ModuleType]
            """
            if isinstance(package, str):
                try:
                    if trace_ext_loading:
                        logger.info(f"loading package {package}")
                    package = importlib.import_module(package)
                except ModuleNotFoundError:
                    logger.warning(f"package {package} not found, ignored (may be path to module was not supplied or is not correct?)")
                    return {}

            results = {}
            for loader, name, is_pkg in pkgutil.walk_packages(package.__path__):
                full_name = package.__name__ + "." + name
                try:
                    results[full_name] = importlib.import_module(full_name)
                    if trace_ext_loading:
                        logger.info(f"loading module {full_name}")
                except ModuleNotFoundError:
                    logger.warning(f"module {full_name} not found, ignored", exc_info=True)
                    continue
                except:
                    logger.warning(f"module {full_name}: error", exc_info=True)
                    continue
                if recursive and is_pkg:
                    results.update(import_submodules(full_name))
            return results

        if self.extension_paths is not None:
            for path in self.extension_paths:
                pythonpath = os.path.abspath(path)
                if os.path.exists(pythonpath) and os.path.isdir(pythonpath):
                    if pythonpath not in sys.path:
                        sys.path.append(pythonpath)
                        arr = os.path.split(pythonpath)
                        self.all_extensions.add(arr[1])
                        if trace_ext_loading:
                            logger.info(f"added extension path {pythonpath} to sys.path")

        logger.debug(f"loading extensions {", ".join(self.all_extensions)}..")
        loaded = []
        for package in self.all_extensions:
            test = import_submodules(package)
            if len(test) > 0:
                logger.debug(f"loaded package {package}")  #  (recursively)
                loaded.append(package)
        logger.debug("..loaded")
        logger.info(f"loaded extensions {", ".join(loaded)}")

    def get_activations_for(self, action: DECK_ACTIONS) -> list:
        return [a for a in self.all_activations.values() if action in a.get_required_capability()]

    def get_representations_for(self, feedback: DECK_FEEDBACK):
        return [a for a in self.all_representations.values() if feedback in a.get_required_capability()]

    # #########################################################
    # Initialisation
    #
    def init(self):
        """
        Loads extensions, then build lists of available resources (simulators, decks, etc.)
        """
        show_details = False  # self._environ.verbose

        self.add_extensions(trace_ext_loading=show_details)

        for v in self._permanent_variable_names:
            intvar = self.get_variable(name=Variable.internal_variable_name(v), factory=self)
            intvar.add_listener(self)
            self._permanent_variables[v] = intvar
        logger.info(f"permanent variables: {', '.join([Variable.internal_variable_root_name(v) for v in self._permanent_variables.keys()])}")

        self.all_simulators = {s.name: s for s in CockpitdecksLoader.all_subclasses(Simulator)}
        logger.info(f"available simulators: {', '.join(self.all_simulators.keys())}")

        self.all_deck_drivers = {s.DECK_NAME: [s, s.DEVICE_MANAGER] for s in CockpitdecksLoader.all_subclasses(Deck) if s.DECK_NAME != "none"}
        logger.info(f"available deck drivers: {', '.join(self.all_deck_drivers.keys())}")

        # classes with NAME that ends with "-base" are considered "base" classes and should not be instancieted.
        self.all_activations = {s.name(): s for s in CockpitdecksLoader.all_subclasses(Activation) if not s.name().endswith("-base")} | {
            DECK_ACTIONS.NONE.value: Activation
        }
        if show_details:
            logger.info(f"available activations: {', '.join(sorted(self.all_activations.keys()))}")

        self.all_representations = {s.name(): s for s in CockpitdecksLoader.all_subclasses(Representation) if not s.name().endswith("-base")} | {
            DECK_FEEDBACK.NONE.value: Representation
        }
        if show_details:
            logger.info(f"available representations: {', '.join(sorted(self.all_representations.keys()))}")

        self.all_hardware_representations = {s.name(): s for s in CockpitdecksLoader.all_subclasses(HardwareRepresentation)}
        if show_details:
            logger.info(f"available hardware representations: {', '.join(self.all_hardware_representations.keys())}")

        self.load_resources()
        self.scan_devices()

    # #########################################################
    # Devices
    #
    def scan_devices(self):
        """Scan for hardware devices"""

        # ################################################
        # pkg_resources.require(dependencies)  # to be replace with importlib statements
        # See https://github.com/pypa/packaging-problems/issues/664
        # and https://github.com/HansBug/hbutils/blob/main/hbutils/system/python/package.py
        #
        def _yield_reqs_to_install(req: Requirement, current_extra: str = ""):
            if req.marker and not req.marker.evaluate({"extra": current_extra}):
                return

            try:
                version = importlib.metadata.distribution(req.name).version
            except importlib.metadata.PackageNotFoundError:  # req not installed
                yield req
            else:
                if req.specifier.contains(version):
                    for child_req in importlib.metadata.metadata(req.name).get_all("Requires-Dist") or []:
                        child_req_obj = Requirement(child_req)

                        need_check, ext = False, None
                        for extra in req.extras:
                            if child_req_obj.marker and child_req_obj.marker.evaluate({"extra": extra}):
                                need_check = True
                                ext = extra
                                break

                        if need_check:  # check for extra reqs
                            yield from _yield_reqs_to_install(child_req_obj, ext)

                else:  # main version not match
                    yield req

        def _check_req(req: Requirement):
            return not bool(list(itertools.islice(_yield_reqs_to_install(req), 1)))

        def check_reqs(reqs: List[str]) -> bool:
            """
            Overview:
                Check if the given requirements are all satisfied.

            :param reqs: List of requirements.
            :return satisfied: All the requirements in ``reqs`` satisfied or not.

            Examples::
                >>> from hbutils.system import check_reqs
                >>> check_reqs(['pip>=20.0'])
                True
                >>> check_reqs(['pip~=19.2'])
                False
                >>> check_reqs(['pip>=20.0', 'setuptools>=50.0'])
                True

            .. note::
                If a requirement's marker is not satisfied in this environment,
                **it will be ignored** instead of return ``False``.
            """
            return all(map(lambda x: _check_req(Requirement(x)), reqs))

        if len(self.all_deck_drivers) == 0:
            logger.error("no driver")
            return
        driver_info = []
        for deck_driver in self.all_deck_drivers:
            try:
                desc = f"{deck_driver} {importlib.metadata.version(deck_driver)}"
                driver_info.append(desc)
            except:
                if deck_driver == VirtualDeck.DRIVER_NAME:
                    desc = f"{deck_driver} {VirtualDeck.DRIVER_VERSION}"
                    driver_info.append(desc)
                    continue
                logger.warning(f"no driver information for {deck_driver}")
        if len(driver_info) == 0:
            logger.warning("no device driver for physical decks")
            return

        logger.info(f"device drivers installed for {', '.join(driver_info)}")
        logger.info("scanning for decks and initializing them (this may take a few seconds)..")

        dependencies = []
        for name, deck_driver in self.all_deck_drivers.items():
            if name == "virtualdeck":
                continue
            dep = ""
            try:
                dep = f"{deck_driver[0].DRIVER_NAME}>={deck_driver[0].MIN_DRIVER_VERSION}"
            except:
                logger.warning(f"no driver information for {name}", exc_info=True)
            if dep != "":
                dependencies.append(dep)
        logger.debug(f"dependencies: {dependencies}")
        if len(dependencies) > 0:
            check_reqs(dependencies)
            logger.info(f"requirements {';'.join(dependencies)} satified")
            # pkg_resources.require(dependencies)  # to be replace with importlib statements

        # If there are already some devices, we need to terminate/kill them first
        if len(self.devices) > 0:
            logger.info("new scan for devices, terminating previous devices..")
            self.terminate_devices()
            self._device_scanned = False
            logger.info("..previous devices terminated")

        self.devices = []
        for deck_driver, builder in self.all_deck_drivers.items():
            if deck_driver == VIRTUAL_DECK_DRIVER:
                # will be added later, when we have acpath set, in add virtual_decks()
                continue
            decks = builder[1]().enumerate()
            logger.info(f"found {len(decks)} {deck_driver}")
            for name, device in enumerate(decks):
                device.open()
                serial = device.get_serial_number()
                device.close()
                if serial in EXCLUDE_DECKS:
                    logger.warning(f"deck {serial} excluded")
                    del decks[name]
                if self._environ.verbose:
                    logger.info(f"added {type(device).__name__} (driver {deck_driver}, serial {serial[:3]}{'*'*max(1,len(serial))})")
                self.devices.append(
                    {
                        CONFIG_KW.DRIVER.value: deck_driver,
                        CONFIG_KW.DEVICE.value: device,
                        CONFIG_KW.SERIAL.value: serial,
                    }
                )
            logger.debug(f"using {len(decks)} {deck_driver}")
        self._device_scanned = True

        logger.debug(f"..scanned")

    def get_device(self, req_driver: str, req_serial: str | None):
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
                device.reset()
                return device
            else:
                if i > 1:
                    logger.warning(f"more than one deck of type {req_driver}, no serial to disambiguate")
                    deckdr = filter(
                        lambda d: d[CONFIG_KW.DRIVER.value] == req_driver and d[CONFIG_KW.SERIAL.value] is None,
                        self.devices,
                    )
                    logger.warning(f"driver: {req_driver}, decks with no serial: {[d[CONFIG_KW.DEVICE.value].name for d in deckdr]}")
            return None
        ## Got serial, search for it
        for deck in self.devices:
            if deck[CONFIG_KW.SERIAL.value] == req_serial:
                device = deck[CONFIG_KW.DEVICE.value]
                device.open()
                device.reset()
                return device
        logger.warning(f"deck with driver {req_driver} and serial '{req_serial}' not found")
        return None

    # #########################################################
    # Variables and Events
    #
    def get_activities(self) -> set:
        ret = set()
        if type(self.observables) is Observables:
            obs = self.observables.get_activities()
            if len(obs) > 0:
                ret = ret | obs
        elif type(self.observables) is dict:
            for obs in self.observables.values():
                ret = ret | obs.get_activities()
        ac = self.aircraft.get_activities()
        if len(ac) > 0:
            ret = ret | ac
        return ret

    def activity_factory(self, name: str, creator: str = None) -> Activity:
        """Returns data or create a new internal variable"""
        activity = Activity(name=name)
        if creator is not None:
            activity._creator = creator
        return activity

    def register_activity(self, activity: Activity) -> Activity:
        return self.activity_database.register(activity)

    def get_activity(self, name: str, factory: ActivityFactory) -> Activity:
        """Returns data or create a new one, internal if path requires it"""
        if self.activity_database.exists(name):
            return self.activity_database.get(name)
        return self.activity_database.register(activity=factory.activity_factory(name=name, creator=self.name))

    def get_variable_value(self, name, default=None) -> Any | None:
        """Gets the value of a Variable monitored by Cockpitdecks
        Args:
            simulator_variable ([type]): [description]
            default ([type]): [description] (default: `None`)

        Returns:
            [type]: [description]
        """
        return self.variable_database.value_of(name, default=default)

    def get_variables(self) -> set:
        """Returns the list of datarefs for which the cockpit wants to be notified, including those of the aircraft."""
        ret = {Variable.internal_variable_name(v) for v in self._permanent_variable_names}
        # ret = {d.name for d in self._permanent_variables.values()}
        if type(self.observables) is Observables:
            obs = self.observables.get_variables()
            if len(obs) > 0:
                ret = ret | obs
        elif type(self.observables) is dict:
            for obs in self.observables.values():
                ret = ret | obs.get_variables()
        elif type(self.observables) is list:
            for obs in self.observables:
                ret = ret | obs.get_variables()
        ac = self.aircraft.get_variables()
        if len(ac) > 0:
            ret = ret | ac
        return ret

    def variable_factory(self, name: str, is_string: bool = False, creator: str = None) -> Variable:
        """Returns data or create a new internal variable"""
        variable = InternalVariable(name=name, is_string=is_string)
        if creator is not None:
            variable._creator = creator
        return variable

    def register(self, variable: Variable) -> Variable:
        return self.variable_database.register(variable)

    def get_variable(self, name: str, factory: VariableFactory, is_string: bool = False) -> Variable:
        """Returns data or create a new one, internal if path requires it"""
        if self.variable_database.exists(name):
            var = self.variable_database.get(name)
            if var is not None and var.is_string != is_string:
                logger.warning(f"variable {name} has wrong type {var.data_type} vs. ={is_string}")
                if is_string:
                    var.data_type = InternalVariableType.STRING
                    logger.warning(f"variable {name} type forced to string" + " *" * 10)
            return var
        return self.variable_database.register(variable=factory.variable_factory(name=name, is_string=is_string, creator=self.name))

    # #########################################################
    # Attribute defaults
    #
    def get_color(self, color, silence: bool = True) -> Tuple[int, int, int] | Tuple[int, int, int, int]:
        if type(color) is str and color in self.named_colors:
            color1 = color
            color = self.named_colors.get(color)  # named color can be the name of a pillow color...
            if silence:
                logger.debug(f"named colors {color1}=>{color}")
            else:
                logger.info(f"named colors {color1}=>{color}")
        return convert_color(color)  # this time, if color is a color name it must be a valid pillow color name

    def convert_color(self, instr):
        """Adds an extra layer of possibilities to define our own color names
        for styling purposes.
        """
        if instr in self.named_colors:
            return self.named_colors.get(instr)
        return convert_color(instr=instr)

    def convert_if_color_attribute(self, attribute: str, value, silence: bool = True):
        if type(attribute) is str and "color" in attribute and type(value) is str:
            if silence:
                logger.debug(f"convert color {attribute}={value}, {type(attribute)}, {self.named_colors.get(value)}")
            else:
                logger.info(f"convert color {attribute}={value}, {type(attribute)}, {self.named_colors.get(value)}")
        return self.get_color(color=value, silence=silence) if type(attribute) is str and "color" in attribute else value

    def set_default(self, dflt, value):
        if not dflt.startswith(DEFAULT_ATTRIBUTE_PREFIX):
            logger.warning(f"default variable {dflt} does not start with {DEFAULT_ATTRIBUTE_PREFIX}")
        ATTRNAME = "_defaults"
        if not hasattr(self, ATTRNAME):
            setattr(self, ATTRNAME, dict())
        ld = getattr(self, ATTRNAME)
        if isinstance(ld, dict):
            ld[dflt] = value
        logger.debug(f"set default {dflt} to {value}")

    def get_attribute(self, attribute: str, default=None, silence: bool = True):
        # Attempts to provide a dark/light theme alternative, fall back on light(=normal)
        # Assumes attributes are-kebab-case.
        def is_themable_attribute(a: str) -> bool:
            # Returns whether an attribute can be themed
            # Currently, only color, texture, and fonts
            return self.theme is not None and (a.endswith("color") or a.endswith("texture") or ("font" in a) or a.startswith("cockpit-"))

        def is_themed_attribute(a: str) -> bool:
            return self.theme is not None and a.startswith(self.theme)

        def is_default_attribute(a: str) -> bool:
            return a.startswith(DEFAULT_ATTRIBUTE_PREFIX) or a.startswith("cockpit-")  # or "default" in a?

        def stripfirst(a):
            return "-".join(a.split("-")[1:])

        def addfirst(a, s):
            return "-".join([s, a])

        def trace_debug(s):
            logger.debug(s) if silence else logger.info(s)

        self._reqdfts.add(attribute)  # internal stats

        trace_debug(f"searching for {attribute}")

        # 1. First, if allowed, we try it in a theme
        if is_themable_attribute(attribute) and not is_themed_attribute(attribute):
            newattr = addfirst(attribute, self.theme)
            trace_debug(f"searching for {attribute}, first trying with theme {self.theme}")
            value = self.get_attribute(attribute=newattr, default=default, silence=silence)
            if not silence:
                logger.info(f"tried themed {newattr}, value {value}")
            if value is not None:
                return self.convert_if_color_attribute(attribute=attribute, value=value, silence=silence)

        trace_debug(f"trying normal {attribute}")
        # 2. Then Let's first try the attribute as requested...
        # 2.1. From the aircraft config (custom, from the user)
        value = self._config.get(attribute)
        if not silence:
            logger.info(f"tried normal (config) {attribute}, value {value}")
        if value is not None:
            trace_debug(f"cockpit returning {attribute}={value} (from config)")
            return self.convert_if_color_attribute(attribute=attribute, value=value, silence=silence)

        # 2.2 From Cockpitdekcs resources (config, fixed)
        value = self._resources_config.get(attribute)
        if not silence:
            logger.info(f"trying normal (resources) {attribute}, value {value}")
        if value is not None:
            trace_debug(f"cockpit returning {attribute}={value} (from resources)")
            return self.convert_if_color_attribute(attribute=attribute, value=value, silence=silence)

        # 3.2 From internal values (fixed)
        ATTRNAME = "_defaults"
        if hasattr(self, ATTRNAME):
            ld = getattr(self, ATTRNAME)
            if isinstance(ld, dict):
                value = ld.get(attribute)
                if not silence:
                    logger.info(f"tried (internal defaults) {attribute}, value {value}")
                if value is not None:
                    trace_debug(f"cockpit returning {attribute}={value} (from internal default)")
                    return self.convert_if_color_attribute(attribute=attribute, value=value, silence=silence)

        # If we're here haven't found the themed attribute either
        # Second, we'll try with default-
        if not (is_default_attribute(attribute) or is_themed_attribute(attribute)):  # we cannot add default-
            newattr = addfirst(attribute, DEFAULT_ATTRIBUTE_NAME)
            trace_debug(f"no value for {attribute}, trying default-")
            value = self.get_attribute(attribute=newattr, default=default, silence=silence)
            if not silence:
                logger.info(f"tried {newattr}, value {value}")
            if value is not None:
                return self.convert_if_color_attribute(attribute=attribute, value=value, silence=silence)

        if is_themed_attribute(attribute):
            # no theme-attribute or theme-default-attribute
            # in this case, we do not return the default,
            # but we notify we did not find a themed value
            # by returning None
            return None

        # no default-attribute
        # No attribute we return the default carried over so far
        if not is_default_attribute(attribute):
            logger.warning(f"returning default value of non default attribute ({default})")

        trace_debug(f"no value for {attribute}, returning default ({default})")
        return self.convert_if_color_attribute(attribute=attribute, value=default, silence=silence)

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

    # #########################################################
    # Cockpitdecks inspection
    #
    def inc(self, name: str, amount: float = 1.0, cascade: bool = False):
        # Here, it is purely statistics
        if self.sim is not None:
            self.sim.inc_internal_variable(name=ID_SEP.join([self.get_id(), name]), amount=amount, cascade=cascade)

    # #########################################################
    # Cockpit data caches
    #
    def load_resources(self):
        self.load_icons()
        self.load_sounds()
        self.load_fonts()
        self.load_defaults()
        self.load_observables()
        self.load_deck_types()

    def load_deck_types(self):
        # 1. "System" types
        for deck_type in DeckType.list():
            try:
                data = DeckType(deck_type)
                self.deck_types[data.name] = data
                if data.is_virtual_deck():
                    self.virtual_deck_types[data.name] = data.get_virtual_deck_layout()
            except ValueError:  # this is one of ours, this is an error, not a warning.
                logger.error(f"could not load deck type {deck_type}, ignoring")
        # 2. Deck types in extension folder(s)
        if self.extension_paths is not None:
            for path in self.extension_paths:
                ext_path = os.path.join(path, DECKS_FOLDER, RESOURCES_FOLDER, TYPES_FOLDER)
                for deck_type in DeckType.list(ext_path):
                    data = DeckType(deck_type)
                    self.deck_types[data.name] = data
                    if data.is_virtual_deck():
                        self.virtual_deck_types[data.name] = data.get_virtual_deck_layout()

        # 3. Deck types in extension modules:
        for package in self.all_extensions:
            for deck_type in DeckType.list(path=None, module=package + ".decks.resources.types"):
                if deck_type not in self.deck_types:
                    data = DeckType(deck_type)
                    self.deck_types[data.name] = data
                    if data.is_virtual_deck():
                        self.virtual_deck_types[data.name] = data.get_virtual_deck_layout()
                    logger.debug(f"package {package}: decktype {deck_type} loaded")
                else:
                    logger.warning(f"package {package}: decktype {deck_type} already loaded")

        real_decks = [k for k, v in self.deck_types.items() if not v.is_virtual_deck()]
        logger.info(f"loaded {len(real_decks)} deck types ({', '.join(real_decks)})")
        logger.info(f"loaded {len(self.virtual_deck_types)} virtual deck types ({', '.join(self.virtual_deck_types.keys())})")

    def load_permanent_observables(self):
        # Permament observables are observables coded as subclass of Observable.
        # They take no configuration to start, they are self contained.
        # If it exposes a variable, the variable can be used in other Observables to trigger actions/instructions.
        self._permanent_observables = {s.name(): s for s in CockpitdecksLoader.all_subclasses(Observable) if not Observable.is_internal(s.name())}
        if len(self._permanent_observables) > 0:
            logger.info(f"loaded {len(self._permanent_observables)} permanent observables: {', '.join(sorted(self._permanent_observables.keys()))}")
        else:
            logger.info("no permanent observables")

    def get_permanent_observables(self):
        return self._permanent_observables.values()

    def load_observables(self):
        # Permanent observables are "coded" observables
        self.load_permanent_observables()

        # Regular, cockpitdecks-level observables
        if self._observables is not None:  # load once
            return
        fn = os.path.abspath(os.path.join(os.path.dirname(__file__), RESOURCES_FOLDER, OBSERVABLES_FILE))
        if os.path.exists(fn):
            config = {}
            with open(fn, "r") as fp:
                config = yaml.load(fp)
            self._observables = config
            logger.info(f"loaded {len(self._observables)} cockpit observables.")
        else:
            logger.info("no cockpit observables")

    @property
    def observables(self) -> list:
        if self._observables is None:
            return []
        if type(self._observables) is Observables:
            return self._observables.observables
        elif type(self._observables) is dict:
            return self._observables.values()
        elif type(self._observables) is list:
            return self._observables
        else:
            logger.warning(f"invalid type for _observables ({type(self._observables)})")
        return {}

    def load_icons(self):
        # Loading default icons
        #
        cache_icon = self.get_attribute("cache-icon")
        dn = os.path.join(os.path.dirname(__file__), RESOURCES_FOLDER, ICONS_FOLDER)
        if os.path.exists(dn):
            cache = os.path.join(dn, "_icon_cache.pickle")
            if os.path.exists(cache) and cache_icon:
                with open(cache, "rb") as fp:
                    self._icons = pickle.load(fp)
                logger.info(f"{len(self._icons)} icons loaded from cache")
            else:
                icons = os.listdir(dn)
                for i in icons:
                    fn = os.path.join(dn, i)
                    if has_ext(i, "png"):  # later, might load JPG as well.
                        image = Image.open(fn)
                        self._icons[i] = image
                    elif has_ext(i, "svg"):  # Wow.
                        try:
                            fn = os.path.join(dn, i)
                            fout = fn.replace(".svg", ".png")
                            svg2png(url=fn, write_to=fout)
                            image = Image.open(fout)
                            self._icons[i] = image
                        except:
                            logger.warning(f"could not load icon {fn}")
                            pass  # no cairosvg

                if cache_icon:  # we cache both folders of icons
                    with open(cache, "wb") as fp:
                        pickle.dump(self._icons, fp)
                    logger.info(f"{len(self._icons)} icons cached")
                else:
                    logger.info(f"{len(self._icons)} icons loaded")

        self.icons = self._icons | self.aircraft.icons

    def load_fonts(self):
        # Loading fonts.
        # For custom fonts (fonts found in the fonts config folder),
        # we supply the full path for font definition to ImageFont.
        # For other fonts, we assume ImageFont will search at OS dependent folders or directories.
        # If the font is not found by ImageFont, we ignore it.
        # So self.icons is a list of properly located usable fonts.
        #
        rn = os.path.join(os.path.dirname(__file__), RESOURCES_FOLDER, FONTS_FOLDER)
        if os.path.exists(rn):
            fonts = os.listdir(rn)
            for i in fonts:
                if has_ext(i, ".ttf") or has_ext(i, ".otf"):
                    if i not in self._fonts.keys():
                        fn = os.path.join(rn, i)
                        try:
                            test = ImageFont.truetype(fn, self.get_attribute("label-size", 12))
                            self._fonts[i] = fn
                        except:
                            logger.warning(f"font file {fn} not loaded")
                    else:
                        logger.debug(f"font {i} already loaded")

        self.fonts = self._fonts | self.aircraft.fonts
        logger.info(
            f"{len(self._fonts)} fonts loaded, default font={self.get_attribute('default-font')}, default label font={self.get_attribute('default-label-font')}"
        )

    def load_sounds(self):
        # Loading sounds.
        #
        rn = os.path.join(os.path.dirname(__file__), RESOURCES_FOLDER, SOUNDS_FOLDER)
        if os.path.exists(rn):
            sounds = os.listdir(rn)
            for i in sounds:
                if has_ext(i, ".wav") or has_ext(i, ".mp3"):
                    if i not in self._sounds.keys():
                        fn = os.path.join(rn, i)
                        try:
                            with open(fn, mode="rb") as file:  # b is important -> binary
                                self._sounds[i] = file.read()
                        except:
                            logger.warning(f"default sound file {fn} not loaded")
                    else:
                        logger.debug(f"sound {i} already loaded")

        self.sounds = self._sounds | self.aircraft.sounds
        logger.info(f"{len(self._sounds)} sounds loaded")

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
                test = ImageFont.truetype(fontname, self.get_attribute("label-size", 12))
                logger.debug(f"font {fontname} found in computer system fonts")
                return fontname
            except:
                logger.debug(f"font {fontname} not found in computer system fonts")

            # 2. Try font in resources folder
            fn = None
            try:
                fn = os.path.join(os.path.dirname(__file__), RESOURCES_FOLDER, fontname)
                test = ImageFont.truetype(fn, self.get_attribute("label-size", 12))
                logger.debug(f"font {fontname} found locally ({RESOURCES_FOLDER} folder)")
                return fn
            except:
                logger.debug(f"font {fontname} not found locally ({RESOURCES_FOLDER} folder)")

            # 3. Try font in resources/fonts folder
            fn = None
            try:
                fn = os.path.join(os.path.dirname(__file__), RESOURCES_FOLDER, FONTS_FOLDER, fontname)
                test = ImageFont.truetype(fn, self.get_attribute("label-size", 12))
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

        more_debug = self._resources_config.get("debug")
        if more_debug is not None:
            self.add_debug(set(more_debug.split(",")))
            self.set_logging_level(__name__)

        if self.sim is not None:
            self.sim.set_simulator_variable_roundings(simulator_variable_roundings=self._resources_config.get("dataref-roundings", {}))
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
            if default_label_font not in self._fonts.keys():
                f = locate_font(default_label_font)
                if f is not None:  # found one, perfect
                    self._fonts[default_label_font] = f
                    self.set_default("default-font", default_label_font)
                    logger.debug(f"default font set to {default_label_font}")
                    logger.debug(f"default label font set to {default_label_font}")
                    logger.info(f"added default label font {default_label_font}")
            else:
                logger.debug(f"default label font is {default_label_font}")
        else:
            logger.warning("no default label font")

        default_system_font = self.get_attribute("system-font")
        if default_system_font is not None:
            if default_system_font not in self._fonts.keys():
                f = locate_font(default_system_font)
                if f is not None:  # found it, perfect, keep it as default font for all purposes
                    self._fonts[default_system_font] = f
                    self.set_default("default-font", default_system_font)
                    logger.debug(f"default font set to {default_system_font}")
                    if default_label_font is None:  # additionnally, if we don't have a default label font, use it
                        self.set_default("default-label-font", default_system_font)
                        logger.debug(f"default label font set to {default_system_font}")
                    logger.info(f"added default system font {default_system_font}")
            else:
                logger.debug(f"default system font is {default_system_font}")
        else:
            logger.warning("no default system font")

        # rebuild font list
        self.fonts = self._fonts | self.aircraft.fonts

        if default_label_font is None and len(self.fonts) > 0:
            first_one = list(self.fonts.keys())[0]
            self.set_default("default-label-font", first_one)
            self.set_default("default-font", first_one)
            logger.debug(f"no default font found, using first available font ({first_one})")

        if default_label_font is None:
            logger.error("no default font")

        # 4. report summary if debugging
        logger.debug(
            f"default fonts {self.fonts.keys()}, default={self.get_attribute('default-font')}, default label={self.get_attribute('default-label-font')}"
        )

    # Getters
    def get_deck_type(self, name: str):
        return self.deck_types.get(name)

    def get_observable(self, name) -> Observable | None:
        # First, search in Cockpit
        if self._observables is not None:
            obs = self._observables.get_observable(name)
            if obs is not None:
                return obs
        # Then in Aircraft
        if self.aircraft._observables is not None:
            obs = self.aircraft._observables.get_observable(name)
            if obs is not None:
                return obs
        # Then in Simulator
        if self.sim._observables is not None:
            obs = self.sim._observables.get_observable(name)
            if obs is not None:
                return obs
        # Then in Permanent Observables
        for obs in self.sim._permanent_observables:
            if obs._name == name:
                return obs
        return None

    def get_icon(self, candidate_icon):
        for ext in ["", ".png", ".jpg", ".jpeg"]:
            fn = add_ext(candidate_icon, ext)
            if fn in self.icons.keys():
                logger.debug(f"Cockpit: icon {fn} found")
                return fn
        logger.warning(f"Cockpit: icon not found {candidate_icon}")  # , available={self.icons.keys()}
        return None

    def get_icon_image(self, icon):
        return self.icons.get(icon)

    # #########################################################
    # Aircraft
    #
    def add_resources(self, aircraft: Aircraft):
        # called from self.aircraft.start() to incorporate aircraft resources into cockpit
        self.fonts = self._fonts | aircraft.fonts
        logger.info(f"{len(self.fonts)} fonts available")

        self.icons = self._icons | aircraft.icons
        logger.info(f"{len(self.icons)} icons available")

        dftname = self.get_attribute("icon-name")
        if dftname in self.icons.keys():
            logger.debug(f"default icon name {dftname} found")
        else:
            logger.warning(f"default icon name {dftname} not found")  # that's ok

        self.sounds = self._sounds | aircraft.sounds
        logger.info(f"{len(self.sounds)} sounds available")

        logger.info(f"{len(self.observables) + len(self.aircraft.observables)} observables")

    def remove_aircraft_resources(self):
        # called from self.aircraft.terminate() to remove aircraft resources from cockpit
        self.fonts = self._fonts
        logger.info(f"{len(self.fonts)} fonts available")

        self.icons = self._icons
        logger.info(f"{len(self.icons)} icons available")

        dftname = self.get_attribute("icon-name")
        if dftname in self.icons.keys():
            logger.debug(f"default icon name {dftname} found")
        else:
            logger.warning(f"default icon name {dftname} not found")  # that's ok

        self.sounds = self._sounds
        logger.info(f"{len(self.sounds)} sounds available")

        logger.info(f"{len(self.observables)} observables")

    def load_aircraft(self, acpath: str, release: bool = False, mode: int = 0):
        """
        Loads decks for aircraft in supplied path and start listening for key presses.
        """
        self.mode = mode
        with self.reload_operation:
            self.aircraft.start(acpath)

    # #########################################################
    # Start/Stop engines
    #
    def get_corresponding_serial(self, serial_in) -> str:
        """Serial numbers returned by ioreg -p IOUSB do not match serial number returned by devices.
        This does hardcoded case by case correspondance between both.
        See https://www.computerpi.com/the-truth-about-usb-device-serial-numbers-and-the-lies-your-tools-tell/

        """
        if serial_in is None:
            return ""
        if serial_in.startswith("A00"):
            return serial_in.replace("A00", "")
        if serial_in == "1.0.1":
            return "X-TOUCH MINI"

    def terminate_devices(self):
        for deck in self.devices:
            deck_driver = deck.get(CONFIG_KW.DRIVER.value)
            if deck_driver not in self.all_deck_drivers.keys():
                logger.warning(f"invalid deck type {deck_driver}, ignoring")
                continue
            device = deck[CONFIG_KW.DEVICE.value]
            self.all_deck_drivers[deck_driver][0].terminate_device(device, deck[CONFIG_KW.SERIAL.value])

    # ###############################################################
    # Web/Virtual decks
    #
    def has_web_decks(self) -> bool:
        for device in self.devices:
            if device.get(CONFIG_KW.DRIVER.value) == VIRTUAL_DECK_DRIVER:
                return True
        return False

    def get_virtual_deck_description(self, deck) -> VirtualDeck:
        return self.virtual_decks.get(deck)

    def get_virtual_deck_defaults(self):
        return self.get_attribute("web-deck-defaults")

