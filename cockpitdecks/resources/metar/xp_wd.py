# ###########################
# XP Weather METAR
# Attempts to build a METAR from X-Plane weather datarefs
#
# Note: This file is independent from Cockpitdecks (hence it's few hardcoded values)
#       It also requests 2 specific packages (tabulate for debugging) and requests.
#
# Script contains a __main__ section to test it in place.
#
# The name xp_wd.py stands for X-Plane Weather Data.
#
import os
import io
import re
import logging
import json
import math
from enum import Enum
from typing import List
from datetime import datetime, timezone

from tabulate import tabulate
import requests

from metar import Metar
from avwx import Station

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("make_metar")
logger.setLevel(logging.DEBUG)


def distance(origin, destination):
    """
    Calculate the Haversine distance.

    Parameters
    ----------
    origin : tuple of float
        (lat, long)
    destination : tuple of float
        (lat, long)

    Returns
    -------
    distance_in_km : float

    Examples
    --------
    >>> origin = (48.1372, 11.5756)  # Munich
    >>> destination = (52.5186, 13.4083)  # Berlin
    >>> round(distance(origin, destination), 1)
    504.2
    """
    lat1, lon1 = origin
    lat2, lon2 = destination
    radius = 6371  # km

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) * math.sin(dlat / 2) + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) * math.sin(dlon / 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    d = radius * c

    return d


class WEATHER_LOCATION(Enum):
    # From X-Plane, two sources of weather informations
    #
    AIRCRAFT = "aircraft"
    REGION = "region"


CLOUD_TYPE = ["Cirrus", "Stratus", "Cumulus", "Cumulo-nimbus"]

# ######################################################################################
# Mapping between python class instance attributes and datarefs:
# weather.baro get dataref "sim/weather/aircraft/barometer_current_pas" current value.
#
DATAREF_TIME = {
    "local_hours": "sim/cockpit2/clock_timer/local_time_hours",
    "local_minutes": "sim/cockpit2/clock_timer/local_time_minutes",
    "zulu_hours": "sim/cockpit2/clock_timer/zulu_time_hours",
    "zulu_minutes": "sim/cockpit2/clock_timer/zulu_time_minutes",
    "day_of_month": "sim/cockpit2/clock_timer/current_day",
    "day_of_year": "sim/time/local_date_days",
}

DATAREF_LOCATION = {"latitude": "sim/flightmodel/position/latitude", "longitude": "sim/flightmodel/position/longitude"}

DATAREF_AIRCRAFT_WEATHER = {
    "alt_error": "sim/weather/aircraft/altimeter_temperature_error",
    "baro": "sim/weather/aircraft/barometer_current_pas",
    "gravity": "sim/weather/aircraft/gravity_mss",
    "precipitations": "sim/weather/aircraft/precipitation_on_aircraft_ratio",
    "qnh": "sim/weather/aircraft/qnh_pas",
    "rel_humidity": "sim/weather/aircraft/relative_humidity_sealevel_percent",
    "speed_of_sound": "sim/weather/aircraft/speed_sound_ms",
    "temp": "sim/weather/aircraft/temperature_ambient_deg_c",
    "temp_leading_edge": "sim/weather/aircraft/temperature_leadingedge_deg_c",
    "thermal_rete": "sim/weather/aircraft/thermal_rate_ms",
    "visibility": "sim/weather/aircraft/visibility_reported_sm",
    "wave_ampl": "sim/weather/aircraft/wave_amplitude",
    "wave_dir": "sim/weather/aircraft/wave_dir",
    "wave_length": "sim/weather/aircraft/wave_length",
    "wave_speed": "sim/weather/aircraft/wave_speed",
    "wind_dir": "sim/weather/aircraft/wind_now_direction_degt",
    "wind_speed": "sim/weather/aircraft/wind_now_speed_msc",
}

DATAREF_AIRCRAFT_CLOUD = {
    "base": "sim/weather/aircraft/cloud_base_msl_m",
    "coverage": "sim/weather/aircraft/cloud_coverage_percent",
    "tops": "sim/weather/aircraft/cloud_tops_msl_m",
    "cloud_type": "sim/weather/aircraft/cloud_type",  # Blended cloud types per layer. 0 = Cirrus, 1 = Stratus, 2 = Cumulus, 3 = Cumulo-nimbus. Intermediate values are to be expected.
}

DATAREF_AIRCRAFT_WIND = {
    "alt_msl": "sim/weather/aircraft/wind_altitude_msl_m",
    "direction": "sim/weather/aircraft/wind_direction_degt",
    "speed_kts": "sim/weather/aircraft/wind_speed_kts",
    "temp_alotf": "sim/weather/aircraft/temperatures_aloft_deg_c",
    "dew_point": "sim/weather/aircraft/dewpoint_deg_c",
    "turbulence": "sim/weather/aircraft/turbulence",
    "shear_dir": "sim/weather/aircraft/shear_direction_degt",
    "shear_kts": "sim/weather/aircraft/shear_speed_kts",
}

DATAREF_REGION_WEATHER = {
    "change_mode": "sim/weather/region/change_mode",  # How the weather is changing. 0 = Rapidly Improving, 1 = Improving, 2 = Gradually Improving, 3 = Static, 4 = Gradually Deteriorating, 5 = Deteriorating, 6 = Rapidly Deteriorating, 7 = Using Real Weather
    "qnh_base": "sim/weather/region/qnh_base_elevation",
    "qnh_pas": "sim/weather/region/qnh_pas",
    "rain_pct": "sim/weather/region/rain_percent",
    "runway_friction": "sim/weather/region/runway_friction",  # The friction constant for runways (how wet they are). Dry = 0, wet(1-3), puddly(4-6), snowy(7-9), icy(10-12), snowy/icy(13-15)
    "pressure_msl": "sim/weather/region/sealevel_pressure_pas",
    "temperature_msl": "sim/weather/region/sealevel_temperature_c",
    "thermal_rate": "sim/weather/region/thermal_rate_ms",
    "update": "sim/weather/region/update_immediately",  # If this is true, any weather region changes EXCEPT CLOUDS will take place immediately instead of at the next update interval (currently 60 seconds).
    "variability": "sim/weather/region/variability_pct",  # How randomly variable the weather is over distance. Range 0 - 1.
    "visibility": "sim/weather/region/visibility_reported_sm",
    "wave_amp": "sim/weather/region/wave_amplitude",
    "wave_dir": "sim/weather/region/wave_dir",
    "wave_length": "sim/weather/region/wave_length",
    "wave_speed": "sim/weather/region/wave_speed",
    "source": "sim/weather/region/weather_source",
}

DATAREF_REGION_CLOUD = {
    "base": "sim/weather/region/cloud_base_msl_m",
    "coverage": "sim/weather/region/cloud_coverage_percent",
    "tops": "sim/weather/region/cloud_tops_msl_m",
    "cloud_type": "sim/weather/region/cloud_type",
}

DATAREF_REGION_WIND = {
    "alt_msl": "sim/weather/region/atmosphere_alt_levels_m",
    "dew_point": "sim/weather/region/dewpoint_deg_c",
    "temp_aloft": "sim/weather/region/temperatures_aloft_deg_c",
    "temp_alt_msl": "sim/weather/region/temperature_altitude_msl_m",
    "wind_alt_msl": "sim/weather/region/wind_altitude_msl_m",
    "wind_dir": "sim/weather/region/wind_direction_degt",
    "wind_speed": "sim/weather/region/wind_speed_msc",
    "turbulence": "sim/weather/region/turbulence",
    "shear_dir": "sim/weather/region/shear_direction_degt",
    "shear_speed": "sim/weather/region/shear_speed_msc",
}
#
# ######################################################################################

# Flavor
AIRCRAFT_DATAREFS = DATAREF_TIME | DATAREF_LOCATION | DATAREF_AIRCRAFT_WEATHER | DATAREF_AIRCRAFT_CLOUD | DATAREF_AIRCRAFT_WIND
REGION_DATAREFS = DATAREF_TIME | DATAREF_LOCATION | DATAREF_REGION_WEATHER | DATAREF_REGION_CLOUD | DATAREF_REGION_WIND


class DatarefAccessor:
    # Maps an object attribute to a dict entry
    # attr_db = { "temp": "sim/weather/aircraft/temperature_ambient_deg_c" }
    # weather.temp --> self.__datarefs__.get( weather.attr_db.get("temp") )
    def __init__(self, attr_db: dict, drefs: dict, index: int | None = None):
        self.attr_db = attr_db
        self.__datarefs__ = drefs
        self.__drefidx__ = index

    def __getattr__(self, name: str):
        # print("converting", name)
        name = f"{self.attr_db[name]}"
        if self.__drefidx__ is not None:
            name = name + f"[{self.__drefidx__}]"
        # print("getting", name)
        # return dref.value() if dref is not None else None # if dict values are datarefs, not values
        return self.__datarefs__.get(name)


class WindLayer(DatarefAccessor):
    def __init__(self, attr_db: dict, drefs: dict, index):
        DatarefAccessor.__init__(self, attr_db=attr_db, drefs=drefs, index=index)


class CloudLayer(DatarefAccessor):
    def __init__(self, attr_db: dict, drefs: dict, index):
        DatarefAccessor.__init__(self, attr_db=attr_db, drefs=drefs, index=index)


class Weather(DatarefAccessor):
    def __init__(self, attr_db: dict, drefs: dict):
        DatarefAccessor.__init__(self, attr_db=attr_db, drefs=drefs)


class Time(DatarefAccessor):
    def __init__(self, attr_db: dict, drefs: dict):
        DatarefAccessor.__init__(self, attr_db=attr_db, drefs=drefs)


class XPWeatherData:
    # Data accessor shell class.
    # Must be supplied with type/mode of weather (aircraft or region)
    # and wether to force update on first start
    # Make dataref accessible through instance attributes like weather.temp.
    #

    CLOUD_LAYERS = 3
    WIND_LAYERS = 13

    def __init__(self, api_url: str, weather_type: str = WEATHER_LOCATION.REGION.value, update: bool = False):
        self.station = None
        self.weather_type = weather_type
        self.last_updated: datetime | None = None
        self.api_url = api_url
        self.generated_metar = None
        self.weather: Weather | None = None
        self.wind_layers: List[WindLayer] = []  #  Defined wind layers. Not all layers are always defined. up to 13 layers(!)
        self.cloud_layers: List[CloudLayer] = []  #  Defined cloud layers. Not all layers are always defined. up to 3 layers

        self.update_weather(update=update)

    @property
    def cache_filename(self) -> str:
        s = self.station.icao if self.station is not None else "ICAO"
        return f"weather-{s}-{self.weather_type}.json"

    def update(self):
        if self.further_than(kilometers=50):
            self.update_weather()
        elif self.older_than(seconds=30 * 60):
            self.update_weather()
        else:
            logger.info("no update necessary")

    def update_weather(self, update: bool = True):
        DATAREF_WEATHER = AIRCRAFT_DATAREFS if self.weather_type == WEATHER_LOCATION.AIRCRAFT.value else REGION_DATAREFS
        DATAREF_CLOUD = DATAREF_AIRCRAFT_CLOUD if self.weather_type == WEATHER_LOCATION.AIRCRAFT.value else DATAREF_REGION_CLOUD
        DATAREF_WIND = DATAREF_AIRCRAFT_WIND if self.weather_type == WEATHER_LOCATION.AIRCRAFT.value else DATAREF_REGION_WIND

        drefs = self.collect_weather_datarefs(update=update)
        self.weather = Weather(DATAREF_WEATHER, drefs)
        self.wind_layers: List[WindLayer] = []  #  Defined wind layers. Not all layers are always defined. up to 13 layers(!)
        self.cloud_layers: List[CloudLayer] = []  #  Defined cloud layers. Not all layers are always defined. up to 3 layers

        for i in range(self.CLOUD_LAYERS):
            self.cloud_layers.append(CloudLayer(DATAREF_CLOUD, drefs, i))

        for i in range(self.WIND_LAYERS):
            self.wind_layers.append(WindLayer(DATAREF_WIND, drefs, i))

    def collect_weather_datarefs(self, update: bool = True, position_only: bool = False) -> dict:
        if not update:
            if os.path.exists(self.cache_filename):
                data = {}
                with open(self.cache_filename) as fp:
                    data = json.load(fp)
                    self.last_updated = os.path.getmtime(self.cache_filename)
                    if "meta" in data and data["meta"].get("mode") == self.weather_type:
                        t = data["meta"].get("mode")
                        logger.info(f"weather file loaded (mode {t})")
                        del data["meta"]
                        return data
                    else:
                        t = data["meta"].get("mode") if "meta" in data else "no mode"
                        logger.warning(f"weather file mode {t} not same mode {self.weather_type}")
            else:
                logger.warning("weather file not found")

        DATA = "data"
        IDENT = "id"

        def get_dataref_specs(path: str) -> dict | None:
            api_url = self.api_url
            payload = {"filter[name]": path}
            response = requests.get(api_url, params=payload)
            resp = response.json()
            if DATA in resp:
                return resp[DATA][0]
            logger.error(resp)
            return None

        def get_dataref_id(path: str) -> int | None:
            specs = get_dataref_specs(path)
            if specs is not None and IDENT in specs:
                return specs[IDENT]
            logger.error(specs)
            return None

        def get_dataref_value(path: str):
            dref = get_dataref_specs(path)
            if dref is None or IDENT not in dref:
                logger.error(f"error for {path}")
                return None
            url = f"{self.api_url}/{dref[IDENT]}/value"
            response = requests.get(url)
            data = response.json()
            if DATA in data:
                return data[DATA]
            logger.error(f"no value for {path}")
            return None

        WEATHER_DATAFEFS = AIRCRAFT_DATAREFS if self.weather_type == WEATHER_LOCATION.AIRCRAFT.value else REGION_DATAREFS
        if position_only:
            WEATHER_DATAFEFS = DATAREF_LOCATION

        logger.info(f"collecting {self.weather_type} weather datarefs..")
        weather_datarefs = {}
        for d in WEATHER_DATAFEFS.values():
            v = get_dataref_value(d)
            weather_datarefs[d] = v
            logger.debug(f"{d}={v}")
        logger.info(f"..collected {len(weather_datarefs)} datarefs")

        # flatten arrays
        for d, v in weather_datarefs.items():
            if type(v) is list:  # "dataref": [value, value, ...]
                weather_datarefs = weather_datarefs | {f"{d}[{i}]": v[i] for i in range(len(v))}  # "dataref[i]": value(i)

        if os.path.exists(self.cache_filename):
            logger.warning("weather file already exists, overwritten")
        with open(self.cache_filename, "w") as fp:
            weather_datarefs["meta"] = {"mode": self.weather_type, "last-updated": self.last_updated, "generated-metar": self.generated_metar}
            json.dump(weather_datarefs, fp)
            del weather_datarefs["meta"]
            logger.info(f"weather file {os.path.abspath(self.cache_filename)} written")

        self.last_updated = datetime.now().timestamp()
        return weather_datarefs

    def older_than(self, seconds):
        if self.last_updated is None:
            logger.info("no data")
            return True
        now = datetime.now().timestamp()
        logger.info(f"older: {round(now - self.last_updated, 2)} vs {seconds}secs.")
        return now - self.last_updated > seconds

    def further_than(self, kilometers):
        if self.station is None:
            logger.info("no station")
            return True
        position = self.collect_weather_datarefs(position_only=True)
        here = (position["sim/flightmodel/position/latitude"], position["sim/flightmodel/position/longitude"])
        station = (self.station.latitude, self.station.longitude)
        dist = distance(station, here)
        logger.info(f"further: {round(dist, 1)} vs {kilometers}km")
        return dist > kilometers

    def guess_location(self):
        logger.info("location not guessed")

    def get_station(self) -> Station:
        lat = self.weather.latitude
        lon = self.weather.longitude
        return Station.nearest(lat=lat, lon=lon, max_coord_distance=150000)

    def setStation(self, station: Station):
        self.station = station

    # ################################################
    # Layer utility functions
    #
    def sort_layers_by_alt(self):
        # only keeps layers with altitude
        cloud_alts = filter(lambda x: x.base is not None, self.cloud_layers)
        self.cloud_layers = sorted(cloud_alts, key=lambda x: x.base)
        if not len(self.cloud_layers) > 0:
            logger.warning("no cloud layer with altitude?")
        wind_alts = filter(lambda x: x.alt_msl is not None, self.wind_layers)
        self.wind_layers = sorted(wind_alts, key=lambda x: x.alt_msl)
        if not len(self.wind_layers) > 0:
            logger.warning("no wind layer with altitude?")

    def cloud_layer_at(self, alt=0) -> CloudLayer | None:
        # Returns cloud layer at altitude alt (MSL)
        self.sort_layers_by_alt()
        for l in self.cloud_layers:
            if alt <= l.base:
                return l
        return None

    def wind_layer_at(self, alt=0) -> WindLayer | None:
        # Returns wind layer at altitude alt (MSL)
        # Collect level bases with index
        self.sort_layers_by_alt()
        for l in self.wind_layers:
            if alt <= l.alt_msl:
                return l
        return None

    def rnd(self, value):
        if value is not None:
            return round(value, 0)
        return None

    def print_cloud_layers_alt(self):
        i = 0
        for l in self.cloud_layers:
            print(f"[{i}]", self.rnd(getattr(l, "base")), self.rnd(getattr(l, "tops")))
            i = i + 1

    def print_wind_layers_alt(self):
        i = 0
        for l in self.wind_layers:
            print(f"[{i}]", self.rnd(getattr(l, "alt_msl")))
            i = i + 1

    # ################################################
    # Weather values
    #
    def weather_wind(self) -> tuple:  # tuple can be (None, None)
        speed = None
        direct = None
        if len(self.wind_layers) > 0:
            hasalt = list(filter(lambda x: x.alt_msl is not None, self.wind_layers))
            if len(hasalt) > 0:
                lb = sorted(hasalt, key=lambda x: x.alt_msl, reverse=True)
                lowest = lb[0]
                if self.weather_type == WEATHER_LOCATION.AIRCRAFT.value:
                    speed = round(lowest.speed_kts)
                    direct = lowest.direction
                else:
                    speed = round(lowest.wind_speed * 1.943844)
                    direct = lowest.wind_dir
                if speed < 0:  # -1: speed not available
                    speed = None
            else:
                logger.warning("no wind layer with altitude")
        return (speed, direct)

    def weather_visibility(self) -> int | float | None:
        # We use SI, no statute miles
        if self.weather.visibility is None:
            return None
        dist = round(self.weather.visibility * 1609)  ## m
        return 9999 if dist > 9999 else 100 * round(dist / 100)

    def is_cavok(self) -> bool:
        # needs refining according to METAR conventions
        # 1. look at current overall visibility
        nocov = False
        dist = 0
        if self.weather.visibility is not None:
            dist = round(self.weather.visibility * 1609)  ## m
            nocov = True
        # 2. look at each cloud layer coverage
        self.sort_layers_by_alt()
        i = 0
        while nocov and i < len(self.cloud_layers):
            cl = self.cloud_layers[i]
            nocov = cl.coverage is None or cl.coverage < 0.125  # 1/8, some say < 0.05
            i = i + 1
        return dist > 9999 and nocov

    def weather_temperatures(self) -> tuple:  # tuple can be (None, None)
        # Temperature
        t1 = None
        if self.weather_type == WEATHER_LOCATION.AIRCRAFT.value:
            if hasattr(self.weather, "temp") and self.weather.temp is not None:
                t1 = self.weather.temp
        else:
            if hasattr(self.weather, "temperature_msl") and self.weather.temperature_msl is not None:
                t1 = self.weather.temperature_msl
        # Dew point of lowest wind layer
        self.sort_layers_by_alt()
        l = self.wind_layers[0]
        t2 = None
        if hasattr(l, "dew_point") and l.dew_point is not None:
            t2 = l.dew_point
        return (t1, t2)

    def weather_pressure(self) -> str:
        t1 = None
        if self.weather_type == WEATHER_LOCATION.AIRCRAFT.value:
            if hasattr(self.weather, "qnh") and self.weather.qnh is not None:
                t1 = self.weather.qnh
        else:
            if hasattr(self.weather, "qnh_pas") and self.weather.qnh_pas is not None:
                t1 = self.weather.qnh_pas
        return t1

    # ################################################
    # METAR Groups
    #
    def metar_group_station_icao(self, remember: bool = False) -> str:
        (nearest, coords) = self.get_station()
        if nearest is not None and remember:
            self.setStation(nearest)
        return "ICAO" if nearest is None else nearest.icao

    def metar_group_time(self) -> str:
        t = datetime.now().astimezone(tz=timezone.utc)
        m = "00"
        if t.minute > 30:
            m = "30"
        return t.strftime(f"%d%H{m}Z")

    def metar_group_auto(self) -> str:
        return "AUTO"

    def metar_group_wind(self) -> str:
        ret = "00000KT"
        if len(self.wind_layers) > 0:
            hasalt = list(filter(lambda x: x.alt_msl is not None, self.wind_layers))
            if len(hasalt) > 0:
                lb = sorted(hasalt, key=lambda x: x.alt_msl, reverse=True)
                lowest = lb[0]
                speed = 0
                direct = None
                if self.weather_type == WEATHER_LOCATION.AIRCRAFT.value:
                    speed = round(lowest.speed_kts)
                    direct = lowest.direction
                else:
                    speed = round(lowest.wind_speed * 1.943844)
                    direct = lowest.wind_dir
                if direct is None:
                    ret = "VRB"
                else:
                    ret = f"{round(direct):03d}"
                if speed < 0:  # -1: speed not available
                    ret = ret + "//KT"
                else:
                    ret = ret + f"{speed:02d}KT"
                # @todo add gusting later
            else:
                logger.warning("no wind layer with altitude")
        return ret

    def metar_group_visibility(self) -> str:
        # We use SI, no statute miles
        if self.weather.visibility is not None:
            dist = round(self.weather.visibility * 1609)  ## m
            if dist > 9999:
                return "9999"
            dist = 100 * round(dist / 100)
            return f"{dist:04d}"
        else:
            return "NOVIS"

    def metar_group_rvr(self) -> str:
        # if station is an airport and airport has runways
        return ""

    def metar_group_phenomenae(self) -> str:
        # hardest: From
        # 1 Does it rain, snow? does water come down?
        # 2 Surface wind
        # 3 Cloud type, coverage and base of lowest layer
        # 4 Visibility
        # Determine:
        # Heavy/Moderate/Light
        # Weather::
        # BC Patches
        # BL Blowing
        # DL Distant lightning
        # DR Drifting
        # FZ Freezing
        # MI Shallow
        # PR Partial
        # SH Showers
        # TS Thunderstorm
        # VC in the Vicinty
        # Phenomenae::
        # BR Mist
        # DU Dust
        # DS Duststorm
        # DZ Drizzle
        # FC Funnel cloud
        # FG Fog
        # FU Smoke
        # GR Hail
        # GS Small hail/snow pellets
        # HZ Haze
        # PL Ice pellets
        # PO Dust devil
        # RA Rain
        # SA Sand
        # SG Snow grains
        # SN Snow
        # SQ Squall
        # SS Sandstorm
        # VA Volcanic ash
        # UP Unidentified precipitation
        #
        phenomenon = ""
        self.sort_layers_by_alt()
        vis = 9999
        if self.weather_type == WEATHER_LOCATION.AIRCRAFT.value:
            if self.weather.visibility is not None:
                vis = round(self.weather.precipitations)  ## m
            water = 0
            if self.weather.visibility is not None:
                water = round(self.weather.precipitations)  ## m
            lc = self.cloud_layers[0]

        # Mist or fog
        # Water saturation 100%, temp <= dew point temp

        # Rain
        # water > 0, friction decreased
        # may be snow?
        # if temp < 2, friction decreased "sa lot"

        return phenomenon

    def metar_group_clouds(self) -> str:

        def to_fl(m, r: int = 10):
            # Convert meters to flight level (1 FL = 100 ft). Round flight level to r if provided, typically rounded to 10, at Patm = 1013 mbar
            fl = m / 30.48
            if r is not None and r > 0:
                fl = r * int(fl / r)
            return fl

        clouds = ""
        self.sort_layers_by_alt()
        last = -1
        for l in self.cloud_layers:
            local = ""
            cov = int(l.coverage / 0.125) if l.coverage is not None else 0
            # alt = to_fl(l.base, 5)
            # print(l.base, l.base * 3.042, ":", cov)
            if cov >= last:
                s = ""
                if cov > 0 and cov <= 2:
                    s = "FEW"
                elif cov > 2 and cov <= 4:
                    s = "SCT"
                elif cov > 4 and cov <= 7:
                    s = "BKN"
                elif cov > 7:
                    s = "OVC"
                if s != "":
                    alt = to_fl(l.base, 5)
                    local = f"{s}{alt:03d}"
                last = cov
            clouds = clouds + " " + local
        return clouds.strip()

    def metar_group_temperatures(self) -> str:
        def negtemp(temp):
            # format negative temperature (celsius)
            # no temperature is //
            if temp is None or (type(temp) is str and temp == "//"):
                return "//"
            return f"M{abs(temp):02d}" if temp < 0 else f"{t1:02d}"

        # Temperature
        t1 = None
        if self.weather_type == WEATHER_LOCATION.AIRCRAFT.value:
            if hasattr(self.weather, "temp") and self.weather.temp is not None:
                t1 = round(self.weather.temp)
            else:
                t1 = "//"
        else:
            if hasattr(self.weather, "temperature_msl") and self.weather.temperature_msl is not None:
                t1 = round(self.weather.temperature_msl)
            else:
                t1 = "//"
        temp = negtemp(t1)
        # Dew point of lowest wind layer
        self.sort_layers_by_alt()
        l = self.wind_layers[0]
        t1 = None
        if hasattr(l, "dew_point") and l.dew_point is not None:
            t1 = round(l.dew_point)
        else:
            t1 = "//"
        # Can return "/////" if no temp
        temp = temp + "/" + negtemp(t1)
        return temp

    def metar_group_pressure(self) -> str:
        press = None
        if self.weather_type == WEATHER_LOCATION.AIRCRAFT.value:
            press = f"{round(self.weather.qnh/100)}"
        else:
            press = f"{round(self.weather.qnh_pas/100)}"
        return press

    def metar_group_forecast(self) -> str:
        return ""

    def metar_group_remarks(self) -> str:
        return ""

    # ################################################
    # Summary output
    #
    def make_metar(self, alt=None):
        metar = self.metar_group_station_icao(remember=self.station is None)
        metar = metar + " " + self.metar_group_time()
        metar = metar + " " + self.metar_group_auto()
        metar = metar + " " + self.metar_group_wind()
        if self.is_cavok():
            metar = metar + " CAVOK"
            metar = metar + " " + self.metar_group_rvr()
        else:
            metar = metar + " " + self.metar_group_visibility()
            metar = metar + " " + self.metar_group_rvr()
            metar = metar + " " + self.metar_group_phenomenae()
            metar = metar + " " + self.metar_group_clouds()
        metar = metar + " " + self.metar_group_temperatures()
        metar = metar + " " + self.metar_group_pressure()
        metar = metar + " " + self.metar_group_forecast()
        metar = metar + " " + self.metar_group_remarks()
        self.generated_metar = re.sub(" +", " ", metar)  # clean multiple spaces
        return self.generated_metar

    def get_metar_lines(self, layer_index: int = 0) -> list:
        lines = []

        if self.weather is None:
            lines.append(f"Mode: {self.weather_type}")
            lines.append("No weather")
            return lines

        dt = "NO TIME"
        if self.last_updated is not None:
            dt = datetime.fromtimestamp(self.last_updated).strftime("%d %H:%M")
        lines.append(f"{dt} /M:{self.weather_type[0:4]}")

        press = self.weather_pressure()
        press = f"{round(press/100)}" if press is not None else "no pressure"
        lines.append(f"Press: {press}")

        temp, dewp = self.weather_temperatures()
        temp = f"{round(temp)}" if temp is not None else "no temperature"
        lines.append(f"Temp: {temp}")

        vis = self.weather_visibility()
        vis = round(vis, 1) if vis is not None else "no visibility info"
        lines.append(f"Vis: {vis} sm")

        # Wind layer info
        widx = layer_index % len(self.wind_layers)
        currwl = self.wind_layers[widx]

        dewp = round(currwl.dew_point, 1)
        lines.append(f"DewP:{dewp} (W{widx})")

        if self.weather_type == WEATHER_LOCATION.AIRCRAFT.value:
            speed = round(currwl.speed_kts)
            direct = currwl.direction
        else:
            speed = round(currwl.wind_speed * 1.943844)
            direct = currwl.wind_dir
        if direct is None:
            wind_direct_str = "variable"
        else:
            wind_direct_str = f"{round(direct):03d}"
        if speed < 0:  # -1: speed not available
            wind_speed_str = "// kt"
        else:
            wind_speed_str = f"{speed:02d} kt"
        lines.append(f"Winds: {wind_speed_str} {wind_direct_str}° (W{widx})")

        # Cloud layer info
        cidx = layer_index % len(self.cloud_layers)
        currcl = self.cloud_layers[cidx]
        covr8 = int(currcl.coverage * 8)
        covcode = "SKC"
        if 0.5 < covr8 <= 2:
            covcode = "FEW"
        elif 2 < covr8 <= 4:
            covcode = "SCT"
        elif 4 < covr8 <= 7:
            covcode = "BKN"
        else:
            covcode = "OVC"
        lines.append(f"Clouds:{covr8}/8 {covcode} {CLOUD_TYPE[int(currcl.cloud_type)]} (C{cidx})")

        return lines

    def get_metar_desc(self, metar=None):
        if metar is None:
            if self.generated_metar is None:
                metar = self.make_metar()
            else:
                metar = self.generated_metar
        try:
            obs = Metar.Metar(metar)
            return obs.string()
        except:
            logger.warning(f"failed to parse METAR {metar}", exc_info=True)
            return f"METAR parsing failed ({metar})"

    def print(self, level=logging.INFO):
        width = 70
        output = io.StringIO()
        print("\n", file=output)
        print("=" * width, file=output)
        MARK_LIST = ["DATAREF", "VALUE"]
        table = []
        csv = []

        DATAREF_WEATHER = DATAREF_AIRCRAFT_WEATHER if self.weather_type == WEATHER_LOCATION.AIRCRAFT.value else DATAREF_REGION_WEATHER
        DATAREF_CLOUD = DATAREF_AIRCRAFT_CLOUD if self.weather_type == WEATHER_LOCATION.AIRCRAFT.value else DATAREF_REGION_CLOUD
        DATAREF_WIND = DATAREF_AIRCRAFT_WIND if self.weather_type == WEATHER_LOCATION.AIRCRAFT.value else DATAREF_REGION_WIND

        for k, v in DATAREF_WEATHER.items():
            line = (v, getattr(self.weather, k))
            table.append(line)  # print(v, getattr(self.weather, k))
            csv.append(line)
        i = 0
        for l in self.cloud_layers:
            for k, v in DATAREF_CLOUD.items():
                line = (f"{v}[{i}]", getattr(l, k))  # print(f"{v}[{i}]", getattr(l, k))
                table.append(line)
                csv.append(line)
            i = i + 1
        i = 0
        for l in self.wind_layers:
            for k, v in DATAREF_WIND.items():
                line = (f"{v}[{i}]", getattr(l, k))  # print(f"{v}[{i}]", getattr(l, k))
                table.append(line)
                csv.append(line)
            i = i + 1
        # table = sorted(table, key=lambda x: x[0])  # absolute emission time
        print(tabulate(table, headers=MARK_LIST), file=output)
        print("-" * width, file=output)
        print(f"reconstructed METAR: {self.make_metar()}", file=output)
        print("=" * width, file=output)

        # with open(self.cache_filename, "w") as fp:
        #     for l in csv:
        #         print(l[0], l[1], file=fp)

        contents = output.getvalue()
        output.close()
        logger.log(level, f"{contents}")


# Tests
if __name__ == "__main__":
    api_url = "http://192.168.1.140:8080/api/v1/datarefs"
    w = XPWeatherData(api_url=api_url, weather_type=WEATHER_LOCATION.REGION.value, update=True)
    w.print(level=logging.DEBUG)  # writes to logger.debug

    w.print_cloud_layers_alt()
    print("cl base", w.cloud_layer_at(0).base)

    w.print_wind_layers_alt()
    print("wl base", w.wind_layer_at(0).alt_msl)

    print("sample values")
    if w.weather_type == WEATHER_LOCATION.AIRCRAFT.value:
        print("baro", w.weather.baro)
        print("qnh", w.weather.qnh)
    else:
        print("qnh base", w.weather.qnh_pas)
    print("cloud type", w.cloud_layers[2].cloud_type)
    print("wind layer alt", w.wind_layers[7].alt_msl)

    print("generated metar")
    print(w.get_metar_desc())

    # w.update()
