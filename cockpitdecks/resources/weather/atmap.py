import re
from typing import Union
from avwx import Metar, Taf
from avwx.structs import MetarData, TafData, TafLineData, Units


class Atmap:
    def __init__(self, data: Union[MetarData, TafLineData], units: Units, min_temp: float = None):
        self.data = data
        self.units = units
        self.min_temp = min_temp
        self.wx = self._parse_wx()

    @classmethod
    def from_metar(cls, report: str):
        report = report.strip()
        m = Metar.from_report(report)
        obj = cls(data=m.data, units=m.units)
        return obj

    @classmethod
    def metar(cls, station: str):
        m = Metar(station)
        m.update()
        obj = cls(data=m.data, units=m.units)
        return obj

    @classmethod
    def taf(cls, station: str):
        t = Taf(station)
        t.update()
        return cls._get_taf(t)

    @classmethod
    def from_taf(cls, report: str):
        report = report.strip()
        t = Taf.from_report(report)
        return cls._get_taf(t)

    @classmethod
    def _get_taf(cls, taf: Taf):
        r = []
        min_temp = Atmap._parse_min_temp(taf.data)
        for data in taf.data.forecast:
            obj = cls(data=data, units=taf.units, min_temp=min_temp)
            r.append(
                {
                    "start_time": data.start_time.dt,
                    "end_time": data.end_time.dt,
                    "probability": (data.probability.value if data.probability is not None else None),
                    "atmap": obj,
                }
            )
        return r

    @property
    def ceiling(self):
        return self._get_visibility_ceiling_coef()

    @property
    def wind(self):
        return self._get_wind_coef()

    @property
    def precip(self):
        return self._get_precipitation_coef()

    @property
    def freezing(self):
        return self._get_freezing_coef()

    @property
    def phenomena(self):
        return self._get_dangerous_phenomena_coef()

    @staticmethod
    def _parse_min_temp(taf_data: TafData):
        temp = taf_data.min_temp if taf_data.min_temp is not None else taf_data.max_temp
        if temp is None:
            return None

        tmp_search = re.search(r"^(?P<temp>(TN(M)?(\d{1,2})))", temp)
        _, min_temp = tmp_search.group(1, 4)
        min_temp = float(min_temp)
        if tmp_search.group(1, 3)[1] is not None:
            min_temp = min_temp * -1

        return min_temp

    def _parse_wx(self):
        weather = []
        pattern = re.compile(
            r"^(?P<int>(-|\+|VC)*)(?P<desc>(MI|PR|BC|DR|BL|SH|TS|FZ)+)?(?P<prec>(DZ|RA|SN|SG|IC|PL|GR|GS|UP|/)*)(?P<obsc>BR|FG|FU|VA|DU|SA|HZ|PY)?(?P<other>PO|SQ|FC|SS|DS|NSW|/+)?(?P<int2>[-+])?",
            re.VERBOSE,
        )
        for code in self.data.wx_codes:
            match = pattern.search(code.repr).groupdict()
            intensity, desc, precip, obs, other, intensityt = match.values()
            if not intensity and intensityt:
                intensity = intensityt

            weather.append((intensity, desc, precip, obs, other))
        return weather

    def _get_dangerous_phenomena_coef(self):
        if not self._assert_cloud_data():
            return None

        phenomena, showers = self.__dangerous_weather()
        cb, tcu, ts = self.__dangerous_clouds()
        if showers is not None and showers > 0:
            if cb == 12:
                ts = 18 if showers == 1 else 24

            if cb == 10 or tcu == 10:
                ts = 12 if showers == 1 else 20

            if cb == 6 or tcu == 8:
                ts = 10 if showers == 1 else 15

            if cb == 4 or tcu == 5:
                ts = 8 if showers == 1 else 12

            if tcu == 3:
                ts = 4 if showers == 1 else 6

        return max(i for i in [phenomena, cb, tcu, ts] if i is not None)

    def _assert_cloud_data(self):
        return self.data.clouds is not None

    def __dangerous_weather(self):
        phenomena = None
        showers = None
        for intensity, desc, precip, obs, other in self.wx:
            __phenomena = 0
            __showers = 0
            if other in ["FC", "DS", "SS"] or obs in ["VA", "SA"] or precip in ["GR", "PL"]:
                __phenomena = 24

            if desc == "TS":
                __phenomena = 30 if intensity == "+" else 24

            if precip == "GS":
                __phenomena = 18

            if phenomena is None or __phenomena > phenomena:
                phenomena = __phenomena

            if desc == "SH":
                __showers = 1 if intensity == "-" else 2

            if showers is None or __showers > showers:
                showers = __showers

        return (phenomena, showers)

    def __dangerous_clouds(self):
        cb = 0
        tcu = 0
        for cloud in self.data.clouds:
            __cb = 0
            __tcu = 0
            if cloud.type == "OVC":
                if cloud.modifier == "TCU":
                    __tcu = 10

                if cloud.modifier == "CB":
                    __cb = 12

            if cloud.type == "BKN":
                if cloud.modifier == "TCU":
                    __tcu = 8

                if cloud.modifier == "CB":
                    __cb = 10

            if cloud.type == "SCT":
                if cloud.modifier == "TCU":
                    __tcu = 5

                if cloud.modifier == "CB":
                    __cb = 6

            if cloud.type == "FEW":
                if cloud.modifier == "TCU":
                    __tcu = 3

                if cloud.modifier == "CB":
                    __cb = 4

            if __cb > cb:
                cb = __cb

            if __tcu > tcu:
                tcu = __tcu

        return (cb, tcu, None)

    def _get_wind_coef(self):
        if not self._assert_wind_data():
            return None

        spd = self.data.wind_speed.value
        gusts = self.data.wind_gust.value if self.data.wind_gust is not None else None
        if self.units.wind_speed == "kmh":
            spd = self.__kmh_to_kt(spd)
            gusts = self.__kmh_to_kt(gusts)
        if self.units.wind_speed == "mps":
            spd = self.__mps_to_kt(spd)
            gusts = self.__mps_to_kt(gusts)

        coef = 0
        if 16 <= spd <= 20:
            coef = 1

        if 21 <= spd <= 30:
            coef = 2

        if spd > 30:
            coef = 4

        if gusts is not None:
            coef += 1

        return coef

    def _assert_wind_data(self):
        return self.data.wind_speed is not None

    def _get_precipitation_coef(self):
        coef = 0
        for intensity, desc, precip, obs, other in self.wx:
            __coef = 0
            if desc == "FZ":
                __coef = 3

            if precip == "SN":
                __coef = 2 if intensity == "-" else 3

            if precip == "SG" or (precip == "RA" and intensity == "+"):
                __coef = 2

            if precip in ["RA", "UP", "IC", "DZ"]:
                __coef = 1

            if __coef > coef:
                coef = __coef

        return coef

    def _get_freezing_coef(self):
        if not self._assert_temperature_data():
            return None

        tt = self.data.temperature.value if type(self.data) == MetarData else self.min_temp
        dp = self.data.dewpoint.value if type(self.data) == MetarData else None
        moisture = None
        for intensity, desc, precip, obs, other in self.wx:
            __moisture = None
            if desc == "FZ":
                __moisture = 5

            if precip == "SN":
                __moisture = 4 if intensity == "-" else 5

            if precip in ["SG", "RASN"] or (precip == "RA" and intensity == "+") or obs == "BR":
                __moisture = 4

            if precip in ["DZ", "IC", "RA", "UP", "GR", "GS", "PL"] or obs == "FG":
                __moisture = 3

            if moisture is None or __moisture > moisture:
                moisture = __moisture

        if tt <= 3 and moisture == 5:
            return 4

        if tt <= -15 and moisture is not None:
            return 4

        if tt <= 3 and moisture == 4:
            return 3

        if tt <= 3 and (moisture == 3 or (dp is not None and (tt - dp) < 3)):
            return 1

        if tt <= 3 and moisture is None:
            return 0

        if tt > 3 and moisture is not None:
            return 0

        if tt > 3 and (moisture is None or (dp is not None and (tt - dp) >= 3)):
            return 0

        return 0

    def _assert_temperature_data(self):
        if type(self.data) == MetarData:
            return self.data.temperature is not None

        return self.min_temp is not None

    def _get_visibility_ceiling_coef(self):
        if not self._assert_visibility_data():
            return None

        vis = self.__get_visibility()
        cld_base = self.__get_ceiling()

        if (vis <= 325) or (cld_base is not None and cld_base <= 50):
            return 5

        if (350 <= vis <= 500) or (cld_base is not None and 100 <= cld_base <= 150):
            return 4

        if (550 <= vis <= 750) or (cld_base is not None and 200 <= cld_base <= 250):
            return 2

        return 0

    def _assert_visibility_data(self):
        return self.data.visibility is not None and self.data.clouds is not None

    def __get_ceiling(self):
        cld_base = None
        for cloud in self.data.clouds:
            if cloud.type in ["BKN", "OVC", "VV"] and cloud.base is not None and (cld_base is None or cld_base > cloud.base):
                cld_base = cloud.base
            if cloud.type == "VV" and cloud.base is None:
                cld_base = 0

        return cld_base * 100 if cld_base is not None else None

    def __get_visibility(self):
        vis = self.data.visibility.value
        rvr = None
        if type(self.data) == TafLineData:
            return vis

        for runway in self.data.runway_visibility:
            if runway.visibility is not None and (rvr is None or rvr > runway.visibility.value):
                rvr = runway.visibility.value
            elif len(runway.variable_visibility) > 0 and (rvr is None or rvr > runway.variable_visibility[0].value):
                rvr = runway.variable_visibility[0].value

        if self.units.visibility == "sm":
            vis = self.__sm_to_m(vis)
            rvr = self.__ft_to_m(rvr)

        if rvr is not None and rvr < 1500:
            vis = rvr

        return vis

    def __kmh_to_kt(self, value):
        return value * 0.539957 if value is not None else None

    def __mps_to_kt(self, value):
        return value * 1.94384 if value is not None else None

    def __sm_to_m(self, value):
        return value * 1609.34 if value is not None else None

    def __ft_to_m(self, value):
        return value * 0.3048 if value is not None else None
