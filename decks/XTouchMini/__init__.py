from datetime import datetime
__NAME__ = "python-xtouch-mini"
__DESCRIPTION__ = "XTouch Mini python interface."
__LICENSE__ = "MIT"
__LICENSEURL__ = "https://mit-license.org"
__COPYRIGHT__ = f"© 2022-{datetime.now().strftime('%Y')} Pierre M <pierre@devleaks.be>"
__version__ = "1.0.0"
__version_info__ = tuple(map(int, __version__.split(".")))
__author__ = "Pierre M <pierre@devleaks.be>"
__authorurl__ = "https://devleaks.be/"


from .DeviceManager import DeviceManager