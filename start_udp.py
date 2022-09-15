import os
import logging
from time import sleep
import sys
sys.path.append('/Users/pierre/Developer/xppythonstubs')

from decks import Decks, XPlaneUDP

# logging.basicConfig(level=logging.DEBUG, filename="streamdecks.log", filemode='a')
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("decks_udp")

s = None
try:
    s = Decks(None, XPlaneUDP)
    s.load(os.path.join(os.path.dirname(__file__), "A321"))
except KeyboardInterrupt:
    if s is not None:
        s.terminate_all()
