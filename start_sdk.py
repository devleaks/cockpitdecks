import os

import sys
# p = os.path.join("/Users", "pierre", "X-Plane 11", "Resources", "plugins", "XPPython3")
p = os.path.join("/Users", "pierre", "Developer", "xppythonstubs")
print(p)
sys.path.append(p)

import logging
from time import sleep

from PI_streamdecks import PythonInterface

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("streamdecks")

pi = None
try:
    pi = PythonInterface()
    pi.XPluginStart()
    pi.XPluginEnable()
except KeyboardInterrupt:
    if pi is not None:
        pi.XPluginDisable()
        pi.XPluginStop()
