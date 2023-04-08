# List known deck types, their contructor, and their device manager for enumeration
#
# If a model of deck listed below is not available, comment out the lines.
#

# Hardware deck device handlers
from StreamDeck.DeviceManager import DeviceManager as StreamDeckDeviceManager
from Loupedeck  import DeviceManager as LoupedeckDeviceManager
from XTouchMini import DeviceManager as XTouchMiniDeviceManager

# Cockpitdecks representations of decks
from .streamdeck import Streamdeck
from .loupedeck  import Loupedeck
from .xtouchmini import XTouchMini


# Deck type matches attribute type in config.yaml file:
#
# decks:
#   type: loupedeck
#
# This links the deck type, its hardware device manager, and Cockpitdecks representating class.
#
# DECK_TYPES = { "type": [ CockpitdecksClass, DeckDeviceManager ], ... }
#
DECK_TYPES = {
    "streamdeck": [Streamdeck, StreamDeckDeviceManager],
    "loupedeck":  [Loupedeck,  LoupedeckDeviceManager],
    "xtouchmini": [XTouchMini, XTouchMiniDeviceManager]
}
