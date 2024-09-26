#
# C O C K P I T D E C K S
#
# Decks and web decks to X-Plane Cockpit
#
#
__path__ = __import__("pkgutil").extend_path(__path__, __name__)  # Aum
import re
from datetime import datetime

__NAME__ = "cockpitdecks"
__COPYRIGHT__ = f"© 2022-{datetime.now().strftime('%Y')} Pierre M <pierre@devleaks.be>"

__version__ = "11.25.0"

#
#
# ##########################################################################
# Logging
#
SPAM_LEVEL = 15
SPAM = "SPAM"
LOGFILE = "cockpitdecks.log"
FORMAT = "[%(asctime)s] %(levelname)s %(threadName)s %(filename)s:%(funcName)s:%(lineno)d: %(message)s"
#
# ##############################################################
# References used throughout Cockpitdecks
#
from .constant import *


#
#
# ##########################################################################
# Utility functions
# (mainly unit conversion functions)
#
def now():
    return datetime.now().astimezone()


def to_fl(m, r: int = 10):
    # Convert meters to flight level (1 FL = 100 ft). Round flight level to r if provided, typically rounded to 10, at Patm = 1013 mbar
    fl = m / 30.48
    if r is not None and r > 0:
        fl = r * int(fl / r)
    return fl


def to_m(fl):
    # Convert flight level to meters, at Patm = 1013 mbar
    return round(fl * 30.48)


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


# ############################################################
from .cockpit import Cockpit, CockpitBase
