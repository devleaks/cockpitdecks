import os
import logging
from time import sleep
import socket
import struct
import binascii
import platform

from decks.xplane import Dataref, XPlane
from decks.xplaneudp import XPlaneUDP

 # logging.basicConfig(level=logging.DEBUG, filename="streamdecks.log", filemode='a')
logging.basicConfig(level=logging.INFO)

s = XPlaneUDP(None)
refs = dict([(p, s.get_dataref(p)) for p in ["AirbusFBW/ILSonCapt", "AirbusFBW/FD1Engage"]])
print(refs)
s.add_datarefs_to_monitor(refs)

s.running = True
s.loop()
