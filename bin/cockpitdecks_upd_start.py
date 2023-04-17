import os
import logging
import sys

COCKPIT_DECK_BASEDIR = os.path.join(os.path.dirname(__file__), '..')
sys.path.append(COCKPIT_DECK_BASEDIR)

from cockpitdecks import Cockpit, DEFAULT_AIRCRAFT
from cockpitdecks import __NAME__, __version__, __COPYRIGHT__
from cockpitdecks.xplaneudp import XPlaneUDP

# logging.basicConfig(level=logging.DEBUG, filename="streamdecks.log", filemode='a')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ac = sys.argv[1] if len(sys.argv) > 1 else os.path.join(COCKPIT_DECK_BASEDIR, DEFAULT_AIRCRAFT)
s = None

try:
    logger.info(f"{__NAME__.title()} {__version__} {__COPYRIGHT__}")
    logger.info(f"Starting for {os.path.basename(ac)}..")
    logger.info(f"..searching for decks and initializing them (this may take a few seconds)..")
    s = Cockpit(XPlaneUDP)
    s.start_aircraft(ac)
    logger.info(f"..{os.path.basename(ac)} terminated.")
except KeyboardInterrupt:
    if s is not None:
        s.terminate_all()
    logger.info(f"..{os.path.basename(ac)} terminated.")
