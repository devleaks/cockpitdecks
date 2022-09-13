import socket
import struct
import binascii
import platform
import threading
import time


class XPlaneIpNotFound(Exception):
    args = "Could not find any running XPlane instance in network."

class XPlaneTimeout(Exception):
    args = "XPlane timeout."

class XPlaneVersionNotSupported(Exception):
    args = "XPlane version not supported."


class XPUDP:

    #constants
    MCAST_GRP = "239.255.1.1"
    MCAST_PORT = 49707 # (MCAST_PORT was 49000 for XPlane10)
    BEACON_TIMEOUT = 3.0  # seconds

    def __init__(self):
        # Open a UDP Socket to receive on Port 49000
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(self.BEACON_TIMEOUT)
        # values from xplane
        self.BeaconData = {}
        self.UDP_PORT = None

        self.init()

    def init(self):
        try:
            beacon = self.FindIp()
            print(beacon)
        except XPlaneVersionNotSupported:
            self.BeaconData = {}
            print("init: XPlane Version not supported.")
        except XPlaneIpNotFound:
            self.BeaconData = {}
            print("init: XPlane IP not found. Probably there is no XPlane running in your local network.")

    def __del__(self):
        self.socket.close()

    def ExecuteCommand(self, command: str):
        if "IP" in self.BeaconData:
            message = 'CMND0' + command
            self.socket.sendto(message.encode(), (self.BeaconData["IP"], self.BeaconData["Port"]))
            print(f"ExecuteCommand: executed {command}")
        else:
            print(f"ExecuteCommand: no IP connection")

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
            print(f"FindIp: XPlane Beacon: {packet.hex()}")

            # decode data
            # * Header
            header = packet[0:5]
            if header != b"BECN\x00":
                print(f"FindIp: Unknown packet from {sender[0]}, {str(len(packet))} bytes:")
                print(packet)
                print(binascii.hexlify(packet))

            else:
                # * Data
                data = packet[5:21]
                # struct becn_struct
                # {
                # 	uchar beacon_major_version;		// 1 at the time of X-Plane 10.40
                # 	uchar beacon_minor_version;		// 1 at the time of X-Plane 10.40
                # 	xint application_host_id;		// 1 for X-Plane, 2 for PlaneMaker
                # 	xint version_number;			// 104014 for X-Plane 10.40b14
                # 	uint role;						// 1 for master, 2 for extern visual, 3 for IOS
                # 	ushort port;					// port number X-Plane is listening on
                # 	xchr	computer_name[strDIM];	// the hostname of the computer
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
                    print(f"FindIp: XPlane Beacon Version: {beacon_major_version}.{beacon_minor_version}.{application_host_id}")
                else:
                    print(f"FindIp: XPlane Beacon Version not supported: {beacon_major_version}.{beacon_minor_version}.{application_host_id}")
                    raise XPlaneVersionNotSupported()

        except socket.timeout:
            print("FindIp: XPlane IP not found.")
            raise XPlaneIpNotFound()
        finally:
            sock.close()

        return self.BeaconData

    # ################################
    # X-Plane Interface
    #
    def commandOnce(self, command: str):
        self.ExecuteCommand(command)

    def commandBegin(self, command: str):
        self.ExecuteCommand(command+"/begin")

    def commandEnd(self, command: str):
        self.ExecuteCommand(command+"/end")


if __name__ == '__main__':
    xp = XPUDP()

    if "IP" in xp.BeaconData:
        xp.commandBegin("AirbusFBW/FireTestAPU")
        time.sleep(5)
        xp.commandEnd("AirbusFBW/FireTestAPU")
    else:
        print("could not connect to X-Plane")
