# List known deck types, their contructor, and their device manager for enumeration
#
# If a model of deck listed below is not available, comment out the lines.
#
DECK_TYPES = {}


try:
    from StreamDeck.DeviceManager import DeviceManager as StreamDeckDeviceManager
    from .streamdeck import Streamdeck

    DECK_TYPES["streamdeck"] = [Streamdeck, StreamDeckDeviceManager]
except ImportError:
    pass


try:
    from Loupedeck import DeviceManager as LoupedeckDeviceManager
    from .loupedeck import Loupedeck

    DECK_TYPES["loupedeck"] = [Loupedeck, LoupedeckDeviceManager]
except ImportError:
    pass


try:
    from XTouchMini import DeviceManager as XTouchMiniDeviceManager
    from .xtouchmini import XTouchMini

    DECK_TYPES["xtouchmini"] = [XTouchMini, XTouchMiniDeviceManager]
except ImportError:
    pass

# removed try/except blocks for development
#
# from StreamDeck.DeviceManager import DeviceManager as StreamDeckDeviceManager
# from .streamdeck import Streamdeck
# DECK_TYPES["streamdeck"] = [Streamdeck, StreamDeckDeviceManager]


# from Loupedeck  import DeviceManager as LoupedeckDeviceManager
# from .loupedeck  import Loupedeck
# DECK_TYPES["loupedeck"] = [Loupedeck,  LoupedeckDeviceManager]


# from XTouchMini import DeviceManager as XTouchMiniDeviceManager
# from .xtouchmini import XTouchMini
# DECK_TYPES["xtouchmini"] = [XTouchMini, XTouchMiniDeviceManager]
