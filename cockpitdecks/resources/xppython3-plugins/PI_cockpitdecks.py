# Creates pair of commandBegin/commandEnd for some commands.
# New commands for "command" are "command/begin" and "command/end".
#
# Starts broadcasting string datarefs more or less frequently (every 5-10 seconds)
# because collecting string datarefs is expensive.
#
import os
import glob
from re import split
import socket
import time
import json
from traceback import print_exc
from threading import RLock

import ruamel
from ruamel.yaml import YAML

from XPPython3 import xp

ruamel.yaml.representer.RoundTripRepresenter.ignore_aliases = lambda x, y: True
yaml = YAML(typ="safe", pure=True)

# ###########################################################
#
#   C O C K P T D E C K S   H E L P E R   P L U G I N
#
RELEASE = "1.4.0"  # local version number
#
# Changelog:
#
# 27-JAN-2025: 1.4.0: Added aircraft path in datarefs
# 09-JAN-2025: 1.3.1: Added explicit command begin-end-command in search
# 28-OCT-2024: 1.3.0: Added code to split large quantities of string into acceptable UDP packets
# 23-OCT-2024: 1.2.0: Add maximum frequency (~10 secs) for collection, send UDP more frequently
# 30-SEP-2024: 1.1.2: Add maximum frequency (~10 secs)
# 23-AUG-2024: 1.1.1: Wrong if/then/else
# 23-AUG-2024: 1.1.0: Added datarefs to allow for external monitoring
# 21-AUG-2024: 1.0.4: Add defaults if requested
# 26-JUL-2024: 1.0.3: Added string-dataref (singular)
# 11-JUL-2024: 1.0.2: Corrected issue when getDatas would complain for 0 length string
# 11-JUL-2024: 1.0.1: Added AIRCRAFT_LIVERY to the list of datarefs that are always sent
# 05-JUL-2024: 1.0.0: Initial version, combination of cockpitdecks_helper and string_datarefs_udp
#
# Constants:
#
# Where to find things
CONFIG_DIR = "deckconfig"
CONFIG_FILE = "config.yaml"
DEFAULT_LAYOUT = "default"
#
# Internal datarefs for monitoring
#
CDH_RELEASE = "XPPython3/cockpitdeckshelper/release"
CDH_IS_RUNNING = "XPPython3/cockpitdeckshelper/is_running"
CDH_LPCOMMANDS = "XPPython3/cockpitdeckshelper/longpress_commands"
CDH_STRINGDREF = "XPPython3/cockpitdeckshelper/string_datarefs"

CDH_DATAREFS = [CDH_IS_RUNNING, CDH_RELEASE, CDH_LPCOMMANDS, CDH_STRINGDREF]
#
# ###########################################################
# LONG PRESS COMMAND
#
# Commands extracted from these button types
# will get a command/begin command/end helper command.
NOTICABLE_BUTTON_TYPES = ["long-press", "longpress", "begin-end-command"]
#
REF = "cmdref"
FUN = "cmdfun"
HDL = "cmdhdl"
#
#
#
# ###########################################################
# STRING DATAREFS UDP
#
MCAST_GRP = "239.255.1.1"  # same as X-Plane 12
MCAST_PORT = 49505  # 49707 for XPlane12
MCAST_TTL = 2
MAX_PACK_LEN = 1472

COLLECTION_FREQUENCY = 5.0  # will run every COLLECTION_FREQUENCY seconds at most, never faster
COLLECTION_FREQUENCY_MAX = 10  # will run at least every COLLECTION_FREQUENCY_MAX seconds, never slower
EMISSION_FREQUENCY = 1  # seconds, sends UDP packet often so that Cockpitdecks does not wait to get data.
# note: sending a single UDP package (often) is cheap (cpu, resources), even for X-Plane.

AIRCRAFT_PATH = "sim/aircraft/view/acf_relative_path"
AIRCRAFT_ICAO = "sim/aircraft/view/acf_ICAO"
AIRCRAFT_LIVERY = "sim/aircraft/view/acf_livery_path"
AIRCRAFT_LIVERY_INDEX = "sim/aircraft/view/acf_livery_index"

# default is to return these if asked for default dataref
PERMANENT_STRING_DATAREFS = [AIRCRAFT_PATH, AIRCRAFT_ICAO, AIRCRAFT_LIVERY, AIRCRAFT_LIVERY_INDEX]  # dataref that gets updated if new aircraft loaded
LOAD_PERMANENT_DATAREFS = True

CHECK_COUNT = [5, 20]


def split_dict(indict, packet_max_size: int = MAX_PACK_LEN) -> list:
    """Split large dictionary into smaller ones.
    Returns a list of dictionaries, each len(json.dumps(dict)) < packet_max_size
    """
    # quick check
    if len(json.dumps(indict)) < packet_max_size:
        return [indict]
    # too large, split it
    a = indict.copy()
    i = 0
    bag = []
    b = {}
    while a:
        v = ()
        s = json.dumps(b)
        while a and len(s) < packet_max_size:
            v = a.popitem()
            t = json.dumps({v[0]: v[1]})  # check if individual string is not too big...
            if len(t) > packet_max_size:
                print(f"Cockpitdecks Helper (rel. {RELEASE}): split_dict: ignoring {v} ({len(t)} > {packet_max_size})")
                continue
            b[v[0]] = v[1]
            s = json.dumps(b)

        if a:
            if len(v) > 0 and v[0] in b:
                del b[v[0]]
            s = json.dumps(b)
            bag.append(b)
            i = i + 1
            b = {}
            b[v[0]] = v[1]
    bag.append(b)  # last one
    return bag


#
# ###########################################################
# PLUG IN PythonInterface
#
class PythonInterface:
    def __init__(self):
        self.Name = "Cockpitdecks Helper"
        self.Sig = "xppython3.cockpitdeckshelper"
        self.Desc = f"Cockpitdecks Helper plugin to circumvent some X-Plane UDP limitations (Rel. {RELEASE})"
        self.Info = self.Name + f" (rel. {RELEASE})"
        self.enabled = False
        self.trace = True  # produces extra print/debugging in XPPython3.log for this class

        self.acpath = ""
        self.datarefs = {}
        self.commands = {}
        self.use_defaults = LOAD_PERMANENT_DATAREFS
        self.run_count = 0
        self.num_collected_drefs = 0
        self.frequency = COLLECTION_FREQUENCY
        self.str_bytes = []

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, MCAST_TTL)
        self.RLock = RLock()

        self.isRunningRef = None  # witness for all accessors
        self.cmdCountRef = None
        self.sdrCountRef = None
        self.releaseRef = None

    def XPluginStart(self):
        if self.trace:
            print(self.Info, "XPluginStart: started")

        self.isRunningRef = xp.registerDataAccessor(
            name=CDH_IS_RUNNING, dataType=xp.Type_Int, writable=0, readInt=self.getRunningStatusCallback  # Read-Only
        )  # Refcons not used
        self.cmdCountRef = xp.registerDataAccessor(
            name=CDH_LPCOMMANDS, dataType=xp.Type_Int, writable=0, readInt=self.getLPCommandCountCallback  # Read-Only
        )  # Refcons not used
        self.sdrCountRef = xp.registerDataAccessor(
            CDH_STRINGDREF, dataType=xp.Type_Int, writable=0, readInt=self.getStringDrefCountCallback  # Read-Only
        )  # Refcons not used
        self.releaseRef = xp.registerDataAccessor(
            CDH_RELEASE, dataType=xp.Type_Data, writable=0, readData=self.getReleaseCallback  # Read-Only
        )  # Refcons not used
        if self.trace:
            print(self.Info, f"XPluginStart: data accessors added.")

        return self.Name, self.Sig, self.Desc

    def XPluginStop(self):
        for k, v in self.commands.items():
            if FUN in v:  # cached commands have no FUN
                xp.unregisterCommandHandler(v[REF], v[FUN], 1, None)
            if self.trace:
                print(self.Info, "XPluginStop: unregistered", k)

        if self.isRunningRef is not None:  # and self.isRunningRef > 0?
            xp.unregisterDataAccessor(self.isRunningRef)
            self.isRunningRef = None
            xp.unregisterDataAccessor(self.cmdCountRef)
            self.cmdCountRef = None
            xp.unregisterDataAccessor(self.sdrCountRef)
            self.sdrCountRef = None
            xp.unregisterDataAccessor(self.releaseRef)
            self.releaseRef = None
            if self.trace:
                print(self.Info, "XPluginStop: data accessors unregistered.")
        else:
            if self.trace:
                print(self.Info, "XPluginStop: data accessors not unregistered.")

        if self.trace:
            print(self.Info, "XPluginStop: stopped.")
        return None

    def XPluginEnable(self):
        xp.registerFlightLoopCallback(self.CollectDatarefsCB, 1.0, 0)
        if self.trace:
            print(self.Info, "XPluginEnable: collection flight loop registered")

        xp.registerFlightLoopCallback(self.BroadcastDatarefsCB, 1.0, 0)
        if self.trace:
            print(self.Info, "XPluginEnable: emission flight loop registered")

        if self.isRunningRef is not None:
            for sig in ("com.leecbaker.datareftool", "xplanesdk.examples.DataRefEditor"):
                dre = xp.findPluginBySignature(sig)
                if dre != xp.NO_PLUGIN_ID:
                    for path in CDH_DATAREFS:
                        xp.sendMessageToPlugin(dre, 0x01000000, path)
                    if self.trace:
                        print(self.Info, f"XPluginEnable: data accessors registered with {sig}.")
                else:
                    if self.trace:
                        print(self.Info, f"XPluginEnable: plugin {sig} not found.")

        try:
            ac = xp.getNthAircraftModel(0)  # ('Cessna_172SP.acf', '/Volumns/SSD1/X-Plane/Aircraft/Laminar Research/Cessna 172SP/Cessna_172SP.acf')
            if len(ac) == 2:
                acpath = os.path.split(ac[1])  # ('/Volumns/SSD1/X-Plane/Aircraft/Laminar Research/Cessna 172SP', 'Cessna_172SP.acf')
                print(self.Info, "XPluginEnable: trying " + acpath[0] + " ..")
                self.load(acpath=acpath[0])
                print(self.Info, "XPluginEnable: " + acpath[0] + " done.")
                self.enabled = True
                if self.trace:
                    print(self.Info, "enabled")
                return 1
            print(self.Info, "XPluginEnable: getNthAircraftModel: aircraft not found.")
            return 1
        except:
            if self.trace:
                print(self.Info, "XPluginEnable: exception.")
            print_exc()
            self.enabled = False
            if self.trace:
                print(self.Info, "not enabled")
        return 0

    def XPluginDisable(self):
        xp.unregisterFlightLoopCallback(self.BroadcastDatarefsCB, 0)
        if self.trace:
            print(self.Info, "XPluginDisable: emission flight loop unregistered")
        xp.unregisterFlightLoopCallback(self.CollectDatarefsCB, 0)
        if self.trace:
            print(self.Info, "XPluginDisable: collection flight loop unregistered")
        self.enabled = False
        if self.trace:
            print(self.Info, "disabled")
        return None

    def XPluginReceiveMessage(self, inFromWho, inMessage, inParam):
        """
        When we receive a message that an aircraft was loaded, if it is the user aircraft,
        we try to load the aicraft deskconfig.
        If it does not exist, we default to a screen saver type of screen for the deck.
        """
        if inMessage == xp.MSG_PLANE_LOADED and inParam == 0:  # 0 is for the user aircraft, greater than zero will be for AI aircraft.
            print(self.Info, "XPluginReceiveMessage: user aircraft received")
            try:
                ac = xp.getNthAircraftModel(0)  # ('Cessna_172SP.acf', '/Volumns/SSD1/X-Plane/Aircraft/Laminar Research/Cessna 172SP/Cessna_172SP.acf')
                if len(ac) == 2:
                    acpath = os.path.split(ac[1])  # ('/Volumns/SSD1/X-Plane/Aircraft/Laminar Research/Cessna 172SP', 'Cessna_172SP.acf')
                    if self.trace:
                        print(
                            self.Info,
                            "XPluginReceiveMessage: trying " + acpath[0] + "..",
                        )
                    self.load(acpath=acpath[0])
                    if self.run_count > 0:
                        print(
                            self.Info,
                            "XPluginReceiveMessage: old run count " + str(self.run_count) + ", run count reset",
                        )
                        self.run_count = 0
                    if self.trace:
                        print(
                            self.Info,
                            "XPluginReceiveMessage: .. " + acpath[0] + " done.",
                        )
                    return None
                print(
                    self.Info,
                    "XPluginReceiveMessage: getNthAircraftModel: aircraft not found.",
                )
            except:
                if self.trace:
                    print(self.Info, "XPluginReceiveMessage: exception.")
                print_exc()
                self.enabled = False
        return None

    def getRunningStatusCallback(self, inRefcon):
        return 1 if self.enabled else 0

    def getReleaseCallback(self, inRefcon, values, offset, count):
        # https://xppython3.readthedocs.io/en/latest/development/modules/dataaccess.html
        array = bytearray(RELEASE, encoding="utf-8")
        if values is None:
            return len(RELEASE)
        values.extend(array[offset : offset + count])
        return min(count, len(RELEASE) - offset)  # number of bytes copied

    def getLPCommandCountCallback(self, inRefcon):
        return len(self.commands) if self.commands is not None else 0

    def getStringDrefCountCallback(self, inRefcon):
        return len(self.datarefs) if self.datarefs is not None else 0

    def CollectDatarefsCB(self, sinceLast, elapsedSim, counter, refcon):
        if not self.enabled:
            return 0
        if self.run_count % 100 == 0:
            print(self.Info, f"CollectDatarefsCB: is alive ({self.run_count})")
        elif self.run_count in CHECK_COUNT:
            if len(self.datarefs) < self.num_collected_drefs and (self.acpath is not None and len(self.acpath) > 0):
                print(
                    self.Info,
                    f"CollectStringDatarefsCB: is alive ({self.run_count}), missing string datarefs {len(self.datarefs)}/{self.num_collected_drefs} for {self.acpath}",
                )
                self.load(acpath=self.acpath)
            else:
                print(
                    self.Info,
                    f"CollectStringDatarefsCB: is alive ({self.run_count}), {len(self.datarefs)}/{self.num_collected_drefs} string datarefs for {self.acpath}",
                )
        self.run_count = self.run_count + 1
        drefvalues = {AIRCRAFT_PATH: self.acpath}
        with self.RLock:
            try:  # efficent method
                drefvalues = drefvalues | {d: xp.getDatas(self.datarefs[d]) for d in self.datarefs}
            except:  # if one dataref does not work, try one by one, skip those in error
                drefvalues = {AIRCRAFT_PATH: self.acpath}
                for d in self.datarefs:
                    try:
                        v = xp.getDatas(self.datarefs[d])
                        drefvalues[d] = v
                    except:
                        print(
                            self.Info,
                            f"CollectStringDatarefsCB: error fetching dataref string {d}, skipping",
                        )
            # build packets of bytes
            metainfo = {"meta": {"v": RELEASE, "ts": round(time.time(), 3), "f": round(self.frequency, 1)}}
            metalen = len(json.dumps(metainfo))
            self.str_bytes = [bytes(json.dumps(metainfo | p), "utf-8") for p in split_dict(drefvalues, packet_max_size=MAX_PACK_LEN - metalen)]

        return self.frequency

    def BroadcastDatarefsCB(self, sinceLast, elapsedSim, counter, refcon):
        if not self.enabled:
            return 0
        with self.RLock:
            if len(self.str_bytes) > 0:
                for b in self.str_bytes:
                    if len(b) > MAX_PACK_LEN:
                        print(
                            self.Info,
                            f"BroadcastDatarefsCB: UDP packed too large ({len(b)}/{MAX_PACK_LEN}), not sent",
                        )
                    elif len(b) > 0:
                        self.sock.sendto(b, (MCAST_GRP, MCAST_PORT))
                    else:
                        print(
                            self.Info,
                            f"BroadcastDatarefsCB: UDP packed size is zero, not sent",
                        )
        return EMISSION_FREQUENCY

    def command(self, command: str, begin: bool) -> int:
        # Execute a long press command
        #
        try:
            if command in self.commands:
                if begin:
                    xp.commandBegin(self.commands[command][REF])
                else:
                    xp.commandEnd(self.commands[command][REF])
            else:
                cmdref = xp.findCommand(command)
                if cmdref is not None:
                    self.commands[command] = {}  # cache it
                    self.commands[command][REF] = cmdref
                    if begin:
                        xp.commandBegin(self.commands[command][REF])
                    else:
                        xp.commandEnd(self.commands[command][REF])
                else:
                    print(self.Info, f"command: {command} not found")
        except:
            if self.trace:
                print(self.Info, "command: exception:")
            print_exc()
        return 0  # callback must return 0 or 1.

    def get_beginend_commands(self, acpath):
        # Scans an aircraft deckconfig and collects long press commands.
        #
        # Internal constants (keywords in yaml file)
        #
        BUTTONS = "buttons"  # keyword for button definitions on page
        DECKS = "decks"  # keyword to list decks used for this aircraft
        LAYOUT = "layout"  # keyword to detect layout for above deck
        TYPE = "type"  # keyword to detect the action of the button (intend)
        COMMAND = "command"  # keyword to detect (X-Plane) command in definition of the button
        MULTI_COMMANDS = "commands"  # same as above for multiple commands

        DEBUG = False

        config_dn = os.path.join(acpath, CONFIG_DIR)
        if not os.path.isdir(config_dn):
            print(
                self.Info,
                f"get_beginend_commands: Cockpitdecks config directory '{config_dn}' not found in aircraft path '{acpath}'",
            )
            return []

        config_fn = os.path.join(config_dn, CONFIG_FILE)
        if not os.path.exists(config_fn):
            print(
                self.Info,
                f"get_beginend_commands: Cockpitdecks config file '{config_fn}' not found in Cockpitdecks config dir '{config_dn}'",
            )
            return []

        commands = []
        with open(config_fn, "r", encoding="utf-8") as config_fp:
            config = yaml.load(config_fp)
            if DECKS in config:
                for deck in config[DECKS]:
                    if DEBUG:
                        print(
                            self.Info,
                            f"get_beginend_commands: doing deck {deck.get('name')}..",
                        )
                    layout = DEFAULT_LAYOUT
                    if LAYOUT in deck:
                        layout = deck[LAYOUT]
                    layout_dn = os.path.join(config_dn, layout)
                    if not os.path.exists(layout_dn):
                        print(
                            self.Info,
                            f"get_beginend_commands: ..deck {deck.get('name')}: layout folder '{layout}' not found in '{config_dn}'",
                        )
                        continue
                    pages = []
                    for ext in ["yaml", "yml"]:
                        pages = pages + glob.glob(os.path.join(layout_dn, "*." + ext))
                    for page in pages:
                        if os.path.basename(page) == CONFIG_FILE:
                            if DEBUG:
                                print(
                                    self.Info,
                                    f"get_beginend_commands: skipping config file {page}",
                                )
                            continue
                        if DEBUG:
                            print(
                                self.Info,
                                f"get_beginend_commands: doing page {os.path.basename(page)}..",
                            )  #  (file {page})
                        with open(page, "r", encoding="utf-8") as page_fp:
                            page_def = yaml.load(page_fp)
                            if BUTTONS not in page_def:
                                print(
                                    self.Info,
                                    f"get_beginend_commands: page {os.path.basename(page)} has no button (file {page})",
                                )
                                continue
                            for button_def in page_def[BUTTONS]:
                                # if DEBUG:
                                #     print(self.Info, f"get_beginend_commands: doing button {button_def.get('index')}..")
                                bty = button_def.get(TYPE)
                                if bty is None:
                                    if DEBUG:
                                        print(
                                            self.Info,
                                            f"get_beginend_commands: button {button_def} has no type",
                                        )
                                    continue
                                if bty in NOTICABLE_BUTTON_TYPES:
                                    if DEBUG:
                                        print(
                                            self.Info,
                                            f"get_beginend_commands: doing button {button_def.get('index')}",
                                        )
                                    if COMMAND in button_def:
                                        commands.append(button_def[COMMAND])
                                        if DEBUG:
                                            print(
                                                self.Info,
                                                f"get_beginend_commands: added command {button_def[COMMAND]}",
                                            )
                                    if MULTI_COMMANDS in button_def:
                                        for c in button_def[MULTI_COMMANDS]:
                                            commands.append(c)
                                            if DEBUG:
                                                print(
                                                    self.Info,
                                                    f"get_beginend_commands: added multi-command {c}",
                                                )
                                # if DEBUG:
                                #     print(self.Info, f"get_beginend_commands: ..done button {button_def.get('index')}")
                        if DEBUG:
                            print(
                                self.Info,
                                f"get_beginend_commands: ..done page {os.path.basename(page)}",
                            )
                    if DEBUG:
                        print(
                            self.Info,
                            f"get_beginend_commands: ..done deck {deck.get('name')}",
                        )
        return commands

    def get_string_datarefs(self, acpath):
        # Scans an aircraft deckconfig and collects string datarefs.
        #
        # Internal constants (keywords in yaml file)
        #
        BUTTONS = "buttons"  # keyword for button definitions on page
        DECKS = "decks"  # keyword to list decks used for this aircraft
        LAYOUT = "layout"  # keyword to detect layout for above deck
        STRING_DATAREF = "string-dataref"  # keyword to detect (X-Plane) command in definition of the button
        STRING_DATAREFS = "string-datarefs"  #

        DEBUG = False

        config_dn = os.path.join(acpath, CONFIG_DIR)
        if not os.path.isdir(config_dn):
            print(
                self.Info,
                f"get_string_datarefs: Cockpitdecks config directory '{config_dn}' not found in aircraft path '{acpath}'",
            )
            return []

        config_fn = os.path.join(config_dn, CONFIG_FILE)
        if not os.path.exists(config_fn):
            print(
                self.Info,
                f"get_string_datarefs: Cockpitdecks config file '{config_fn}' not found in Cockpitdecks config dir '{config_dn}'",
            )
            return []

        strings = []
        with open(config_fn, "r", encoding="utf-8") as config_fp:
            config = yaml.load(config_fp)
            self.use_defaults = config.get("use-permanent-string-datarefs", LOAD_PERMANENT_DATAREFS)
            ret = config.get("string-datarefs", [])
            if self.trace:
                print(
                    self.Info,
                    f"get_string_datarefs: Cockpitdecks config file '{config_fn}' loaded, config length={len(ret)}, use default={self.use_defaults}.",
                )
            strings = strings + ret
            if DECKS in config:
                for deck in config[DECKS]:
                    if DEBUG:
                        print(
                            self.Info,
                            f"get_string_datarefs: doing deck {deck.get('name')}..",
                        )
                    layout = DEFAULT_LAYOUT
                    if LAYOUT in deck:
                        layout = deck[LAYOUT]
                    layout_dn = os.path.join(config_dn, layout)
                    if not os.path.exists(layout_dn):
                        print(
                            self.Info,
                            f"get_string_datarefs: ..deck {deck.get('name')}: layout folder '{layout}' not found in '{config_dn}'",
                        )
                        continue
                    pages = []
                    for ext in ["yaml", "yml"]:
                        pages = pages + glob.glob(os.path.join(layout_dn, "*." + ext))
                    for page in pages:
                        if os.path.basename(page) == CONFIG_FILE:
                            if DEBUG:
                                print(
                                    self.Info,
                                    f"get_string_datarefs: skipping config file {page}",
                                )
                            continue
                        if DEBUG:
                            print(
                                self.Info,
                                f"get_string_datarefs: doing page {os.path.basename(page)}..",
                            )  #  (file {page})
                        with open(page, "r", encoding="utf-8") as page_fp:
                            page_def = yaml.load(page_fp)
                            if BUTTONS not in page_def:
                                print(
                                    self.Info,
                                    f"get_string_datarefs: page {os.path.basename(page)} has no button (file {page})",
                                )
                                continue
                            for button_def in page_def[BUTTONS]:
                                # if DEBUG:
                                #     print(self.Info, f"get_string_datarefs: doing button {button_def.get('index')}..")
                                sdrefs = button_def.get(STRING_DATAREF)
                                sdrefs = [sdrefs] if sdrefs is not None else []
                                sdrefs = sdrefs + button_def.get(STRING_DATAREFS, [])
                                if sdrefs is None or len(sdrefs) == 0:
                                    # if DEBUG:
                                    #     print(
                                    #         self.Info,
                                    #         f"get_string_datarefs: button {button_def.get('index')} has no string datarefs",
                                    #     )
                                    continue
                                strings = strings + sdrefs
                                if self.trace:
                                    print(
                                        self.Info,
                                        f"get_string_datarefs: deck {deck.get('name')}, layout {layout}, page {os.path.basename(os.path.splitext(page)[0])}, button {button_def.get('index')}: added {sdrefs}",
                                    )
                                continue
                        if DEBUG:
                            print(
                                self.Info,
                                f"get_string_datarefs: ..done page {os.path.basename(page)}",
                            )
                    if DEBUG:
                        print(
                            self.Info,
                            f"get_string_datarefs: ..done deck {deck.get('name')}",
                        )
                if DEBUG:
                    print(
                        self.Info,
                        f"get_string_datarefs: ..done config {config_fn}",
                    )
        return set(strings)

    def load(self, acpath):
        #
        # ###################################################################
        #
        # Load current aircraft string datarefs.
        #
        self.acpath = acpath

        # remove previous command set
        new_dataref_set = {}

        # install this aircraft's set
        datarefs = self.get_string_datarefs(acpath)

        if len(datarefs) == 0:
            print(self.Info, f"load: no string datarefs")
            if self.use_defaults:
                datarefs = PERMANENT_STRING_DATAREFS
                print(self.Info, f"load: using defaults only")
        else:
            if self.use_defaults:
                datarefs = datarefs.union(PERMANENT_STRING_DATAREFS)
                print(self.Info, f"load: added default datarefs")

        self.num_collected_drefs = len(datarefs)

        # Find the data refs we want to record.
        for dataref in datarefs:
            dref = xp.findDataRef(dataref)
            if dref is not None:
                new_dataref_set[dataref] = dref
                if self.trace:
                    print(self.Info, f"load: added string dataref {dataref}")
            else:
                print(self.Info, f"load: dataref {dataref} not found")

        if len(new_dataref_set) > 0:
            with self.RLock:
                self.datarefs = new_dataref_set
            if self.trace:
                print(
                    self.Info,
                    f"load: new dataref set installed {', '.join(new_dataref_set.keys())}",
                )
            # adjust frequency since operation is expensive
            oldf = self.frequency
            self.frequency = min(max(COLLECTION_FREQUENCY + len(self.datarefs) / 2, COLLECTION_FREQUENCY), COLLECTION_FREQUENCY_MAX)
            if oldf != self.frequency and self.trace:
                print(self.Info, f"load: frequency adjusted to {self.frequency}")

        #
        # ###################################################################
        #
        # Load current aircraft "long press" commands.
        #
        #
        # Unload previous aircraft's command set.
        # Load current aircraft command set.
        #
        # remove previous command set
        for k, v in self.commands.items():
            try:
                if FUN in v:  # cached commands have no FUN
                    xp.unregisterCommandHandler(v[REF], v[FUN], 1, None)
                if self.trace:
                    print(self.Info, f"load: unregistered {k}")
            except:
                if self.trace:
                    print(self.Info, "load: exception:")
                print_exc()
                continue

        # install this aircraft's set
        commands = self.get_beginend_commands(acpath)
        if len(commands) > 0:
            for command in commands:
                try:
                    # cmdref = xp.findCommand(command)
                    # if cmdref is not None:
                    # As such, we only check for command existence at execution time.
                    cmd = command + "/begin"
                    self.commands[cmd] = {}
                    self.commands[cmd][REF] = xp.createCommand(cmd, "Begin " + cmd)
                    self.commands[cmd][FUN] = lambda *args, cmd=command: self.command(cmd, True)
                    # self.commands[cmd][FUN] = lambda *args: (xp.commandBegin(cmdref), 0)[1]  # callback must return 0 or 1
                    self.commands[cmd][HDL] = xp.registerCommandHandler(self.commands[cmd][REF], self.commands[cmd][FUN], 1, None)
                    if self.trace:
                        print(self.Info, f"load: added command {cmd}")
                    cmd = command + "/end"
                    self.commands[cmd] = {}
                    self.commands[cmd][REF] = xp.createCommand(cmd, "End " + cmd)
                    self.commands[cmd][FUN] = lambda *args, cmd=command: self.command(cmd, False)
                    # self.commands[cmd][FUN] = lambda *args: (xp.commandEnd(cmdref), 0)[1]  # callback must return 0 or 1
                    self.commands[cmd][HDL] = xp.registerCommandHandler(self.commands[cmd][REF], self.commands[cmd][FUN], 1, None)
                    if self.trace:
                        print(self.Info, f"load: added command {cmd}")
                    # else:
                    #     print(self.Info, f"load: {command} not found")
                except Exception as e:
                    if self.trace:
                        print(self.Info, "load: exception:")
                    print_exc()
        else:
            if self.trace:
                print(self.Info, f"load: no command to add.")

        if self.trace:
            print(self.Info, f"load: {len(self.commands)} commands installed.")


# #####################################################@
# Multicast client
# Adapted from: http://chaos.weblogs.us/archives/164

# import socket

# ANY = "0.0.0.0"

# MCAST_GRP = "239.255.1.1"
# MCAST_PORT = 49505  # (MCAST_PORT is 49707 for XPlane12)

# # Create a UDP socket
# sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)

# # Allow multiple sockets to use the same PORT number
# sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

# # Bind to the port that we know will receive multicast data
# sock.bind((ANY, MCAST_PORT))

# # Tell the kernel that we want to add ourselves to a multicast group
# # The address for the multicast group is the third param
# status = sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, socket.inet_aton(MCAST_GRP) + socket.inet_aton(ANY))

# # setblocking(False) is equiv to settimeout(0.0) which means we poll the socket.
# # But this will raise an error if recv() or send() can't immediately find or send data.
# sock.setblocking(False)

# while 1:
#     try:
#         data, addr = sock.recvfrom(1024)
#     except socket.error as e:
#         pass
#     else:
#         print("From: ", addr)
#         print("Data: ", data)
