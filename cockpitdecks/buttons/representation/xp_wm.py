# ###########################
# XP Weather METAR
# Attempts to build a METAR from the weather datarefs
#
import sys
import os
import io
import re
import logging

from typing import List
from datetime import datetime, timezone

from metar import Metar
from tabulate import tabulate

# When we are developing this class, we need this to run it standalone
sys.path.append(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)  # we assume we're in subdir "bin/"

from cockpitdecks.simulator import Dataref
from cockpitdecks import to_fl


logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)
# logger.setLevel(logging.DEBUG)

WOFN = "wofn.txt"

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
    # "wave_ampl": "sim/weather/aircraft/wave_amplitude",
    # "wave_dir": "sim/weather/aircraft/wave_dir",
    # "wave_length": "sim/weather/aircraft/wave_length",
    # "wave_speed": "sim/weather/aircraft/wave_speed",
    "wind_speed": "sim/weather/aircraft/wind_speed_msc",
}

DATAREF_AIRCRAFT_CLOUD = {
    "base": "sim/weather/aircraft/cloud_base_msl_m",
    "coverage": "sim/weather/aircraft/cloud_coverage_percent",
    "tops": "sim/weather/aircraft/cloud_tops_msl_m",
    "cloud_type": "sim/weather/aircraft/cloud_type",
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

# Mapping between python class instance attributes and datarefs:
# weather.baro get dataref "sim/weather/aircraft/barometer_current_pas" current value.
#
# PLEASE MAKE SURE YOU USE THE SAME ATTRIBUTE NAME IN AIRCRAFT AND REGION FOR SAME PURPOSE
#
DATAREF_REGION_WEATHER = {
    "change_mode": "sim/weather/region/change_mode",
    "qnh_base": "sim/weather/region/qnh_base_elevation",
    "rain_pct": "sim/weather/region/rain_percent",
    "runway_friction": "sim/weather/region/runway_friction",
    "pressure_msl": "sim/weather/region/sealevel_pressure_pas",
    "temperature_msl": "sim/weather/region/sealevel_temperature_c",
    "thermal_rate": "sim/weather/region/thermal_rate_ms",
    "update": "sim/weather/region/update_immediately",
    "variability": "sim/weather/region/variability_pct",
    "visibility": "sim/weather/region/visibility_reported_sm",
    "wave_amp": "sim/weather/region/wave_amplitude",
    "wave_dir": "sim/weather/region/wave_dir",
    "wave_length": "sim/weather/region/wave_length",
    "wave_speed": "sim/weather/region/wave_speed",
    "source": "sim/weather/region/weather_source",
}

DATAREF_REGION_CLOUD = {
    "base": "sim/weather/region/cloud_base_msl_m",
    "coverage_pct": "sim/weather/region/cloud_coverage_percent",
    "tops": "sim/weather/region/cloud_tops_msl_m",
    "type": "sim/weather/region/cloud_type",
}

DATAREF_REGION_WIND = {
    "alt_levels_m": "sim/weather/region/atmosphere_alt_levels_m",
    "dewpoint": "sim/weather/region/dewpoint_deg_c",
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

DATAREF_WEATHER = DATAREF_AIRCRAFT_WEATHER
DATAREF_CLOUD = DATAREF_AIRCRAFT_CLOUD
CLOUD_LAYERS = 3
DATAREF_WIND = DATAREF_AIRCRAFT_WIND
WIND_LAYERS = 13
DATAREF = DATAREF_TIME | DATAREF_WEATHER | DATAREF_CLOUD | DATAREF_WIND


class DatarefAccessor:
    def __init__(self, drefs, index: int | None = None):
        self.__datarefs__ = drefs
        self.__drefidx__ = index

    def __getattr__(self, name: str):
        #       print("converting", name)
        if self.__drefidx__ is None:
            name = DATAREF[name]
        else:
            name = f"{DATAREF[name]}[{self.__drefidx__}]"
        #       print("getting", name)
        dref = self.__datarefs__.get(name)
        return dref.current_value if dref is not None else None


class WindLayer(DatarefAccessor):
    def __init__(self, drefs, index):
        DatarefAccessor.__init__(self, drefs=drefs, index=index)


class CloudLayer(DatarefAccessor):
    def __init__(self, drefs, index):
        DatarefAccessor.__init__(self, drefs=drefs, index=index)


class Weather(DatarefAccessor):
    def __init__(self, drefs):
        DatarefAccessor.__init__(self, drefs=drefs)


class Time(DatarefAccessor):
    def __init__(self, drefs):
        DatarefAccessor.__init__(self, drefs=drefs)


class Station:
    def __init__(self):
        self.icao = None
        self.iata = None
        self.name = None
        self.name_local = None
        self.lat = None
        self.lon = None
        self.alt = None
        self.tz = None


class Runway:
    def __init__(self):
        self.name = None
        self.orientation = None
        self.length = None
        self.pavement = None
        self.slope = None


class Airport(Station):
    def __init__(self):
        Station.__init__(self)
        self.runways = []


class XPWeather:
    # Data accessor shell class.
    # Must be supplied with dict of {path: Dataref(path)}
    # Make dataref accessible through instance attributes like weather.temperature.
    #
    def __init__(self, drefs):
        self.weather = Weather(drefs)
        self.wind_layers: List[WindLayer] = (
            []
        )  #  Defined wind layers. Not all layers are always defined. up to 13 layers(!)
        self.cloud_layers: List[CloudLayer] = (
            []
        )  #  Defined cloud layers. Not all layers are always defined. up to 3 layers

        for i in range(CLOUD_LAYERS):
            self.cloud_layers.append(CloudLayer(drefs, i))

        for i in range(WIND_LAYERS):
            self.wind_layers.append(WindLayer(drefs, i))

        self.init()

    def init(self):
        self.print(level=logging.DEBUG)  # writes to logger.debug

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

    def make_metar(self, alt=None):
        metar = self.getStation()
        metar = metar + " " + self.getTime()
        metar = metar + " " + self.getAuto()
        metar = metar + " " + self.getWind()
        if self.is_cavok():
            metar = metar + " CAVOK"
            metar = metar + " " + self.getRVR()
        else:
            metar = metar + " " + self.getVisibility()
            metar = metar + " " + self.getRVR()
            metar = metar + " " + self.getPhenomenae()
            metar = metar + " " + self.getClouds()
        metar = metar + " " + self.getTemperatures()
        metar = metar + " " + self.getPressure()
        metar = metar + " " + self.getForecast()
        metar = metar + " " + self.getRemarks()
        return re.sub(" +", " ", metar)  # clean multiple spaces

    def print(self, level=logging.INFO):
        width = 70
        output = io.StringIO()
        print("\n", file=output)
        print("=" * width, file=output)
        MARK_LIST = ["DATAREF", "VALUE"]
        table = []
        csv = []

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

        with open(WOFN, "w") as fp:
            for l in csv:
                print(l[0], l[1], file=fp)

        contents = output.getvalue()
        output.close()
        logger.log(level, f"{contents}")

    def print_cloud_layers_alt(self):
        i = 0
        for l in self.cloud_layers:
            print(f"[{i}]", getattr(l, "base"), getattr(l, "tops"))
            i = i + 1

    def print_wind_layers_alt(self):
        i = 0
        for l in self.wind_layers:
            print(f"[{i}]", getattr(l, "alt_msl"))
            i = i + 1

    def getStation(self):
        return "ICAO"

    def getTime(self):
        t = datetime.now().astimezone(tz=timezone.utc)
        m = "00"
        if t.minute > 30:
            m = "30"
        return t.strftime(f"%d%H{m}Z")

    def getAuto(self):
        return "AUTO"

    def getWind(self):
        ret = "00000KT"
        if len(self.wind_layers) > 0:
            hasalt = list(filter(lambda x: x.alt_msl is not None, self.wind_layers))
            if len(hasalt) > 0:
                lb = sorted(hasalt, key=lambda x: x.alt_msl, reverse=True)
                lowest = lb[0]
                speed = round(lowest.speed_kts)
                direct = lowest.direction
                if direct is None:
                    ret = f"{speed:02d}VRBKT"
                else:
                    direct = round(lowest.direction)
                    ret = f"{direct:03d}{speed:02d}KT"
                # @todo add gusting later
            else:
                logger.warning("no wind layer with altitude")
        return ret

    def is_cavok(self) -> bool:
        # needs refining according to METAR conventions
        # 1. look at current overall visibility
        nocov = False
        if self.weather.visibility is not None:
            dist = round(self.weather.visibility * 1609)  ## m
            nocov = True
        # 2. look at each cloud layer coverage
        self.sort_layers_by_alt()
        i = 0
        while nocov and i < len(self.cloud_layers):
            l = self.cloud_layers[i]
            nocov = l.coverage is None or l.coverage < 0.125  # 1/8
            i = i + 1
        return dist > 9999 and nocov

    def getVisibility(self):
        # We use SI, no statute miles
        if self.weather.visibility is not None:
            dist = round(self.weather.visibility * 1609)  ## m
            if dist > 9999:
                return "9999"
            dist = 100 * round(dist / 100)
            return f"{dist:04d}"
        else:
            return "NOVIS"

    def getRVR(self):
        # if station is an airport and airport has runways
        return ""

    def getPhenomenae(self):
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

    def getClouds(self):
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
                    local = f"{s}{alt}"
                last = cov
            clouds = clouds + " " + local
        return clouds.strip()

    def getTemperatures(self):
        t1 = round(self.weather.temp)
        temp = ""
        if t1 < 0:
            temp = f"M{abs(t1)}/"
        else:
            temp = f"{t1}"
        self.sort_layers_by_alt()
        l = self.wind_layers[0]
        t1 = round(l.dew_point)
        if t1 < 0:
            temp = temp + "/" + f"M{abs(t1)}/"
        else:
            temp = temp + "/" + f"{t1}"
        return temp

    def getPressure(self):
        press = f"{round(self.weather.qnh/100)}"
        return press

    def getForecast(self):
        return ""

    def getRemarks(self):
        return ""

    def get_metar_desc(self, metar=None):
        if metar is None:
            metar = self.make_metar()
        try:
            obs = Metar.Metar(metar)
            return obs.string()
        except:
            logger.warning(f"failed to parse METAR {metar}", exc_info=True)
            return f"METAR parsing failed ({metar})"


# Tests
if __name__ == "__main__":
    drefs = {}
    with open(os.path.join("..", "..", "..", WOFN), "r") as fp:
        line = fp.readline()
        line = line.strip().rstrip("\n\r")
        while line:
            if len(line) > 2:
                arr = line.split()
                dref = Dataref(arr[0])
                dref.current_value = float(arr[1])
                drefs[arr[0]] = dref
            line = fp.readline()

    w = XPWeather(drefs)
    print(w.get_metar_desc())
    # w.print()
    # w.print_cloud_layers_alt()
    # print("cl base", w.cloud_layer_at(0).base)
    # w.print_wind_layers_alt()
    # print("wl base", w.wind_layer_at(0).alt_msl)
    # print(w.weather.baro)
    # print(w.cloud_layers[2].cloud_type)
    # print(w.wind_layers[7].alt_msl)
