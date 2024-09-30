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

# Test
try:
    from .customdeck import CustomDeck
except ImportError:
    pass
