# Real Weather METAR and TAF collector
#
import threading
import re
import logging
from functools import reduce
from datetime import datetime, timezone

from avwx import Metar, Station
from suntime import Sun
from zoneinfo import ZoneInfo
from timezonefinder import TimezoneFinder

from .iconfonts import (
    WEATHER_ICONS,
    WEATHER_ICON_FONT,
    DEFAULT_WEATHER_ICON,
)

from cockpitdecks.simulator import SimulatorData

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

# #############
# Local constant
#
KW_NAME = "iconName"  # "cloud",
KW_DAY = "day"  # 2,  0=night, 1=day, 2=day or night
KW_NIGHT = "night"  # 1,
KW_TAGS = "descriptor"  # [],
KW_PRECIP = "precip"  # "RA",
KW_VIS = "visibility"  # [""],
KW_CLOUD = "cloud"  # ["BKN"],
KW_WIND = "wind"  # [0, 21]

WI_PREFIX = "wi_"
DAY = "day_"
NIGHT = "night_"
NIGHT_ALT = "night_alt_"

KW_CAVOK = "clear"  # Special keyword for CAVOK day or night
CAVOK_DAY = "wi_day_sunny"
CAVOK_NIGHT = "wi_night_clear"

LATITUDE = ("sim/flightmodel/position/latitude",)
LONGITUDE = "sim/flightmodel/position/longitude"


class WI:
    """
    Simplified weather icon
    """

    I_S = [
        "_sunny",
        "_cloudy",
        "_cloudy_gusts",
        "_cloudy_windy",
        "_fog",
        "_hail",
        "_haze",
        "_lightning",
        "_rain",
        "_rain_mix",
        "_rain_wind",
        "_showers",
        "_sleet",
        "_sleet_storm",
        "_snow",
        "_snow_thunderstorm",
        "_snow_wind",
        "_sprinkle",
        "_storm_showers",
        "_sunny_overcast",
        "_thunderstorm",
        "_windy",
        "_cloudy_high",
        "_light_wind",
    ]

    DB = [
        {
            KW_NAME: KW_CAVOK,
            KW_TAGS: [],
            KW_PRECIP: "",
            KW_VIS: ["CAVOK", "NCD"],
            KW_CLOUD: [""],
            KW_WIND: [0, 21],
        },
        {
            KW_NAME: "cloud",
            KW_TAGS: [],
            KW_PRECIP: "",
            KW_VIS: [""],
            KW_CLOUD: ["BKN"],
            KW_WIND: [0, 21],
        },
        {
            KW_NAME: "cloudy",
            KW_TAGS: [],
            KW_PRECIP: "",
            KW_VIS: [""],
            KW_CLOUD: ["OVC"],
            KW_WIND: [0, 21],
        },
        {
            KW_NAME: "cloudy-gusts",
            KW_TAGS: [],
            KW_PRECIP: "",
            KW_VIS: [""],
            KW_CLOUD: ["SCT", "BKN", "OVC"],
            KW_WIND: [22, 63],
        },
        {
            KW_NAME: "rain",
            KW_TAGS: [],
            KW_PRECIP: "RA",
            KW_VIS: [""],
            KW_CLOUD: [""],
            KW_WIND: [0, 21],
        },
        {
            KW_NAME: "rain-wind",
            KW_TAGS: [],
            KW_PRECIP: "RA",
            KW_VIS: [""],
            KW_CLOUD: [""],
            KW_WIND: [22, 63],
        },
        {
            KW_NAME: "showers",
            KW_TAGS: ["SH"],
            KW_PRECIP: "",
            KW_VIS: [""],
            KW_CLOUD: [""],
            KW_WIND: [0, 63],
        },
        {
            KW_NAME: "fog",
            KW_TAGS: [],
            KW_PRECIP: "",
            KW_VIS: ["BR", "FG"],
            KW_CLOUD: [""],
            KW_WIND: [0, 63],
        },
        {
            KW_NAME: "storm-showers",
            KW_TAGS: ["TS", "SH"],
            KW_PRECIP: "",
            KW_VIS: [""],
            KW_CLOUD: [""],
            KW_WIND: [0, 63],
        },
        {
            KW_NAME: "thunderstorm",
            KW_TAGS: ["TS"],
            KW_PRECIP: "",
            KW_VIS: [""],
            KW_CLOUD: [""],
            KW_WIND: [0, 63],
        },
        {
            KW_NAME: "windy",
            KW_TAGS: [],
            KW_PRECIP: "",
            KW_VIS: ["CAVOK", "NCD"],
            KW_CLOUD: [""],
            KW_WIND: [22, 33],
        },
        {
            KW_NAME: "strong-wind",
            KW_TAGS: [],
            KW_PRECIP: "",
            KW_VIS: ["CAVOK", "NCD"],
            KW_CLOUD: [""],
            KW_WIND: [34, 63],
        },
        {
            KW_NAME: "cloudy",
            KW_TAGS: [],
            KW_PRECIP: "",
            KW_VIS: [""],
            KW_CLOUD: ["FEW", "SCT"],
            KW_WIND: [0, 21],
        },
        {
            KW_NAME: "cloudy",
            KW_TAGS: [],
            KW_PRECIP: "",
            KW_VIS: [""],
            KW_CLOUD: ["FEW", "SCT"],
            KW_WIND: [0, 21],
        },
        {
            KW_NAME: "cloudy-gusts",
            KW_TAGS: [],
            KW_PRECIP: "",
            KW_VIS: [""],
            KW_CLOUD: ["SCT", "BKN", "OVC"],
            KW_WIND: [22, 63],
        },
        {
            KW_NAME: "cloudy-gusts",
            KW_TAGS: [],
            KW_PRECIP: "",
            KW_VIS: [""],
            KW_CLOUD: ["SCT", "BKN", "OVC"],
            KW_WIND: [22, 63],
        },
        {
            KW_NAME: "cloudy-windy",
            KW_TAGS: [],
            KW_PRECIP: "",
            KW_VIS: [""],
            KW_CLOUD: ["FEW", "SCT"],
            KW_WIND: [22, 63],
        },
        {
            KW_NAME: "cloudy-windy",
            KW_TAGS: [],
            KW_PRECIP: "",
            KW_VIS: [""],
            KW_CLOUD: ["FEW", "SCT"],
            KW_WIND: [22, 63],
        },
        {
            KW_NAME: "snow",
            KW_TAGS: [],
            KW_PRECIP: "SN",
            KW_VIS: [""],
            KW_CLOUD: [""],
            KW_WIND: [0, 21],
        },
        {
            KW_NAME: "snow-wind",
            KW_TAGS: [],
            KW_PRECIP: "SN",
            KW_VIS: [""],
            KW_CLOUD: [""],
            KW_WIND: [22, 63],
        },
    ]

    def __init__(self, day: bool, cover=float, wind=float, precip=float, special=float):
        self.day = day  # night=False, time at location (local time)
        self.cover = cover  # 0=clear, 1=overcast
        self.wind = wind  # 0=no wind, 1=storm
        self.precip = precip  # 0=none, 1=rain1, 2=rain2, 3=snow, 4=hail
        self.special = special  # 0=none, 1=fog, 2=sandstorm


class StationCollector:
    """Set and maintain station for METAR/TAF"""

    def __init__(self, cockpit, config):
        self._inited = False
        self.config = config
        self.cockpit = cockpit

        self.station = None
        self.sun = None
        self._moved = False

        self.update_position = False

        self.icao_dataref_path = config.get("string-dataref")
        self.icao_dataref = None

        self.init()

    def init(self):
        if self._inited:
            return
        self._inited = True
        pass

    def get_simulator_data(self) -> set:
        ret = {LATITUDE, LONGITUDE}
        if self.icao_dataref_path is not None:
            ret.add(self.icao_dataref_path)
        return ret

    def simulator_data_changed(self, data: SimulatorData):
        # what if Dataref.internal_dataref_path("weather:*") change?
        if self.icao_dataref_path is not None:
            if data.name != self.icao_dataref_path:
                return
            icao = data.value()
            if icao is None or icao == "":
                return
            if self.station is not None and icao == self.station.icao:
                return
            self.station = Station.from_icao(icao)
            self.sun = Sun(self.station.latitude, self.station.longitude)
            return
        # then check with lat/lon
        # If we are at the default station, we check where we are to see if we moved.
        lat = self.cockpit.get_simulator_data_value(LATITUDE)
        lon = self.cockpit.get_simulator_data_value(LONGITUDE)

        if lat is not None and lon is not None:
            (nearest, coords) = Station.nearest(lat=lat, lon=lon, max_coord_distance=150000)
            if self.station != nearest:
                self._moved = True
                self.station = nearest
            logger.debug(f"closest station to lat={lat},lon={lon},nearest={nearest},moved={self._moved}")


class MetarCollector:
    def __init__(self, cockpit):
        self.cockpit = cockpit

        # local containers
        self.metar = {}
        self.taf = {}
        self._station = None
        self._last_updated = None

        # Collection thread
        self.metar_collector_run = False
        self.metar_collector_thread = None
        self.metar_collector_last_run = None

    @property
    def station(self):
        return self._station

    @station.setter
    def station(self, station):
        if self._station is None:
            self._stattion = station
            return
        if self._station.icao != station.icao:
            self._station = station
            self.metar = None

    def update_metar(self, create: bool = False):
        if self.metar is None:
            self.metar = Metar(self.station.icao)
        updated = self.metar.update()
        self._last_updated = datetime.now()
        if updated:
            logger.info(f"UPDATED: station {self.station.icao}, Metar updated")
            if before != self.metar.raw and before is not None and before != "":
                logger.info(f"{before}")
                logger.info(f"{self.metar.raw}")
        else:
            logger.debug(f"Metar fetched, no Metar update for station {self.station.icao}")
        return updated

    def start(self):
        if not self.metar_collector_run:
            self.metar_collector_thread = threading.Thread(target=self.run, name="Cockpit::metar_collector")
            self.metar_collector_run = True
            self.metar_collector_thread.start()
            logger.debug("started")
        else:
            logger.warning("already running")

    def stop(self):
        if self.metar_collector_run:
            self.metar_collector_run = False
            logger.debug("stopped")
        else:
            logger.warning("not running")

    def run(self):
        pass
