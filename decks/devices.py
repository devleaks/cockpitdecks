# List known deck types, their contructor, and their device manager for enumeration
#
# If a model of deck listed below is not available, comment out the lines.
#
import logging
logger = logging.getLogger("Device")
logger.setLevel(logging.INFO)

DECK_TYPES = {}

try:
    from StreamDeck.DeviceManager import DeviceManager as StreamDeckDeviceManager
    from .streamdeck import Streamdeck
    DECK_TYPES["streamdeck"] = [Streamdeck, StreamDeckDeviceManager]
    logger.info(f"Streamdeck drivers installed")
except ImportError:
    pass


try:
    from Loupedeck  import DeviceManager as LoupedeckDeviceManager
    from .loupedeck  import Loupedeck
    DECK_TYPES["loupedeck"] = [Loupedeck,  LoupedeckDeviceManager]
    logger.info(f"Loupedeck drivers installed")
except ImportError:
    pass


try:
    from XTouchMini import DeviceManager as XTouchMiniDeviceManager
    from .xtouchmini import XTouchMini
    DECK_TYPES["xtouchmini"] = [XTouchMini, XTouchMiniDeviceManager]
    logger.info(f"Berhinger drivers installed")
except ImportError:
    pass
