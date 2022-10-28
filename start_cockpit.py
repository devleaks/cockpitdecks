import os
import logging
import sys
from time import sleep

from decks import Cockpit
from decks.xplaneudp import XPlaneUDP

# logging.basicConfig(level=logging.DEBUG, filename="streamdecks.log", filemode='a')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cockpitdecks")

ac = "A321"

if len(sys.argv) > 1:
    ac = sys.argv[1]

s = None
try:
    logger.info(f"Cockpitdecks starting for {ac}..")
    s = Cockpit(XPlaneUDP)
    s.load(os.path.join(os.path.dirname(__file__), ac))
except KeyboardInterrupt:
    if s is not None:
        s.terminate_all()
    logger.info(f"Cockpitdecks for {ac} terminated.")
