from datetime import datetime

__NAME__ = "cockpitdecks"
__DESCRIPTION__ = "Elgato Stream Decks and Loupedeck LoupedeckLive to X-Plane Cockpit"
__LICENSE__ = "MIT"
__LICENSEURL__ = "https://mit-license.org"
__COPYRIGHT__ = f"© 2022-{datetime.now().strftime('%Y')} Pierre M <pierre@devleaks.be>"
__version__ = "3.0.0"
__version_info__ = tuple(map(int, __version__.split(".")))
__version_name__ = "development"
__author__ = "Pierre M <pierre@devleaks.be>"
__authorurl__ = "https://github.com/devleaks/streamdecks"

from .cockpit import Cockpit
