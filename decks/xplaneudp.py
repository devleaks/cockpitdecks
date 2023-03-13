# Class for interface with X-Plane using X-Plane SDK
# To be used when run as an external program via UDP access.
#
import socket
import struct
import binascii
import platform
import threading
import logging
import time
import datetime

from .constant import SPAM
from .xplane import XPlane, Dataref
from .button import Button

logger = logging.getLogger("XPlaneUDP")
# logger.setLevel(logging.DEBUG)
# logger.setLevel(SPAM)

# Data too delicate to be put in constant.py
# !! adjust with care !!
DATA_SENT    = 2    # times per second, X-Plane send that data on UDP every that often. Too often = SLOW
DATA_REFRESH = 1 / (4 * DATA_SENT) # secs we poll for data every x seconds,
                    # must be < 0.1 for UDP, and < 1/DATA_SENT to consume faster than produce.
LOOP_ALIVE   = 100  # report loop activity every 1000 executions on DEBUG, set to None to suppress output
RECONNECT_TIMEOUT = 10  # seconds

SOCKET_TIMEOUT    = 10  # seconds
MAX_TIMEOUT_COUNT = 5   # after x timeouts, assumes connection lost, disconnect, and restart later

# XPlaneBeacon
# Beacon-specific error classes
#
class XPlaneIpNotFound(Exception):
    args = "Could not find any running XPlane instance in network."

class XPlaneTimeout(Exception):
    args = "XPlane timeout."

class XPlaneVersionNotSupported(Exception):
    args = "XPlane version not supported."

class XPlaneBeacon:
    '''
    Get data from XPlane via network.
    Use a class to implement RAI Pattern for the UDP socket.
    '''
    #constants
    MCAST_GRP = "239.255.1.1"
    MCAST_PORT = 49707 # (MCAST_PORT was 49000 for XPlane10)
    BEACON_TIMEOUT = 3.0  # seconds

    def __init__(self):
        # Open a UDP Socket to receive on Port 49000
        self.socket = None

        self.connected = False
        self.should_run = False

        self.connect_thread = None
        self.BeaconData = {}

    def FindIp(self):
        '''
        Find the IP of XPlane Host in Network.
        It takes the first one it can find.
        '''
        if self.socket is not None:
            self.socket.close()
            self.socket = None
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.BeaconData = {}

        # open socket for multicast group.
        # this socker is for getting the beacon, it can be closed when beacon is found.
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if platform.system() == "Windows":
            sock.bind(('', self.MCAST_PORT))
        else:
            sock.bind((self.MCAST_GRP, self.MCAST_PORT))
        mreq = struct.pack("=4sl", socket.inet_aton(self.MCAST_GRP), socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        sock.settimeout(XPlaneBeacon.BEACON_TIMEOUT)

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
            logger.warning("FindIp: XPlane IP not found.")
            raise XPlaneIpNotFound()
        finally:
            sock.close()

        return self.BeaconData

    def start(self):
        logger.warning("start: nothing to start")

    def stop(self):
        logger.warning("stop: nothing to stop")

    def connect_loop(self):
        logger.debug("connect_loop: connecting..")
        while self.should_run:
            if not self.connected:
                try:
                    self.FindIp()
                    if "IP" in self.BeaconData:
                        self.connected = True
    #                    self.should_run = False
                    logger.info(self.BeaconData)
                    logger.debug("connect_loop: ..starting..")
                    self.start()
                    logger.info(f"connect_loop: connected, dataref listener started")  # ignore
                except XPlaneVersionNotSupported:
                    self.BeaconData = {}
                    self.connected = False
                    logger.error("connect_loop: XPlane Version not supported.")
                except XPlaneIpNotFound:
                    self.BeaconData = {}
                    self.connected = False
                    # logger.error("connect_loop: XPlane IP not found. Probably there is no XPlane running in your local network.")
                if not self.connected:
                    time.sleep(RECONNECT_TIMEOUT)
                    logger.debug("connect_loop: ..trying..")
            else:
                time.sleep(RECONNECT_TIMEOUT)
                logger.debug("connect_loop: ..awake..")
        logger.debug("connect_loop: ..ended")

    # ################################
    # Interface
    #
    def connect(self):
        if not self.should_run:
            self.should_run = True
            self.connect_thread = threading.Thread(target=self.connect_loop)
            self.connect_thread.name = "XPlaneBeacon::connect_loop"
            self.connect_thread.start()
            logger.debug("connect: connect_loop started")
        else:
            logger.debug("connect: connect_loop already started")

    def disconnect(self):
        if self.should_run:
            logger.debug("disconnect: disconnecting..")
            self.BeaconData = {}
            self.connected = False
            self.should_run = False
            wait = RECONNECT_TIMEOUT
            logger.debug(f"disconnect: ..asked to stop connect_loop.. (this may last {wait} secs.)")
            self.connect_thread.join(timeout=wait)
            if self.connect_thread.is_alive():
                logger.warning(f"disconnect: ..thread may hang..")
            logger.debug("disconnect: ..disconnected")
        else:
            logger.debug("disconnect: not connected")


class XPlaneUDP(XPlane, XPlaneBeacon):
    '''
    Get data from XPlane via network.
    Use a class to implement RAI Pattern for the UDP socket.
    '''

    #constants
    MCAST_GRP = "239.255.1.1"
    MCAST_PORT = 49707 # (MCAST_PORT was 49000 for XPlane10)
    BEACON_TIMEOUT = 3.0  # seconds

    def __init__(self, decks):
        XPlane.__init__(self, decks=decks)
        XPlaneBeacon.__init__(self)

        self.defaultFreq = 1

        # list of requested datarefs with index number
        self.datarefidx = 0
        self.datarefs = {} # key = idx, value = dataref

        self.init()

    def init(self):
        pass
        # self.connect()

    def __del__(self):
        for i in range(len(self.datarefs)):
            self.AddDataRef(next(iter(self.datarefs.values())), freq=0)
        self.disconnect()

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
        if not self.is_connected():
            logger.warning(f"WriteDataRef: no connection ({dataref})")
            return

        cmd = b"DREF\x00"
        dataref = dataref + '\x00'
        string = dataref.ljust(500).encode()
        message = "".encode()
        if vtype == "float":
            message = struct.pack("<5sf500s", cmd, value, string)
        elif vtype == "int":
            message = struct.pack("<5si500s", cmd, value, string)
        elif vtype == "bool":
            message = struct.pack("<5sI500s", cmd, int(value), string)

        assert(len(message)==509)
        logger.debug(f"WriteDataRef: ({self.BeaconData['IP']}, {self.BeaconData['Port']}): {dataref}={value} ..")
        logger.log(SPAM, f"WriteDataRef: {dataref}={value}")
        self.socket.sendto(message, (self.BeaconData["IP"], self.BeaconData["Port"]))
        logger.debug(f"WriteDataRef: .. sent")

    def AddDataRef(self, dataref, freq = None):
        '''
        Configure XPlane to send the dataref with a certain frequency.
        You can disable a dataref by setting freq to 0.
        '''
        if not self.is_connected():
            logger.warning(f"AddDataRef: no connection ({dataref}, {freq})")
            return
        idx = -9999
        if freq is None:
            freq = self.defaultFreq

        if dataref in self.datarefs.values():
            idx = list(self.datarefs.keys())[list(self.datarefs.values()).index(dataref)]
            if freq == 0:
                if dataref in self.xplaneValues.keys():
                    del self.xplaneValues[dataref]
                del self.datarefs[idx]
        else:
            idx = self.datarefidx
            self.datarefs[self.datarefidx] = dataref
            self.datarefidx += 1

        cmd = b"RREF\x00"
        string = dataref.encode()
        message = struct.pack("<5sii400s", cmd, freq, idx, string)
        assert(len(message)==413)
        self.socket.sendto(message, (self.BeaconData["IP"], self.BeaconData["Port"]))
        if self.datarefidx%100 == 0:
            time.sleep(0.2)

    def GetValues(self):
        """
        Gets the values from X-Plane for each dataref in self.datarefs.
        On returns {dataref-name: value} dict.
        """
        try:
            # Receive packet
            self.socket.settimeout(SOCKET_TIMEOUT)
            data, addr = self.socket.recvfrom(1472) # maximum bytes of an RREF answer X-Plane will send (Ethernet MTU - IP hdr - UDP hdr)
            # Decode Packet
            retvalues = {}
            # * Read the Header "RREFO".
            header=data[0:5]
            if header != b"RREF,": # (was b"RREFO" for XPlane10)
                logger.warning(f"Unknown packet: {binascii.hexlify(data)}")
            else:
                # * We get 8 bytes for every dataref sent:
                #     An integer for idx and the float value.
                values =data[5:]
                lenvalue = 8
                numvalues = int(len(values)/lenvalue)
                for i in range(0,numvalues):
                    singledata = data[(5+lenvalue*i):(5+lenvalue*(i+1))]
                    (idx,value) = struct.unpack("<if", singledata)
                    if idx in self.datarefs.keys():
                        # convert -0.0 values to positive 0.0
                        if value < 0.0 and value > -0.001 :
                            value = 0.0
                        retvalues[self.datarefs[idx]] = value
            self.xplaneValues.update(retvalues)
        except:
            raise XPlaneTimeout
        return self.xplaneValues

    def ExecuteCommand(self, command: str):
        if not self.is_connected():
            logger.warning(f"ExecuteCommand: no connection ({command})")
            return
        if command.lower() in ["none", "placeholder"]:
            logger.debug(f"ExecuteCommand: not executed command '{command}' (place holder)")
            return
        message = 'CMND0' + command
        self.socket.sendto(message.encode(), (self.BeaconData["IP"], self.BeaconData["Port"]))
        logger.log(SPAM, f"ExecuteCommand: executed {command}")

    def loop(self):
        logger.debug(f"loop: started..")
        i = 0
        total_to = 0
        j1, j2 = 0, 0
        tot1, tot2 = 0.0, 0.0
        while self.running:
            nexttime = DATA_REFRESH
            i = i + 1
            if LOOP_ALIVE is not None and i % LOOP_ALIVE == 0 and j1 > 0:
                logger.debug(f"loop: {i}: {datetime.datetime.now()}, avg_get={round(tot2/j2, 6)}, avg_not={round(tot1/j1, 6)}")
            if len(self.datarefs) > 0:
                try:
                    now = time.time()
                    with self.dataref_db_lock:
                        self.current_values = self.GetValues()
                    later = time.time()
                    j2 = j2 + 1
                    tot2 = tot2 + (later - now)

                    now = time.time()
                    self.detect_changed()
                    later = time.time()
                    j1 = j1 + 1
                    tot1 = tot1 + (later - now)
                    nexttime = DATA_REFRESH - (later - now)
                    total_to = 0
                except XPlaneTimeout:
                    logger.info(f"loop: XPlaneTimeout ({total_to})")  # ignore
                    total_to = total_to + 1
                    if total_to > MAX_TIMEOUT_COUNT:  # attemps to reconnect
                        logger.warning(f"loop: too many times out, disconnecting, dataref listener terminated")  # ignore
                        self.connected = False  # notify above that connection lost
                        self.running = False    # auto stop

            if nexttime > 0:
                time.sleep(nexttime)
        logger.debug(f"loop: ..terminated")

    # ################################
    # X-Plane Interface
    #
    def commandOnce(self, command: str):
        self.ExecuteCommand(command)

    def commandBegin(self, command: str):
        self.ExecuteCommand(command+"/begin")

    def commandEnd(self, command: str):
        self.ExecuteCommand(command+"/end")

    def clean_datarefs_to_monitor(self):
        if not self.is_connected():
            logger.warning(f"clean_datarefs_to_monitor: no connection")
            return
        for i in range(len(self.datarefs)):
            self.AddDataRef(next(iter(self.datarefs.values())), freq=0)
        super().clean_datarefs_to_monitor()
        logger.debug(f"clean_datarefs_to_monitor: done")

    def add_datarefs_to_monitor(self, datarefs):
        if not self.is_connected():
            logger.warning(f"add_datarefs_to_monitor: no connection")
            logger.debug(f"add_datarefs_to_monitor: would add {datarefs.keys()}")
            return
        # Add those to monitor
        super().add_datarefs_to_monitor(datarefs)
        prnt = []
        for d in datarefs.values():
            self.AddDataRef(d.path, freq=DATA_SENT)
            prnt.append(d.path)
        logger.log(SPAM, f"add_datarefs_to_monitor: added {prnt}")

    def remove_datarefs_to_monitor(self, datarefs):
        if not self.is_connected():
            logger.warning(f"remove_datarefs_to_monitor: no connection")
            logger.debug(f"remove_datarefs_to_monitor: would remove {datarefs.keys()}")
            return
        # Add those to monitor
        prnt = []
        for d in datarefs.values():
            if d.path in self.datarefs_to_monitor.keys():
                if self.datarefs_to_monitor[d.path] == 1:  # will be decreased by 1 in super().remove_datarefs_to_monitor()
                    self.AddDataRef(d.path, freq=0)
                    prnt.append(d.path)
                else:
                    logger.debug(f"remove_datarefs_to_monitor: {d.path} monitored {self.datarefs_to_monitor[d.path]} times")
            else:
                logger.debug(f"remove_datarefs_to_monitor: no need to remove {d.path}")
        logger.debug(f"remove_datarefs_to_monitor: removed {prnt}")
        super().remove_datarefs_to_monitor(datarefs)

    def add_all_datarefs_to_monitor(self):
        if not self.is_connected():
            logger.warning(f"add_all_datarefs_to_monitor: no connection")
            return
        # Add those to monitor
        prnt = []
        for path in self.datarefs_to_monitor.keys():
            self.AddDataRef(path, freq=DATA_SENT)
            prnt.append(path)
        logger.log(SPAM, f"add_all_datarefs_to_monitor: added {prnt}")

    def start(self):
        if not self.is_connected():
            logger.warning(f"start: no IP address. could not start.")
            return
        if not self.running:
            self.thread = threading.Thread(target=self.loop)
            self.thread.name = f"XPlaneUDP::datarefs_watcher"
            self.running = True
            self.thread.start()
            logger.info(f"start: XPlaneUDP started")
        else:
            logger.info(f"start: XPlaneUDP already running.")
        # When restarted after network failure, should clean all datarefs
        # then reload datarefs from current page of each deck
        self.clean_datarefs_to_monitor()
        self.add_all_datarefs_to_monitor()
        self.cockpit.reload_pages()

    def stop(self):
        if self.running:
            logger.debug(f"stop: stopping..")
            self.running = False
            wait = SOCKET_TIMEOUT
            logger.debug(f"stop: ..asked to stop loop.. (this may last {wait} secs.)")
            self.thread.join(wait)
            if self.thread.is_alive():
                logger.warning(f"stop: ..thread may hang in socket.recvfrom()..")
            logger.debug(f"stop: ..stopped")
        else:
            logger.info(f"stop: not running")

    # ################################
    # Cockpit interface
    #
    def terminate(self):
        logger.debug(f"terminate: currently {'not ' if not self.running else ''}running. terminating..")
        logger.info(f"terminate: ..disconnecting..")
        self.disconnect()
        logger.info(f"terminate: ..stopping..")
        self.stop()
        logger.info(f"terminate: ..terminated")
