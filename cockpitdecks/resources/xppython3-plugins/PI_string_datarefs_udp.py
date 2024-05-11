"""
Little plugin that reads string-type datarefs and multicast them at regular interval.
(I use it to fetch Toliss Airbus FMA text lines. But can be used to multicast any string-typed dataref.)
Return value is JSON {dataref-path: dataref-value} dictionary.
Return value must be smaller than 1472 bytes.
"""

import os
import glob
import socket
import time
import json
import ruamel
from ruamel.yaml import YAML
from traceback import print_exc
from threading import RLock

from XPPython3 import xp

ruamel.yaml.representer.RoundTripRepresenter.ignore_aliases = lambda x, y: True
yaml = YAML(typ="safe", pure=True)

RELEASE = "3.0.3"

# Changelog:
#
# 08-MAY-2024: 3.0.3: Trying to reload missing datarefs..
# 08-MAY-2024: 3.0.2: Attempts to reload aircraft if not loaded after MSG_PLANE_LOADED message.
# 08-MAY-2024: 3.0.1: Limited defaults to acf_icao.
# 07-MAY-2024: 3.0.0: Now scan all button definitions for string-datarefs: [] attribute.
# 02-MAY-2024: 2.0.5: Now changing dataref set in one operation to minimize impact on flightloop
# 23-APR-2024: 2.0.4: Now reading from config.yaml for aircraft.
# 22-DEC-2023: 1.0.0: Initial version.
#

MCAST_GRP = "239.255.1.1"  # same as X-Plane 12
MCAST_PORT = 49505  # 49707 for XPlane12
MCAST_TTL = 2

FREQUENCY = 5.0  # will run every FREQUENCY seconds at most, never faster

CONFIG_DIR = "deckconfig"
CONFIG_FILE = "config.yaml"
DEFAULT_LAYOUT = "default"


DEFAULT_STRING_DATAREFS = [
    "sim/aircraft/view/acf_ICAO"
]  # default is to return these, for Toliss Airbusses

CHECK_COUNT = [5, 20]


class PythonInterface:
    def __init__(self):
        self.Name = "String datarefs multicast"
        self.Sig = "xppython3.strdrefmcast"
        self.Desc = f"Fetches string-type datarefs at regular intervals and UPD multicast their values (Rel. {RELEASE})"
        self.Info = self.Name + f" (rel. {RELEASE})"
        self.enabled = False
        self.trace = (
            True  # produces extra print/debugging in XPPython3.log for this class
        )
        self.acpath = ""
        self.datarefs = {}
        self.use_defaults = False
        self.run_count = 0
        self.num_collected_drefs = 0
        self.frequency = FREQUENCY

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, MCAST_TTL)
        self.RLock = RLock()

    def XPluginStart(self):
        if self.trace:
            print(self.Info, "started")

        return self.Name, self.Sig, self.Desc

    def XPluginStop(self):
        if self.trace:
            print(self.Info, "stopped")

    def XPluginEnable(self):
        xp.registerFlightLoopCallback(self.FlightLoopCallback, 1.0, 0)
        if self.trace:
            print(self.Info, "PI::XPluginEnable: flight loop registered")
        try:
            ac = xp.getNthAircraftModel(
                0
            )  # ('Cessna_172SP.acf', '/Volumns/SSD1/X-Plane/Aircraft/Laminar Research/Cessna 172SP/Cessna_172SP.acf')
            if len(ac) == 2:
                acpath = os.path.split(
                    ac[1]
                )  # ('/Volumns/SSD1/X-Plane/Aircraft/Laminar Research/Cessna 172SP', 'Cessna_172SP.acf')
                print(self.Info, "PI::XPluginEnable: trying " + acpath[0] + " ..")
                self.load(acpath=acpath[0])
                print(self.Info, "PI::XPluginEnable: " + acpath[0] + " done.")
                self.enabled = True
                if self.trace:
                    print(self.Info, "enabled")
                return 1
            print(
                self.Info, "PI::XPluginEnable: getNthAircraftModel: aircraft not found."
            )
            return 1
        except:
            if self.trace:
                print(self.Info, "PI::XPluginEnable: exception.")
            print_exc()
            self.enabled = False
            if self.trace:
                print(self.Info, "not enabled")
        return 0

    def XPluginDisable(self):
        xp.unregisterFlightLoopCallback(self.FlightLoopCallback, 0)
        if self.trace:
            print(self.Info, "PI::XPluginDisable: flight loop unregistered")
        self.enabled = False
        if self.trace:
            print(self.Info, "disabled")

    def XPluginReceiveMessage(self, inFromWho, inMessage, inParam):
        """
        When we receive a message that an aircraft was loaded, if it is the user aircraft,
        we try to load the aicraft deskconfig.
        If it does not exist, we default to a screen saver type of screen for the deck.
        """
        if (
            inMessage == xp.MSG_PLANE_LOADED and inParam == 0
        ):  # 0 is for the user aircraft, greater than zero will be for AI aircraft.
            print(self.Info, "PI::XPluginReceiveMessage: user aircraft received")
            try:
                ac = xp.getNthAircraftModel(
                    0
                )  # ('Cessna_172SP.acf', '/Volumns/SSD1/X-Plane/Aircraft/Laminar Research/Cessna 172SP/Cessna_172SP.acf')
                if len(ac) == 2:
                    acpath = os.path.split(
                        ac[1]
                    )  # ('/Volumns/SSD1/X-Plane/Aircraft/Laminar Research/Cessna 172SP', 'Cessna_172SP.acf')
                    if self.trace:
                        print(
                            self.Info,
                            "PI::XPluginReceiveMessage: trying " + acpath[0] + "..",
                        )
                    self.load(acpath=acpath[0])
                    if self.run_count > 0:
                        print(
                            self.Info,
                            "PI::XPluginReceiveMessage: old run count "
                            + str(self.run_count)
                            + ", run count reset",
                        )
                        self.run_count = 0
                    if self.trace:
                        print(
                            self.Info,
                            "PI::XPluginReceiveMessage: .. " + acpath[0] + " done.",
                        )
                    return None
                print(
                    self.Info,
                    "PI::XPluginReceiveMessage: getNthAircraftModel: aircraft not found.",
                )
            except:
                if self.trace:
                    print(self.Info, "PI::XPluginReceiveMessage: exception.")
                print_exc()
                self.enabled = False
        return None

    def FlightLoopCallback(self, elapsedMe, elapsedSim, counter, refcon):
        if not self.enabled:
            return 0
        if self.run_count % 100 == 0:
            print(self.Info, f"PI::FlightLoopCallback: is alive ({self.run_count})")
        elif self.run_count in CHECK_COUNT:
            if len(self.datarefs) < self.num_collected_drefs and (
                self.acpath is not None and len(self.acpath) > 0
            ):
                print(
                    self.Info,
                    f"PI::FlightLoopCallback: is alive ({self.run_count}), missing string datarefs {len(self.datarefs)}/{self.num_collected_drefs} for {self.acpath}",
                )
                self.load(acpath=self.acpath)
            else:
                print(
                    self.Info,
                    f"PI::FlightLoopCallback: is alive ({self.run_count}), {len(self.datarefs)}/{self.num_collected_drefs} string datarefs for {self.acpath}",
                )
        self.run_count = self.run_count + 1
        with self.RLock:  # add a meta data to sync effectively
            drefvalues = {"ts": time.time(), "f": self.frequency} | {
                d: xp.getDatas(self.datarefs[d]) for d in self.datarefs
            }
        fma_bytes = bytes(
            json.dumps(drefvalues), "utf-8"
        )  # no time to think. serialize as json
        # if self.trace:
        #     print(self.Info, fma_bytes.decode("utf-8"))
        if len(fma_bytes) > 1472:
            print(
                self.Info,
                f"PI::FlightLoopCallback: returned value too large ({len(fma_bytes)}/1472)",
            )
        else:
            self.sock.sendto(fma_bytes, (MCAST_GRP, MCAST_PORT))
        return self.frequency

    def load(self, acpath):
        # Load current aircraft string datarefs.
        #
        self.acpath = acpath

        # remove previous command set
        new_dataref_set = {}

        # install this aircraft's set
        datarefs = self.get_string_datarefs(acpath)
        self.num_collected_drefs = len(datarefs)

        if len(datarefs) == 0:
            print(self.Info, f"PI::load: no string datarefs")
            if self.use_defaults:
                datarefs = DEFAULT_STRING_DATAREFS
                print(self.Info, f"PI::load: using defaults")

        # Find the data refs we want to record.
        for dataref in datarefs:
            dref = xp.findDataRef(dataref)
            if dref is not None:
                new_dataref_set[dataref] = dref
                if self.trace:
                    print(self.Info, f"PI::load: added string dataref {dataref}")
            else:
                print(self.Info, f"PI::load: dataref {dataref} not found")

        if len(new_dataref_set) > 0:
            with self.RLock:
                self.datarefs = new_dataref_set
            if self.trace:
                print(
                    self.Info,
                    f"PI::load: new dataref set installed {', '.join(new_dataref_set.keys())}",
                )
            # adjust frequency since operation is expensive
            oldf = self.frequency
            self.frequency = max(len(self.datarefs), FREQUENCY)
            if oldf != self.frequency and self.trace:
                print(self.Info, f"PI::load: frequency adjusted to {self.frequency}")

    def get_string_datarefs(self, acpath):
        # Scans an aircraft deckconfig and collects string datarefs.
        #
        # Internal constants (keywords in yaml file)
        #
        BUTTONS = "buttons"  # keyword for button definitions on page
        DECKS = "decks"  # keyword to list decks used for this aircraft
        LAYOUT = "layout"  # keyword to detect layout for above deck
        STRING_DATAREFS = "string-datarefs"  # keyword to detect (X-Plane) command in definition of the button

        DEBUG = False

        config_dn = os.path.join(acpath, CONFIG_DIR)
        if not os.path.isdir(config_dn):
            print(
                self.Info,
                f"PI::get_string_datarefs: Cockpitdecks config directory '{config_dn}' not found in aircraft path '{acpath}'",
            )
            return []

        config_fn = os.path.join(config_dn, CONFIG_FILE)
        if not os.path.exists(config_fn):
            print(
                self.Info,
                f"PI::get_string_datarefs: Cockpitdecks config file '{config_fn}' not found in Cockpitdecks config dir '{config_dn}'",
            )
            return []

        strings = []
        with open(config_fn, "r", encoding="utf-8") as config_fp:
            config = yaml.load(config_fp)
            self.use_defaults = config.get("use-default-string-datarefs", False)
            ret = config.get("string-datarefs", [])
            if self.trace:
                print(
                    self.Info,
                    f"PI::get_string_datarefs: Cockpitdecks config file '{config_fn}' loaded, config length={len(ret)}, use default={self.use_defaults}.",
                )
            strings = strings + ret
            if DECKS in config:
                for deck in config[DECKS]:
                    if DEBUG:
                        print(
                            self.Info,
                            f"PI::get_string_datarefs: doing deck {deck.get('name')}..",
                        )
                    layout = DEFAULT_LAYOUT
                    if LAYOUT in deck:
                        layout = deck[LAYOUT]
                    layout_dn = os.path.join(config_dn, layout)
                    if not os.path.exists(layout_dn):
                        print(
                            self.Info,
                            f"PI::get_string_datarefs: ..deck {deck.get('name')}: layout folder '{layout}' not found in '{config_dn}'",
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
                                    f"PI::get_string_datarefs: skipping config file {page}",
                                )
                            continue
                        if DEBUG:
                            print(
                                self.Info,
                                f"PI::get_string_datarefs: doing page {os.path.basename(page)}..",
                            )  #  (file {page})
                        with open(page, "r", encoding="utf-8") as page_fp:
                            page_def = yaml.load(page_fp)
                            if BUTTONS not in page_def:
                                print(
                                    self.Info,
                                    f"PI::get_string_datarefs: page {os.path.basename(page)} has no button (file {page})",
                                )
                                continue
                            for button_def in page_def[BUTTONS]:
                                # if DEBUG:
                                #     print(self.Info, f"PI::get_string_datarefs: doing button {button_def.get('index')}..")
                                sdrefs = button_def.get(STRING_DATAREFS)
                                if sdrefs is None:
                                    # if DEBUG:
                                    #     print(
                                    #         self.Info,
                                    #         f"PI::get_string_datarefs: button {button_def.get('index')} has no string datarefs",
                                    #     )
                                    continue
                                strings = strings + sdrefs
                                if self.trace:
                                    print(
                                        self.Info,
                                        f"PI::get_string_datarefs: deck {deck.get('name')}, layout {layout}, page {os.path.basename(os.path.splitext(page)[0])}, button {button_def.get('index')}: added {sdrefs}",
                                    )
                                continue
                        if DEBUG:
                            print(
                                self.Info,
                                f"PI::get_string_datarefs: ..done page {os.path.basename(page)}",
                            )
                    if DEBUG:
                        print(
                            self.Info,
                            f"PI::get_string_datarefs: ..done deck {deck.get('name')}",
                        )
                if DEBUG:
                    print(
                        self.Info,
                        f"PI::get_string_datarefs: ..done config {config_fn}",
                    )
        return set(strings)


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
