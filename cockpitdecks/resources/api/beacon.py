import logging
import threading
import socket
import ipaddress
import struct
import binascii
import platform
from datetime import datetime

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

XP_MIN_VERSION = 121100
XP_MAX_VERSION = 121399


# XPlaneBeacon-specific error classes
class XPlaneIpNotFound(Exception):
    args = "Could not find any running XPlane instance in network"


class XPlaneVersionNotSupported(Exception):
    args = "XPlane version not supported"


def my_ip() -> str | set:
    x = set([address[4][0] for address in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)])
    return list(x)[0] if len(x) == 1 else x


def get_ip(s) -> str:
    c = s[0]
    if c in "0123456789":
        return ipaddress.ip_address(s)
    else:
        return ipaddress.ip_address(socket.gethostbyname(s))


class XPlaneBeacon:
    """
    Get data from XPlane via network.
    Use a class to implement RAI Pattern for the UDP socket.
    """

    # constants
    MCAST_GRP = "239.255.1.1"
    MCAST_PORT = 49707  # (MCAST_PORT was 49000 for XPlane10)
    BEACON_TIMEOUT = 3.0  # seconds
    MAX_WARNING = 3
    RECONNECT_TIMEOUT = 10  # seconds, times between attempts to reconnect to X-Plane when not connected
    WARN_FREQ = 10  # seconds

    def __init__(self):
        # Open a UDP Socket to receive on Port 49000
        self.socket = None
        hostname = socket.gethostname()
        self.local_ip = socket.gethostbyname(hostname)
        self.beacon_data = {}
        self.should_not_connect: threading.Event | None = None
        self.connect_thread: threading.Thread | None = None
        self._already_warned = 0
        self.min_version = XP_MIN_VERSION
        self.max_version = XP_MAX_VERSION

    @property
    def connected(self):
        res = "IP" in self.beacon_data.keys()
        if not res and not self._already_warned > self.MAX_WARNING:
            if self._already_warned == self.MAX_WARNING:
                logger.warning("no connection (last warning)")
            else:
                logger.warning("no connection")
            self._already_warned = self._already_warned + 1
        return res

    def FindIp(self):
        """
        Find the IP of XPlane Host in Network.
        It takes the first one it can find.
        """
        if self.socket is not None:
            self.socket.close()
            self.socket = None
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.beacon_data = {}

        # open socket for multicast group.
        # this socker is for getting the beacon, it can be closed when beacon is found.
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)  # SO_REUSEPORT?
        if platform.system() == "Windows":
            sock.bind(("", self.MCAST_PORT))
        else:
            sock.bind((self.MCAST_GRP, self.MCAST_PORT))
        mreq = struct.pack("=4sl", socket.inet_aton(self.MCAST_GRP), socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        sock.settimeout(XPlaneBeacon.BEACON_TIMEOUT)

        # receive data
        try:
            packet, sender = sock.recvfrom(1472)
            logger.debug(f"XPlane Beacon: {packet.hex()}")

            # decode data
            # * Header
            header = packet[0:5]
            if header != b"BECN\x00":
                logger.warning(f"Unknown packet from {sender[0]}, {str(len(packet))} bytes:")
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
                    beacon_major_version,  # 1 at the time of X-Plane 10.40
                    beacon_minor_version,  # 1 at the time of X-Plane 10.40
                    application_host_id,  # 1 for X-Plane, 2 for PlaneMaker
                    xplane_version_number,  # 104014 for X-Plane 10.40b14
                    role,  # 1 for master, 2 for extern visual, 3 for IOS
                    port,  # port number X-Plane is listening on
                ) = struct.unpack("<BBiiIH", data)
                hostname = packet[21:-1]  # the hostname of the computer
                hostname = hostname[0 : hostname.find(0)]
                if beacon_major_version == 1 and beacon_minor_version <= 2 and application_host_id == 1:
                    self.beacon_data["IP"] = sender[0]
                    self.beacon_data["Port"] = port
                    self.beacon_data["hostname"] = hostname.decode()
                    self.beacon_data["XPlaneVersion"] = xplane_version_number
                    self.beacon_data["role"] = role
                    logger.info(f"XPlane Beacon Version: {beacon_major_version}.{beacon_minor_version}.{application_host_id}")
                else:
                    logger.warning(f"XPlane Beacon Version not supported: {beacon_major_version}.{beacon_minor_version}.{application_host_id}")
                    raise XPlaneVersionNotSupported()

        except socket.timeout:
            logger.debug("XPlane IP not found.")
            raise XPlaneIpNotFound()
        finally:
            sock.close()

        return self.beacon_data

    def connect_loop(self):
        """
        Trys to connect to X-Plane indefinitely until self.should_not_connect is set.
        If a connection fails, drops, disappears, will try periodically to restore it.
        """
        logger.debug("starting..")
        cnt = 0
        while self.should_not_connect is not None and not self.should_not_connect.is_set():
            if not self.connected:
                try:
                    self.FindIp()
                    if self.connected:
                        self._already_warned = 0
                        logger.info(f"beacon: {self.beacon_data}")
                        if "XPlaneVersion" in self.beacon_data:
                            curr = self.beacon_data["XPlaneVersion"]
                            if curr < self.min_version:
                                logger.warning(f"X-Plane version {curr} detected, minimal version is {XP_MIN_VERSION}")
                                logger.warning(f"Some features in Cockpitdecks may not work properly")
                            elif curr > self.max_version:
                                logger.warning(f"X-Plane version {curr} detected, maximal version is {XP_MAX_VERSION}")
                                logger.warning(f"Some features in Cockpitdecks may not work properly")
                            else:
                                logger.info(f"X-Plane version meets current criteria ({XP_MIN_VERSION}<= {curr} <={XP_MAX_VERSION})")
                                logger.info("connected")
                except XPlaneVersionNotSupported:
                    self.beacon_data = {}
                    logger.error("..X-Plane Version not supported..")
                except XPlaneIpNotFound:
                    self.beacon_data = {}
                    if cnt % XPlaneBeacon.WARN_FREQ == 0:
                        logger.error(f"..X-Plane instance not found on local network.. ({datetime.now().strftime('%H:%M:%S')})")
                    cnt = cnt + 1
                if not self.connected:
                    self.should_not_connect.wait(XPlaneBeacon.RECONNECT_TIMEOUT)
                    logger.debug("..trying..")
            else:
                self.should_not_connect.wait(XPlaneBeacon.RECONNECT_TIMEOUT)  # could be n * RECONNECT_TIMEOUT
                logger.debug("..monitoring connection..")
        logger.debug("..ended")

    # ################################
    # Interface
    #
    def connect(self):
        """
        Starts connect loop.
        """
        if self.should_not_connect is None:
            self.should_not_connect = threading.Event()
            self.connect_thread = threading.Thread(target=self.connect_loop, name="XPlaneBeacon::connect_loop")
            self.connect_thread.start()
            logger.debug("connect_loop started")
        else:
            logger.debug("connect_loop already started")

    def disconnect(self):
        """
        End connect loop and disconnect
        """
        if self.should_not_connect is not None:
            logger.debug("disconnecting..")
            self.beacon_data = {}
            self.should_not_connect.set()
            wait = XPlaneBeacon.RECONNECT_TIMEOUT
            logger.debug(f"..asked to stop connect_loop.. (this may last {wait} secs.)")
            self.connect_thread.join(timeout=wait)
            if self.connect_thread.is_alive():
                logger.warning("..thread may hang..")
            self.should_not_connect = None
            logger.debug("..disconnected")
        else:
            if self.connected:
                self.beacon_data = {}
                logger.debug("..connect_loop not running..disconnected")
            else:
                logger.debug("..not connected")

    def set_version_control(self, minversion, maxversion):
        self.min_version = minversion
        self.max_version = maxversion

    def runs_locally(self) -> bool:
        if self.connected:
            return ipaddress.ip_address(self.local_ip) == ipaddress.ip_address(self.beacon_data["IP"])
        return False


if __name__ == "__main__":
    xp = XPlaneBeacon()
    xp.connect()
    print(xp.runs_locally())
