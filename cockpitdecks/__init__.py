from datetime import datetime

__NAME__         = "cockpitdecks"
__DESCRIPTION__  = "Elgato Streamdeck, Loupedeck LoupedeckLive, and Berhinger X-Touch Mini to X-Plane Cockpit"
__LICENSE__      = "MIT"
__LICENSEURL__   = "https://mit-license.org"
__COPYRIGHT__    = f"© 2022-{datetime.now().strftime('%Y')} Pierre M <pierre@devleaks.be>"
__version__      = "7.1.1"
__version_info__ = tuple(map(int, __version__.split(".")))
__version_name__ = "development"
__authorurl__    = "https://github.com/devleaks/cockpitdecks"

from .cockpit import Cockpit
