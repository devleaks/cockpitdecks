import os
import logging
from time import sleep
import socket
import struct
import binascii
import platform

class XPlaneIpNotFound(Exception):
    args = "Could not find any running XPlane instance in network."

class XPlaneTimeout(Exception):
    args = "XPlane timeout."

class XPlaneVersionNotSupported(Exception):
    args = "XPlane version not supported."

UDP_PORT = 40007

logger = logging.getLogger("XPlaneUDP")
logger.setLevel(logging.DEBUG)


class XPlaneUDP:
    '''
    Get data from XPlane via network.
    Use a class to implement RAI Pattern for the UDP socket.
    '''

    #constants
    MCAST_GRP = "239.255.1.1"
    MCAST_PORT = 49707 # (MCAST_PORT was 49000 for XPlane10)
    BEACON_TIMEOUT = 3.0  # seconds

    def __init__(self):
        self.defaultFreq = 1

        # Open a UDP Socket to receive on Port 49000
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(self.BEACON_TIMEOUT)
        # values from xplane
        self.BeaconData = {}
        self.UDP_PORT = UDP_PORT

        # list of requested datarefs with index number
        self.datarefidx = 0
        self.datarefs = {} # key = idx, value = dataref

        self.finished = None
        self.init()

    def init(self):
        try:
            beacon = self.FindIp()
            logger.info(beacon)
        except XPlaneVersionNotSupported:
            self.BeaconData = {}
            logger.error("init: XPlane Version not supported.")
        except XPlaneIpNotFound:
            self.BeaconData = {}
            logger.error("init: XPlane IP not found. Probably there is no XPlane running in your local network.")

    def __del__(self):
        for i in range(len(self.datarefs)):
            self.AddDataRef(next(iter(self.datarefs.values())), freq=0)
        self.socket.close()

    def get_dataref(self, path):
        if path in self.all_datarefs.keys():
            return self.all_datarefs[path]
        return self.register(Dataref(path))

    def WriteDataRef(self, dataref, value, vtype='float'):
        '''
        Write Dataref to XPlane
        DREF0+(4byte byte value)+dref_path+0+spaces to complete the whole message to 509 bytes
        DREF0+(4byte byte value of 1)+ sim/cockpit/switches/anti_ice_surf_heat_left+0+spaces to complete to 509 bytes
        '''
        cmd = b"DREF\x00"
        dataref    =dataref+'\x00'
        string = dataref.ljust(500).encode()
        message = "".encode()
        if vtype == "float":
            message = struct.pack("<5sf500s", cmd,value,string)
        elif vtype == "int":
            message = struct.pack("<5si500s", cmd, value, string)
        elif vtype == "bool":
            message = struct.pack("<5sI500s", cmd, int(value), string)

        assert(len(message)==509)
        logger.debug(f"WriteDataRef: ({self.BeaconData['IP']}, {self.UDP_PORT}): {dataref}={value}")
        self.socket.sendto(message, (self.BeaconData["IP"], self.UDP_PORT))

    def ExecuteCommand(self, command: str):
        if "IP" in self.BeaconData:
            if command.lower() in ["none", "placeholder"]:
                logger.debug(f"ExecuteCommand: not executed command '{command}' (place holder)")
                return
            message = 'CMND0' + command
            self.socket.sendto(message.encode(), (self.BeaconData["IP"], self.BeaconData["Port"]))
            logger.debug(f"ExecuteCommand: executed {command}")
        else:
            logger.warning(f"ExecuteCommand: no IP connection ({command})")

    def FindIp(self):
        '''
        Find the IP of XPlane Host in Network.
        It takes the first one it can find.
        '''
        self.BeaconData = {}

        # open socket for multicast group.
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if platform.system() == "Windows":
            sock.bind(('', self.MCAST_PORT))
        else:
            sock.bind((self.MCAST_GRP, self.MCAST_PORT))
        mreq = struct.pack("=4sl", socket.inet_aton(self.MCAST_GRP), socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        sock.settimeout(3.0)

        # receive data
        try:
            packet, sender = sock.recvfrom(1472)
            logger.debug(f"FindIp: XPlane Beacon: {packet.hex()}")

            # decode data
            # * Header
            header = packet[0:5]
            if header != b"BECN\x00":
                logger.warning(f"FindIp: Unknown packet from {sender[0]}, {str(len(packet))} bytes:")
                logger.warning(packet)
                logger.warning(binascii.hexlify(packet))

            else:
                # * Data
                data = packet[5:21]
                # struct becn_struct
                # {
                #   uchar beacon_major_version;     // 1 at the time of X-Plane 10.40
                #   uchar beacon_minor_version;     // 1 at the time of X-Plane 10.40
                #   xint application_host_id;       // 1 for X-Plane, 2 for PlaneMaker
                #   xint version_number;            // 104014 for X-Plane 10.40b14
                #   uint role;                      // 1 for master, 2 for extern visual, 3 for IOS
                #   ushort port;                    // port number X-Plane is listening on
                #   xchr    computer_name[strDIM];  // the hostname of the computer
                # };
                beacon_major_version = 0
                beacon_minor_version = 0
                application_host_id = 0
                xplane_version_number = 0
                role = 0
                port = 0
                (
                    beacon_major_version,    # 1 at the time of X-Plane 10.40
                    beacon_minor_version,    # 1 at the time of X-Plane 10.40
                    application_host_id,     # 1 for X-Plane, 2 for PlaneMaker
                    xplane_version_number,   # 104014 for X-Plane 10.40b14
                    role,                    # 1 for master, 2 for extern visual, 3 for IOS
                    port,                    # port number X-Plane is listening on
                    ) = struct.unpack("<BBiiIH", data)
                hostname = packet[21:-1] # the hostname of the computer
                hostname = hostname[0:hostname.find(0)]
                if beacon_major_version == 1 \
                    and beacon_minor_version <= 2 \
                    and application_host_id == 1:
                    self.BeaconData["IP"] = sender[0]
                    self.BeaconData["Port"] = port
                    self.BeaconData["hostname"] = hostname.decode()
                    self.BeaconData["XPlaneVersion"] = xplane_version_number
                    self.BeaconData["role"] = role
                    logger.info(f"FindIp: XPlane Beacon Version: {beacon_major_version}.{beacon_minor_version}.{application_host_id}")
                else:
                    logger.warning(f"FindIp: XPlane Beacon Version not supported: {beacon_major_version}.{beacon_minor_version}.{application_host_id}")
                    raise XPlaneVersionNotSupported()

        except socket.timeout:
            logger.error("FindIp: XPlane IP not found.")
            raise XPlaneIpNotFound()
        finally:
            sock.close()

        return self.BeaconData

 # logging.basicConfig(level=logging.DEBUG, filename="streamdecks.log", filemode='a')
logging.basicConfig(level=logging.INFO)

s = XPlaneUDP()
s.ExecuteCommand("leecbaker/datareftool/new_search_window")
