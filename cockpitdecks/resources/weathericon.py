# ###########################
# Representation of a Metar in short textual summary form
#
import logging
import random
import re
from functools import reduce
from datetime import datetime, timezone

from suntime import Sun
from zoneinfo import ZoneInfo
from timezonefinder import TimezoneFinder

from cockpitdecks.resources.iconfonts import (
    WEATHER_ICONS,
    DEFAULT_WEATHER_ICON,
)

logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)
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

HARDCODED_DEFAULT = "wi_day_sunny"
HARDCODED_ICON = "\uf00d"


#
# Weather icon
# (Artistic, no standard)
#
class WeatherIcon:

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

    def __init__(self):
        self.sun = None

    def is_metar_day(self, metar, station, sunrise: int = 6, sunset: int = 18) -> bool:
        time = metar.raw[7:12]
        logger.debug(f"zulu {time}")
        if time[-1] != "Z":
            logger.warning(f"no zulu? {time}")
            return True
        tz = self.get_timezone(station)
        logger.debug(f"timezone {'UTC' if tz == timezone.utc else tz.key}")
        utc = datetime.now(timezone.utc)
        utc = utc.replace(hour=int(time[0:2]), minute=int(time[2:4]))
        local = utc.astimezone(tz=tz)
        sun = self.get_sun(local)
        day = local.hour > sun[0] and local.hour < sun[1]
        logger.info(
            f"metar: {time}, local: {local.strftime('%H%M')} {tz} ({local.utcoffset()}), {'day' if day else 'night'} (sunrise {sun[0]}, sunset {sun[1]})"
        )
        return day

    def is_day(self, hours: int, sunrise: int = 5, sunset: int = 19) -> bool:
        # Uses the simulator local time
        if self.sun is not None:
            sr = self.sun.get_sunrise_time()
            ss = self.sun.get_sunset_time()
        else:
            sr = sunrise
            ss = sunset
        return hours >= sr and hours <= ss

    def get_timezone(self, station):
        # pip install timezonefinder
        # from zoneinfo import ZoneInfo
        # from timezonefinder import TimezoneFinder
        #
        tf = TimezoneFinder()
        tzname = tf.timezone_at(lng=station.longitude, lat=station.latitude)
        if tzname is not None:
            logger.debug(f"timezone is {tzname}")
            return ZoneInfo(tzname)
        logger.debug(f"no timezone, using utc")
        return timezone.utc

    def get_sunrise_time(self, station):
        # pip install timezonefinder
        # from zoneinfo import ZoneInfo
        # from timezonefinder import TimezoneFinder
        #
        tf = TimezoneFinder()
        tzname = tf.timezone_at(lng=v.longitude, lat=station.latitude)
        if tzname is not None:
            return ZoneInfo(tzname)
        return timezone.utc

    def get_sun(self, moment: datetime | None = None):
        # Returns sunrise and sunset rounded hours (24h)
        if moment is None:
            today_sr = self.sun.get_sunrise_time()
            today_ss = self.sun.get_sunset_time()
            return (today_sr.hour, today_ss.hour)
        today_sr = self.sun.get_sunrise_time(moment)
        today_ss = self.sun.get_sunset_time(moment)
        return (today_sr.hour, today_ss.hour)

    def day_night(self, icon, day: bool = True):
        # Selects day or night variant of icon
        logger.debug(f"search {icon}, {day}")

        # Special case cavok
        if icon == KW_CAVOK:
            logger.debug(f"{KW_CAVOK}, {day}")
            return CAVOK_DAY if day else CAVOK_NIGHT

        # Do we have a variant?
        icon_np = icon.replace("wi_", "")
        try_icon = None
        dft_name = None
        for prefix in [
            WI_PREFIX,
            WI_PREFIX + DAY,
            WI_PREFIX + NIGHT,
            WI_PREFIX + NIGHT_ALT,
        ]:
            if try_icon is None:
                dft_name = prefix + icon_np
                logger.debug(f"trying {dft_name}..")
                try_icon = WEATHER_ICONS.get(dft_name)
        if try_icon is None:
            logger.debug(f"no such icon or variant {icon}")
            return DEFAULT_WEATHER_ICON
        else:
            logger.debug(f"exists {dft_name}")

        # From now on, we are sure we can find an icon
        # day
        if not day:
            icon_name = WI_PREFIX + NIGHT + icon
            try_icon = WEATHER_ICONS.get(icon_name)
            if try_icon is not None:
                logger.debug(f"exists night {icon_name}")
                return icon_name

            icon_name = WI_PREFIX + NIGHT_ALT + icon
            try_icon = WEATHER_ICONS.get(icon_name)
            if try_icon is not None:
                logger.debug(f"exists night-alt {try_icon}")
                return icon_name

        icon_name = WI_PREFIX + DAY + icon
        try_icon = WEATHER_ICONS.get(icon_name)
        if try_icon is not None:
            logger.debug(f"exists day {icon_name}")
            return icon_name

        logger.debug(f"found {dft_name}")
        return dft_name

    def select_weather_icon(self, metar: str | None, station, at_random: bool = False):
        # Needs improvement
        # Stolen from https://github.com/flybywiresim/efb
        if at_random:
            return random.choice(list(WEATHER_ICONS.keys()))

        if metar is None:
            logger.warning("no metar")
            return DEFAULT_WEATHER_ICON

        if station is not None:
            self.sun = Sun(station.latitude, station.longitude)
        else:
            logger.warning("no station, cannot determine lat/lon or sun time")

        rawtext = metar.raw[13:]  # strip ICAO DDHHMMZ, should do a much clever substring removal based on regex
        logger.debug(f"METAR {rawtext}")
        # Precipitations
        precip = re.match("RA|SN|DZ|SG|PE|GR|GS", rawtext)
        if precip is None:
            precip = []
        logger.debug(f"PRECIP {precip}")
        # Wind
        wind = metar.data.wind_speed.value if hasattr(metar.data, "wind_speed") else 0
        logger.debug(f"WIND {wind}")

        findIcon = []
        for item in WeatherIcon.DB:
            t1 = reduce(
                lambda x, y: x + y,
                [rawtext.find(desc) for desc in item[KW_TAGS]],
                0,
            ) == len(item[KW_TAGS])
            t_precip = (len(item[KW_PRECIP]) == 0) or rawtext.find(item[KW_PRECIP])
            t_clouds = (
                (len(item[KW_CLOUD]) == 0)
                or (len(item[KW_CLOUD]) == 1 and item[KW_CLOUD][0] == "")
                or (
                    reduce(
                        lambda x, y: x + y,
                        [rawtext.find(cld) for cld in item[KW_CLOUD]],
                        0,
                    )
                    > 0
                )
            )
            t_wind = wind > item[KW_WIND][0] and wind < item[KW_WIND][1]
            t_vis = (len(item[KW_VIS]) == 0) or (
                reduce(
                    lambda x, y: x + y,
                    [rawtext.find(vis) for vis in item[KW_VIS]],
                    0,
                )
                > 0
            )
            ok = t1 and t_precip and t_clouds and t_wind and t_vis
            if ok:
                findIcon.append(item)
            logger.debug(f"findIcon: {item[KW_NAME]}, list={t1}, precip={t_precip}, clouds={t_clouds}, wind={t_wind}, vis={t_vis} {('<'*10) if ok else ''}")
        logger.debug(f"STEP 1 {findIcon}")

        # findIcon = list(filter(lambda item: reduce(lambda x, y: x + y, [rawtext.find(desc) for desc in item[KW_TAGS]], 0) == len(item[KW_TAGS])
        #                            and ((len(item[KW_PRECIP]) == 0) or rawtext.find(item[KW_PRECIP]))
        #                            and ((len(item[KW_CLOUD]) == 0) or (len(item[KW_CLOUD]) == 1 and item[KW_CLOUD][0] == "") or (reduce(lambda x, y: x + y, [rawtext.find(cld) for cld in item[KW_CLOUD]], 0) > 0))
        #                            and (wind > item[KW_WIND][0] and wind < item[KW_WIND][1])
        #                            and ((len(item[KW_VIS]) == 0) or (reduce(lambda x, y: x + y, [rawtext.find(vis) for vis in item[KW_VIS]], 0) > 0)),
        #                  WeatherIcon.DB))
        # logger.debug(f"STEP 1 {findIcon}")

        icon = DEFAULT_WEATHER_ICON
        l = len(findIcon)
        if l == 1:
            icon = findIcon[0]["iconName"]
        else:
            if l > 1:
                findIcon2 = []
                if len(precip) > 0:
                    findIcon2 = list(
                        filter(
                            lambda x: re("RA|SN|DZ|SG|PE|GR|GS").match(x["precip"]),
                            findIcon,
                        )
                    )
                else:
                    findIcon2 = list(filter(lambda x: x["day"] == day, findIcon))
                logger.debug(f"STEP 2 {findIcon2}")
                if len(findIcon2) > 0:
                    icon = findIcon2[0]["iconName"]

        logger.debug(f"weather icon {icon}")
        day = self.is_metar_day(metar=metar, station=station)
        daynight_icon = self.day_night(icon, day)
        if daynight_icon is None:
            logger.warning(f"no icon, using default {DEFAULT_WEATHER_ICON}")
            daynight_icon = DEFAULT_WEATHER_ICON
        daynight_icon = daynight_icon.replace("-", "_")  # ! Important
        logger.debug(f"day/night version: {day}: {daynight_icon}")
        return daynight_icon

    def get_icon(self, name) -> str:
        icon_char = WEATHER_ICONS.get(name)
        if icon_char is None:
            logger.warning(f"weather icon '{name}' not found, using default ({DEFAULT_WEATHER_ICON})")
            name = DEFAULT_WEATHER_ICON
            icon_char = WEATHER_ICONS.get(DEFAULT_WEATHER_ICON)
            if icon_char is None:
                logger.warning(f"default weather icon {DEFAULT_WEATHER_ICON} not found, using hardcoded default ({HARDCODED_DEFAULT})")
                icon_char = HARDCODED_ICON
        return icon_char
