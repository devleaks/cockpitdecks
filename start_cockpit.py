import os
import logging
import sys
from time import sleep

from decks import Cockpit
from decks import __NAME__, __version__, __COPYRIGHT__
from decks.xplaneudp import XPlaneUDP

# logging.basicConfig(level=logging.DEBUG, filename="streamdecks.log", filemode='a')
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__NAME__.title())

ac = sys.argv[1] if len(sys.argv) > 1 else "A321"
s = None

try:
    logger.info(f"{__version__} {__COPYRIGHT__}")
    logger.info(f"Starting for {ac}..")
    logger.info(f"..searching for decks and initializing them (this can take a few seconds)..")
    s = Cockpit(XPlaneUDP)
    s.load(os.path.join(os.path.dirname(__file__), ac))
except KeyboardInterrupt:
    if s is not None:
        s.terminate_all()
    logger.info(f"..{ac} terminated.")
