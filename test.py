import os
import logging
import sys
sys.path.append('/Users/pierre/Developer/xppythonstubs')

from streamdeck import Streamdecks

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("streamdecks")

s = Streamdecks()

s.load(os.path.join(os.path.dirname(__file__), "A321"))

