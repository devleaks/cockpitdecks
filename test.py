import os
import logging
import sys
sys.path.append('/Users/pierre/Developer/xppythonstubs')

from streamdecks import Streamdecks, XPlaneUDP

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("streamdecks")

s = None
try:
    s = Streamdecks(None, XPlaneUDP)
    s.load(os.path.join(os.path.dirname(__file__), "A321"))
except KeyboardInterrupt:
    if s is not None:
        s.terminate_all()
