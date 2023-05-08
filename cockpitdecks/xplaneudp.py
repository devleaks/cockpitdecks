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

from .constant import SPAM_LEVEL
from .xplane import XPlane, Dataref
from .button import Button

logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)  # To see which dataref are requested
# logger.setLevel(logging.DEBUG)

# Data too delicate to be put in constant.py
# !! adjust with care !!
DATA_SENT    = 2    # times per second, X-Plane send that data on UDP every that often. Too often will slow down X-PLANE.
DATA_REFRESH = 1 / (4 * DATA_SENT) # secs we poll for data every x seconds,
                    # must be << 1/DATA_SENT to consume faster than produce.
LOOP_ALIVE   = 100  # report loop activity every 1000 executions on DEBUG, set to None to suppress output
RECONNECT_TIMEOUT = 10  # seconds

SOCKET_TIMEOUT    = 10  # seconds
MAX_TIMEOUT_COUNT = 5   # after x timeouts, assumes connection lost, disconnect, and restart later

DATA_PREFIX = "data:"

# The command keywords are not executed, ignored with a warning
NOT_A_COMMAND = ["none", "noop", "no-operation", "no-command", "do-nothing"]
NOT_A_DATAREF = ["DatarefPlaceholder"]

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

        self.beacon_data = {}

        self.should_not_connect = None  # threading.Event()
        self.connect_thread = None      # threading.Thread()

    @property
    def connected(self):
        return "IP" in self.beacon_data.keys()

    def FindIp(self):
        '''
        Find the IP of XPlane Host in Network.
        It takes the first one it can find.
        '''
        if self.socket is not None:
            self.socket.close()
            self.socket = None
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.beacon_data = {}

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
                    self.beacon_data["IP"] = sender[0]
                    self.beacon_data["Port"] = port
                    self.beacon_data["hostname"] = hostname.decode()
                    self.beacon_data["XPlaneVersion"] = xplane_version_number
                    self.beacon_data["role"] = role
                    logger.info(f"FindIp: XPlane Beacon Version: {beacon_major_version}.{beacon_minor_version}.{application_host_id}")
                else:
                    logger.warning(f"FindIp: XPlane Beacon Version not supported: {beacon_major_version}.{beacon_minor_version}.{application_host_id}")
                    raise XPlaneVersionNotSupported()

        except socket.timeout:
            logger.debug("FindIp: XPlane IP not found.")
            raise XPlaneIpNotFound()
        finally:
            sock.close()

        return self.beacon_data

    def start(self):
        logger.warning("start: nothing to start")

    def stop(self):
        logger.warning("stop: nothing to stop")

    def cleanup(self):
        logger.warning("cleanup: nothing to clean up")

    def connect_loop(self):
        """
        Trys to connect to X-Plane indefinitely until self.should_not_connect is set.
        If a connection fails, drops, disappears, will try periodically to restore it.
        """
        logger.debug("connect_loop: starting..")
        WARN_FREQ = 10
        cnt = 0
        while self.should_not_connect is not None and not self.should_not_connect.is_set():
            if not self.connected:
                try:
                    self.FindIp()
                    if self.connected:
                        logger.info(self.beacon_data)
                        logger.debug("connect_loop: ..connected, starting dataref listener..")
                        self.start()
                        logger.info(f"connect_loop: ..dataref listener started..")
                except XPlaneVersionNotSupported:
                    self.beacon_data = {}
                    logger.error("connect_loop: ..X-Plane Version not supported..")
                except XPlaneIpNotFound:
                    self.beacon_data = {}
                    if cnt % WARN_FREQ == 0:
                        logger.error(f"connect_loop: ..X-Plane instance not found on local network.. ({datetime.datetime.now().strftime('%H:%M:%S')})")
                    cnt = cnt + 1
                if not self.connected:
                    self.should_not_connect.wait(RECONNECT_TIMEOUT)
                    logger.debug("connect_loop: ..trying..")
            else:
                self.should_not_connect.wait(RECONNECT_TIMEOUT)  # could be n * RECONNECT_TIMEOUT
                logger.debug("connect_loop: ..monitoring connection..")
        logger.debug("connect_loop: ..ended")

    # ################################
    # Interface
    #
    def connect(self):
        """
        Starts connect loop.
        """
        if self.should_not_connect is None:
            self.should_not_connect = threading.Event()
            self.connect_thread = threading.Thread(target=self.connect_loop)
            self.connect_thread.name = "XPlaneBeacon::connect_loop"
            self.connect_thread.start()
            logger.debug("connect: connect_loop started")
        else:
            logger.debug("connect: connect_loop already started")

    def disconnect(self):
        """
        End connect loop and disconnect
        """
        if self.should_not_connect is not None:
            logger.debug("disconnect: disconnecting..")
            self.cleanup()
            self.beacon_data = {}
            self.should_not_connect.set()
            wait = RECONNECT_TIMEOUT
            logger.debug(f"disconnect: ..asked to stop connect_loop.. (this may last {wait} secs.)")
            self.connect_thread.join(timeout=wait)
            if self.connect_thread.is_alive():
                logger.warning(f"disconnect: ..thread may hang..")
            self.should_not_connect = None
            logger.debug("disconnect: ..disconnected")
        else:
            if self.connected:
                self.beacon_data = {}
                logger.debug("disconnect: ..connect_loop not running..disconnected")
            else:
                logger.debug("disconnect: ..not connected")


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
        self.cockpit.set_logging_level(__name__)

        XPlaneBeacon.__init__(self)

        self.no_dref_listener = None
        self.defaultFreq = 1

        # list of requested datarefs with index number
        self.datarefidx = 0
        self.datarefs = {} # key = idx, value = dataref
        self.init()

    def init(self):
        pass

    def __del__(self):
        for i in range(len(self.datarefs)):
            self.add_dataref_to_monitor(next(iter(self.datarefs.values())), freq=0)
        self.disconnect()

    def get_dataref(self, path):
        if path in self.all_datarefs.keys():
            return self.all_datarefs[path]
        return self.register(Dataref(path))

    def write_dataref(self, dataref, value, vtype='float'):
        '''
        Write Dataref to XPlane
        DREF0+(4byte byte value)+dref_path+0+spaces to complete the whole message to 509 bytes
        DREF0+(4byte byte value of 1)+ sim/cockpit/switches/anti_ice_surf_heat_left+0+spaces to complete to 509 bytes
        '''
        if dataref.startswith(DATA_PREFIX):
            d = self.get_dataref(dataref)
            d.update_value(new_value=value, cascade=True)
            logger.debug(f"write_dataref: written local dataref ({dataref}={value})")
            return

        if not self.connected:
            logger.warning(f"write_dataref: no connection ({dataref}={value})")
            return

        if dataref in NOT_A_DATAREF:
            logger.warning(f"write_dataref: not a dataref ({dataref})")
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
        logger.debug(f"write_dataref: ({self.beacon_data['IP']}, {self.beacon_data['Port']}): {dataref}={value} ..")
        logger.log(SPAM_LEVEL, f"write_dataref: {dataref}={value}")
        self.socket.sendto(message, (self.beacon_data["IP"], self.beacon_data["Port"]))
        logger.debug(f"write_dataref: .. sent")

    def add_dataref_to_monitor(self, dataref, freq = None):
        '''
        Configure XPlane to send the dataref with a certain frequency.
        You can disable a dataref by setting freq to 0.
        '''
        if dataref.startswith(DATA_PREFIX):
            logger.debug(f"add_dataref_to_monitor: {dataref} is local and does not need X-Plane monitoring")
            return False

        if not self.connected:
            logger.warning(f"add_dataref_to_monitor: no connection ({dataref}, {freq})")
            return False

        if dataref in NOT_A_DATAREF:
            logger.warning(f"write_dataref: not a dataref ({dataref})")
            return False

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
        self.socket.sendto(message, (self.beacon_data["IP"], self.beacon_data["Port"]))
        if self.datarefidx%100 == 0:
            time.sleep(0.2)
        return True

    def get_values(self):
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
            check = set()
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
                        check.add(idx)
            # print(check)  # to see which datref get sent
            self.xplaneValues.update(retvalues)
        except:
            raise XPlaneTimeout
        return self.xplaneValues

    def execute_command(self, command: str):
        if command is None or command in NOT_A_COMMAND:
            logger.warning(f"execute_command: command {command} not sent (command placeholder, no command, do nothing)")
            return
        if not self.connected:
            logger.warning(f"execute_command: no connection ({command})")
            return
        if command.lower() in ["none", "placeholder"]:
            logger.debug(f"execute_command: not executed command '{command}' (place holder)")
            return
        message = 'CMND0' + command
        self.socket.sendto(message.encode(), (self.beacon_data["IP"], self.beacon_data["Port"]))
        logger.log(SPAM_LEVEL, f"execute_command: executed {command}")

    def dataref_listener(self):
        logger.debug(f"dataref_listener: starting..")
        i = 0
        total_to = 0
        j1, j2 = 0, 0
        tot1, tot2 = 0.0, 0.0
        while not self.no_dref_listener.is_set():
            nexttime = DATA_REFRESH
            i = i + 1
            if LOOP_ALIVE is not None and i % LOOP_ALIVE == 0 and j1 > 0:
                logger.debug(f"dataref_listener: {i}: {datetime.datetime.now()}, avg_get={round(tot2/j2, 6)}, avg_not={round(tot1/j1, 6)}")
            if len(self.datarefs) > 0:
                try:
                    now = time.time()
                    with self.dataref_db_lock:
                        self.current_values = self.get_values()
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
                    total_to = total_to + 1
                    logger.info(f"dataref_listener: XPlaneTimeout received ({total_to}/{MAX_TIMEOUT_COUNT})")  # ignore
                    if total_to >= MAX_TIMEOUT_COUNT:  # attemps to reconnect
                        logger.warning(f"dataref_listener: too many times out, disconnecting, dataref listener terminated")  # ignore
                        self.beacon_data = {}
                        self.no_dref_listener.set()

            if not self.no_dref_listener.is_set() and nexttime > 0:
                self.no_dref_listener.wait(nexttime)
        self.no_dref_listener = None
        logger.debug(f"dataref_listener: ..terminated")

    # ################################
    # X-Plane Interface
    #
    def commandOnce(self, command: str):
        self.execute_command(command)

    def commandBegin(self, command: str):
        self.execute_command(command+"/begin")

    def commandEnd(self, command: str):
        self.execute_command(command+"/end")

    def remove_local_datarefs(self, datarefs) -> list:
        return list(filter(lambda d: not d.startswith(DATA_PREFIX), datarefs))

    def clean_datarefs_to_monitor(self):
        if not self.connected:
            logger.warning(f"clean_datarefs_to_monitor: no connection")
            return
        for i in range(len(self.datarefs)):
            self.add_dataref_to_monitor(next(iter(self.datarefs.values())), freq=0)
        super().clean_datarefs_to_monitor()
        logger.debug(f"clean_datarefs_to_monitor: done")

    def add_datarefs_to_monitor(self, datarefs):
        if not self.connected:
            logger.warning(f"add_datarefs_to_monitor: no connection")
            logger.debug(f"add_datarefs_to_monitor: would add {self.remove_local_datarefs(datarefs.keys())}")
            return
        # Add those to monitor
        super().add_datarefs_to_monitor(datarefs)
        prnt = []
        for d in datarefs.values():
            if d.path.startswith(DATA_PREFIX):
                logger.debug(f"add_datarefs_to_monitor: local dataref {d.path} is not monitored")
                continue
            if self.add_dataref_to_monitor(d.path, freq=self.slow_datarefs.get(d.path, DATA_SENT)):
                prnt.append(d.path)
        logger.log(SPAM_LEVEL, f"add_datarefs_to_monitor: added {prnt}")

    def remove_datarefs_to_monitor(self, datarefs):
        if not self.connected and len(self.datarefs_to_monitor) > 0:
            logger.warning(f"remove_datarefs_to_monitor: no connection")
            logger.debug(f"remove_datarefs_to_monitor: would remove {datarefs.keys()}")
            return
        # Add those to monitor
        prnt = []
        for d in datarefs.values():
            if d.path.startswith(DATA_PREFIX):
                logger.debug(f"remove_datarefs_to_monitor: local dataref {d.path} is not monitored")
                continue
            if d.path in self.datarefs_to_monitor.keys():
                if self.datarefs_to_monitor[d.path] == 1:  # will be decreased by 1 in super().remove_datarefs_to_monitor()
                    if self.add_dataref_to_monitor(d.path, freq=0):
                        prnt.append(d.path)
                else:
                    logger.debug(f"remove_datarefs_to_monitor: {d.path} monitored {self.datarefs_to_monitor[d.path]} times")
            else:
                logger.debug(f"remove_datarefs_to_monitor: no need to remove {d.path}")
        logger.debug(f"remove_datarefs_to_monitor: removed {prnt}")
        super().remove_datarefs_to_monitor(datarefs)

    def remove_all_datarefs(self):
        if not self.connected and len(self.all_datarefs) > 0:
            logger.warning(f"remove_all_datarefs: no connection")
            logger.debug(f"remove_all_datarefs: would remove {self.all_datarefs.keys()}")
            return
        # Not necessary:
        # self.remove_datarefs_to_monitor(self.all_datarefs)
        super().remove_all_datarefs()

    def add_all_datarefs_to_monitor(self):
        if not self.connected:
            logger.warning(f"add_all_datarefs_to_monitor: no connection")
            return
        # Add those to monitor
        prnt = []
        for path in self.datarefs_to_monitor.keys():
            if self.add_dataref_to_monitor(path, freq=DATA_SENT):
                prnt.append(path)
        logger.log(SPAM_LEVEL, f"add_all_datarefs_to_monitor: added {prnt}")

    def cleanup(self):
        """
        Called when before disconnecting.
        Just before disconnecting, we try to cancel dataref UDP reporting in X-Plane
        """
        self.clean_datarefs_to_monitor()

    def start(self):
        if not self.connected:
            logger.warning(f"start: no IP address. could not start.")
            return
        if self.no_dref_listener is None:
            self.no_dref_listener = threading.Event()
            self.thread = threading.Thread(target=self.dataref_listener)
            self.thread.name = f"XPlaneUDP::datarefs_listener"
            self.thread.start()
            logger.info(f"start: XPlaneUDP started")
        else:
            logger.info(f"start: XPlaneUDP already running.")
        # When restarted after network failure, should clean all datarefs
        # then reload datarefs from current page of each deck
        self.clean_datarefs_to_monitor()
        self.add_all_datarefs_to_monitor()
        self.cockpit.reload_pages()  # to take into account updated values

    def stop(self):
        if self.no_dref_listener is not None:
            self.no_dref_listener.set()
            logger.debug(f"stop: stopping..")
            wait = SOCKET_TIMEOUT
            logger.debug(f"stop: ..asked to stop dataref listener (this may last {wait} secs. for UDP socket to timeout)..")
            self.thread.join(wait)
            if self.thread.is_alive():
                logger.warning(f"stop: ..thread may hang in socket.recvfrom()..")
            self.no_dref_listener = None
            logger.debug(f"stop: ..stopped")
        else:
            logger.debug(f"stop: not running")

    # ################################
    # Cockpit interface
    #
    def terminate(self):
        logger.debug(f"terminate: currently {'not ' if self.no_dref_listener is None else ''}running. terminating..")
        self.remove_all_datarefs()
        logger.info(f"terminate: terminating..disconnecting..")
        self.disconnect()
        logger.info(f"terminate: ..stopping..")
        self.stop()
        logger.info(f"terminate: ..terminated")
