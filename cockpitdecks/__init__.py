#
# C O C K P I T D E C K S
#
# Decks and web decks to X-Plane Cockpit
#
#
__path__ = __import__("pkgutil").extend_path(__path__, __name__)  # Aum
import re
from datetime import datetime, timezone

#
# ##############################################################
# References used throughout Cockpitdecks
#
from .constant import *  # noqa: F403

#
# ##############################################################
# Version and information
#
__NAME__ = "cockpitdecks"
__COPYRIGHT__ = f"© 2022-{datetime.now().strftime('%Y')} Pierre M <pierre@devleaks.be>"
__DESCRIPTION__ = "Deck and web decks to X-Plane 12.1.4+ (required for Web API)"

__version__ = "15.9.2"

#
# ##########################################################################
# Logging
#
DEPRECATION_LEVEL = 12
DEPRECATION = "DEPRECATION"
SPAM_LEVEL = 15
SPAM = "SPAM"

LOGFILE = "cockpitdecks.log"
FORMAT = "[%(asctime)s] %(levelname)s %(threadName)s %(filename)s:%(funcName)s:%(lineno)d: %(message)s"
# logger name: %(name)s


#
# ##########################################################################
# Utility functions
# (mainly unit conversion functions)
#
def now():
    # Returns now with local timezone.
    return datetime.now().astimezone()


def nowutc() -> datetime:
    # Returns now in UTC timezone
    return datetime.now(timezone.utc)


def to_fl(m, r: int = 10):
    # Convert meters to flight level (1 FL = 100 ft). Round flight level to r if provided, typically rounded to 10, at Patm = 1013 mbar
    fl = m / 30.48
    if r is not None and r > 0:
        fl = r * int(fl / r)
    return fl


def to_m(fl):
    # Convert flight level to meters, at Patm = 1013 mbar
    return round(fl * 30.48)


def parse_options(options: dict | None) -> list:
    if options is None:
        return []
    # https://stackoverflow.com/questions/25250553/can-i-use-a-regex-to-remove-any-whitespace-that-is-not-between-quotes
    # \s+(?=(?:[^\'"]*[\'"][^\'"]*[\'"])*[^\'"]*$)
    rx = r"""(?x)
        \s
        (?=
            (
                " [^\'"]* "
                |
                [^\'"]
            ) *
            $
        )
    """
    old = re.sub(rx, "", options)
    # old = ""  # a, c, d are options, b, e are option values. c option value is boolean True.
    while len(old) != len(options):
        old = options
        options = old.strip().replace(" =", "=").replace("= ", "=").replace(" ,", ",").replace(", ", ",")
    return [a.strip() for a in options.split(",")]


def get_aliases(data: dict, aliases: list | set | tuple):
    # def get_aliases(data: dict, aliases: CONFIG_KW_ALIASES):
    for a in aliases:  # CONFIG_KW_ALIASES(aliases).value
        if v := data.get(a) is not None:
            return v
    return None


# ############################################################
# from .cockpit import Cockpit
