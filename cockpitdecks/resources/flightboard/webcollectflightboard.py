import requests
import base64
from datetime import datetime

# BASE_URL = "http://localhost:8086/api/v1/datarefs"
BASE_URL = "http://192.168.1.140:8080/api/v1/datarefs"
DATA = "data"
IDENT = "id"
NAME = "name"


def get_dataref_value_by_id(ident: int, nullas: str = ""):
    url = f"{BASE_URL}/{ident}/value"
    response = requests.get(url)
    data = response.json()
    if DATA in data and type(data[DATA]) in [bytes, str]:
        return base64.b64decode(data[DATA])[:-1].decode("ascii").replace("\u0000", nullas)
    return data[DATA]


# sim/multiplayer/position/plane23_prop
ACBASE = "sim/multiplayer/position/plane"
ACPROPS = ["tailnum", "ICAO", "manufacturer", "model", "ICAOairline", "airline", "flightnum", "apt_from", "apt_to", "cslModel"]
ACBOOT = ["tailnum", "flightnum", "cslModel"]  # these are checked first for existence
ACUNBOOT = [s for s in ACPROPS if s not in ACBOOT]


class Aircraft:

    def __init__(self, index: int) -> None:
        self.index = index
        self.props: dict = {p: "" for p in ACPROPS}
        self._last_updated = datetime.now()

    def __str__(self):
        p = self.props
        return f'{p["ICAOairline"].ljust(4)} {p["flightnum"].ljust(7)} {p["apt_from"].ljust(4)} {p["apt_to"].ljust(4)} {p["ICAO"].ljust(4)} {p["tailnum"].ljust(7)}'

    def datarefs(self):
        return [f"{ACBASE}{self.index}_{s}" for s in self.props.keys()]

    def defined(self) -> bool:
        for p in ACBOOT:
            if self.props[p].strip() != "":
                return True
        return False

    def collect(self, ids) -> bool:
        self.props = {s: get_dataref_value_by_id(ids[f"{ACBASE}{self.index}_{s}"]) for s in ACBOOT}
        if self.defined():
            self.props = self.props | {s: get_dataref_value_by_id(ids[f"{ACBASE}{self.index}_{s}"]) for s in ACUNBOOT}
            self._last_updated = datetime.now()
            return True
        return False


class TCASEntry:
    def __init__(self, props: dict) -> None:
        self.index = props.get("index")
        self.props = props
        self._last_updated = datetime.now()

    def __str__(self):
        p = self.props
        # return f'{self.props["flight_id"]}/{self.index}'
        return f'{p["index"]:2d} {p["flight_id"].ljust(7)} {p["icao24"].ljust(4)} {p["actype"].ljust(4)} {p["squawk"]:4d}'

    def defined(self) -> bool:
        for p in self.props.keys():
            if p == "index":
                continue
            if type(self.props[p]) is str and self.props[p].strip() not in ["", "0", "000000"]:
                return True
            if type(self.props[p]) in [int, float] and int(self.props[p]) != 0:
                return True
        return False

    def update(self, data):
        self._last_updated = datetime.now()


class DatarefCollector:

    TCAS_DATAREFS = [
        "sim/cockpit2/tcas/targets/modeS_id",  #  int[64] y   integer 24bit (0-16777215 or 0 - 0xFFFFFF) unique ID of the airframe. This is also known as the ADS-B "hexcode".
        "sim/cockpit2/tcas/targets/modeC_code",  #    int[64] y   integer Mode C transponder code 0000 to 7777. This is not really an integer, this is an octal number.
        "sim/cockpit2/tcas/targets/flight_id",  # byte[512]   y   string  7 character Flight ID, terminated by 0 byte. ICAO flightplan item 7.
        "sim/cockpit2/tcas/targets/icao_type",  # byte[512]   y   string  7 character ICAO code, terminated by 0 byte. C172, B738, etc... see https://www.icao.int/publications/DOC8643/Pages/Search.aspx
    ]

    def __init__(self) -> None:
        self.aircrafts = []
        self.tcas = {}
        self.tcas_datarefs = {}
        self.ac_datarefs = {}

        self.init()

    def get_all_dataref_specs(self, datarefs) -> dict | None:
        payload = "&".join([f"filter[name]={path}" for path in datarefs])
        response = requests.get(BASE_URL, params=payload)
        resp = response.json()
        return resp[DATA]

    def init(self):
        all_dataref_descs = self.get_all_dataref_specs(self.TCAS_DATAREFS)
        self.tcas_datarefs = {d.get(NAME): d.get(IDENT) for d in all_dataref_descs}
        all_dataref_descs = []
        for j in range(0, 8):
            datarefs = []
            for i in range(j * 8, (j + 1) * 8):
                if i == 0:
                    continue
                a = Aircraft(i)
                self.aircrafts.append(a)
                datarefs = datarefs + a.datarefs()
            all_dataref_descs = all_dataref_descs + self.get_all_dataref_specs(datarefs)
        self.ac_datarefs = {d.get(NAME): d.get(IDENT) for d in all_dataref_descs}
        print("inited")

    def load_ac(self):
        for a in self.aircrafts:
            if a.collect(self.ac_datarefs):
                print(f"{a.index:2d}", a)

    def load_tcas(self):
        # collect
        a = {
            s: get_dataref_value_by_id(
                self.tcas_datarefs[s], nullas=" " if s in ["sim/cockpit2/tcas/targets/flight_id", "sim/cockpit2/tcas/targets/icao_type"] else ""
            )
            for s in self.TCAS_DATAREFS
        }
        # split and reformat
        a["sim/cockpit2/tcas/targets/modeS_id"] = [f"{i:06x}" for i in a["sim/cockpit2/tcas/targets/modeS_id"]]
        a["sim/cockpit2/tcas/targets/flight_id"] = [
            a["sim/cockpit2/tcas/targets/flight_id"][0 + i : 8 + i].replace(" ", "") for i in range(0, len(a["sim/cockpit2/tcas/targets/flight_id"]), 8)
        ]
        a["sim/cockpit2/tcas/targets/icao_type"] = [
            a["sim/cockpit2/tcas/targets/icao_type"][0 + i : 8 + i].replace(" ", "") for i in range(0, len(a["sim/cockpit2/tcas/targets/icao_type"]), 8)
        ]
        # create dict
        minlen = min([len(a[x]) for x in a])
        self.tcas = [
            TCASEntry(
                {
                    "index": i+1,
                    "icao24": a["sim/cockpit2/tcas/targets/modeS_id"][i],
                    "flight_id": a["sim/cockpit2/tcas/targets/flight_id"][i],
                    "squawk": a["sim/cockpit2/tcas/targets/modeC_code"][i],
                    "actype": a["sim/cockpit2/tcas/targets/icao_type"][i],
                }
            )
            for i in range(minlen)
        ]
        used = sorted([str(c) for c in self.tcas if c.defined()])
        print(f"{len(used)} TCAS:\n{'\n'.join(used)}")


f = DatarefCollector()
f.load_tcas()
f.load_ac()

# LiveTraffic Attributes:
#
# Key
# Кеу Туре
# ID
# Registration
# Type
# Class
# Manufacturer
# Model
# Category Descr.
# Operator
# Call Sign
# squawk
# Flight
# Route
# Update
# Position
# Lat
# Lon
# Altitude
# AGL
# VSI
# kn
# Track
# Heading
# Pitch
# Roll
# Bearing
# Distance
# CSL Model
# Last Data
# Channel
# Phase
# Gear
# Flaps
# Lights
# TCAS Idx
# Flight Model
# Actions
