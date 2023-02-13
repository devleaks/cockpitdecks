# List known deck types, their contructor, and their device manager for emuneration
#
from StreamDeck.DeviceManager import DeviceManager as StreamDeckDeviceManager

from .streamdeck import Streamdeck
from .loupedeck import Loupedeck
from .xtouchmini import XTouchMini

from .Loupedeck import DeviceManager as LoupedeckDeviceManager
from .XTouchMini import DeviceManager as XTouchMiniDeviceManager

DECK_TYPES = {
    # "streamdeck": [Streamdeck, StreamDeckDeviceManager],
    "loupedeck": [Loupedeck, LoupedeckDeviceManager],
    # "xtouchmini": [XTouchMini, XTouchMiniDeviceManager]
}
