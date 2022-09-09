from datetime import datetime

__NAME__ = "streamdecks"
__DESCRIPTION__ = "Elgato Stream Decks to X-Plane Connector"
__LICENSE__ = "MIT"
__LICENSEURL__ = "https://mit-license.org"
__COPYRIGHT__ = f"© 2022-{datetime.now().strftime('%Y')} Pierre M <pierre@devleaks.be>"
__version__ = "0.4.0"
__version_info__ = tuple(map(int, __version__.split(".")))
__version_name__ = "development"
__author__ = "Pierre M <pierre@devleaks.be>"
__authorurl__ = "https://github.com/devleaks/streamdecks"

from .streamdecks import Streamdecks
from .xplane import XPlane
from .xplaneudp import XPlaneUDP
from .xplanesdk import XPlaneSDK
