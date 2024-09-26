# List known deck drivers, their contructor, and their device manager for enumeration
#
# If a model of deck listed below is not available, comment out the lines.
#
import sys
import os

try:
    from .streamdeck import Streamdeck
except ImportError:
    pass

try:
    from .loupedeck import Loupedeck
except ImportError:
    pass

try:
    from .xtouchmini import XTouchMini
except ImportError:
    pass

try:
    from .virtualdeck import VirtualDeck
except ImportError:
    pass
