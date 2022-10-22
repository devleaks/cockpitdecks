import os
import logging
from time import sleep

from decks import Cockpit
from decks.xplaneudp import XPlaneUDP

# logging.basicConfig(level=logging.DEBUG, filename="streamdecks.log", filemode='a')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cockpitdecks")

s = None
try:
    s = Cockpit(XPlaneUDP)
    s.load(os.path.join(os.path.dirname(__file__), "A321"))
except KeyboardInterrupt:
    if s is not None:
        s.terminate_all()
