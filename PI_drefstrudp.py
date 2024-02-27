"""
Little plugin that reads string-type datarefs and multicast them at regular interval.
(I use it to fetch Toliss Airbus FMA text lines. But can be used to multicast any string-typed dataref.)
Return value is JSON {dataref-path: dataref-value} dictionary.
Return value must be smaller than 1472 bytes.
"""

import os
import socket
import time
import json
from XPPython3 import xp

RELEASE = "1.0.0"

MCAST_GRP = "239.255.1.1"  # same as X-Plane 12
MCAST_PORT = 49505  # 49707 for XPlane12
MULTICAST_TTL = 2
FREQUENCY = 5.0  # will run every FREQUENCY seconds

STRING_DATAREFS = [
    "AirbusFBW/FMA1w",
    "AirbusFBW/FMA1g",
    "AirbusFBW/FMA1b",
    "AirbusFBW/FMA2w",
    "AirbusFBW/FMA2b",
    "AirbusFBW/FMA2m",
    "AirbusFBW/FMA3w",
    "AirbusFBW/FMA3b",
    "AirbusFBW/FMA3a",
]


class PythonInterface:
    def __init__(self):
        self.Name = "String datarefs multicast"
        self.Sig = "xppython3.strdrefmcast"
        self.Desc = f"Fetches string-type datarefs at regular intervals and UPD multicast their values (Rel. {RELEASE})"
        self.Info = self.Name + f" (rel. {RELEASE})"
        self.enabled = False
        self.trace = True  # produces extra print/debugging in XPPython3.log for this class
        self.datarefs = {}

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, MULTICAST_TTL)

    def XPluginStart(self):
        # Find the data refs we want to record.
        for dataref in STRING_DATAREFS:
            dref = xp.findDataRef(dataref)
            if dref is not None:
                self.datarefs[dataref] = dref
            else:
                print(self.Info, f"Dataref {dataref} not found")

        if self.trace:
            print(self.Info, "started")

        return self.Name, self.Sig, self.Desc

    def XPluginStop(self):
        if self.trace:
            print(self.Info, "stopped")

    def XPluginEnable(self):
        xp.registerFlightLoopCallback(self.FlightLoopCallback, 1.0, 0)
        self.enabled = True
        if self.trace:
            print(self.Info, "enabled")
        return 1

    def XPluginDisable(self):
        xp.unregisterFlightLoopCallback(self.FlightLoopCallback, 0)
        self.enabled = False
        if self.trace:
            print(self.Info, "disabled")

    def XPluginReceiveMessage(self, inFromWho, inMessage, inParam):
        pass

        # pylint: disable=unused-argument

    def FlightLoopCallback(self, elapsedMe, elapsedSim, counter, refcon):
        if not self.enabled:
            return 0
        drefvalues = {"ts": time.time()} | {d: xp.getDatas(self.datarefs[d]) for d in self.datarefs}
        fma_bytes = bytes(json.dumps(drefvalues), "utf-8")  # no time to think. serialize as json
        # if self.trace:
        #     print(self.Info, fma_bytes.decode("utf-8"))
        if len(fma_bytes) > 1472:
            print(self.Info, f"returned value too large ({len(fma_bytes)}/1472)")
        else:
            self.sock.sendto(fma_bytes, (MCAST_GRP, MCAST_PORT))
        return FREQUENCY


# #####################################################@
# Multicast client
# Adapted from: http://chaos.weblogs.us/archives/164

# import socket

# ANY = "0.0.0.0"

# MCAST_GRP = "239.255.1.1"
# MCAST_PORT = 49505  # (MCAST_PORT is 49707 for XPlane12)

# # Create a UDP socket
# sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)

# # Allow multiple sockets to use the same PORT number
# sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

# # Bind to the port that we know will receive multicast data
# sock.bind((ANY, MCAST_PORT))

# # Tell the kernel that we want to add ourselves to a multicast group
# # The address for the multicast group is the third param
# status = sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, socket.inet_aton(MCAST_GRP) + socket.inet_aton(ANY))

# # setblocking(False) is equiv to settimeout(0.0) which means we poll the socket.
# # But this will raise an error if recv() or send() can't immediately find or send data.
# sock.setblocking(False)

# while 1:
#     try:
#         data, addr = sock.recvfrom(1024)
#     except socket.error as e:
#         pass
#     else:
#         print("From: ", addr)
#         print("Data: ", data)
