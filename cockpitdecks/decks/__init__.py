# List known deck drivers, their contructor, and their device manager for enumeration
#
# If a model of deck listed below is not available, comment out the lines.
#
DECK_DRIVERS = {}

try:
    from StreamDeck.DeviceManager import DeviceManager as StreamDeckDeviceManager
    from .streamdeck import Streamdeck

    DECK_DRIVERS[Streamdeck.DECK_NAME] = [Streamdeck, StreamDeckDeviceManager]
except ImportError:
    pass


try:
    from Loupedeck import DeviceManager as LoupedeckDeviceManager
    from .loupedeck import Loupedeck

    DECK_DRIVERS[Loupedeck.DECK_NAME] = [Loupedeck, LoupedeckDeviceManager]
except ImportError:
    pass


try:
    from XTouchMini import DeviceManager as XTouchMiniDeviceManager
    from .xtouchmini import XTouchMini

    DECK_DRIVERS[XTouchMini.DECK_NAME] = [XTouchMini, XTouchMiniDeviceManager]
except ImportError:
    pass

# removed try/except blocks for development
#
# from StreamDeck.DeviceManager import DeviceManager as StreamDeckDeviceManager
# from .streamdeck import Streamdeck

# DECK_DRIVERS["streamdeck"] = [Streamdeck, StreamDeckDeviceManager]


# from Loupedeck import DeviceManager as LoupedeckDeviceManager
# from .loupedeck import Loupedeck

# DECK_DRIVERS["loupedeck"] = [Loupedeck, LoupedeckDeviceManager]


# from XTouchMini import DeviceManager as XTouchMiniDeviceManager
# from .xtouchmini import XTouchMini

# DECK_DRIVERS["xtouchmini"] = [XTouchMini, XTouchMiniDeviceManager]
