import logging

from streamdeck import Streamdecks

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("streamdecks")

s = Streamdecks()
s.load("A321")

