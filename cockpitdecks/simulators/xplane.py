# Class for interface with X-Plane using UDP protocol.
#
import socket
import struct
import binascii
import platform
import threading
import logging
import time
import datetime

from cockpitdecks import SPAM_LEVEL
from cockpitdecks.simulator import Simulator, Dataref, Command, NOT_A_DATAREF
from cockpitdecks.button import Button
from cockpitdecks.simulator import DatarefSetCollector

logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)  # To see which dataref are requested
# logger.setLevel(logging.DEBUG)

# Data too delicate to be put in constant.py
# !! adjust with care !!
DATA_SENT = 2  # times per second, X-Plane send that data on UDP every that often. Too often will slow down X-PLANE.
DATA_REFRESH = 1 / (4 * DATA_SENT)  # secs we poll for data every x seconds,
# must be << 1/DATA_SENT to consume faster than produce.
# UDP sends at most ~40 to ~50 dataref values per packet.
DEFAULT_REQ_FREQUENCY = 1
LOOP_ALIVE = 100  # report loop activity every 1000 executions on DEBUG, set to None to suppress output
RECONNECT_TIMEOUT = 10  # seconds

SOCKET_TIMEOUT = 10  # seconds
MAX_TIMEOUT_COUNT = 5  # after x timeouts, assumes connection lost, disconnect, and restart later

MAX_DREF_COUNT = 80  # Maximum number of dataref that can be requested to X-Plane, CTD around ~100 datarefs

# When this (internal) dataref changes, the loaded aircraft has changed
#
AIRCRAFT_DATAREF_IPC = Dataref.mk_internal_dataref("_aircraft_icao")


# XPlaneBeacon
# Beacon-specific error classes
class XPlaneIpNotFound(Exception):
    args = "Could not find any running XPlane instance in network."


class XPlaneTimeout(Exception):
    args = "XPlane timeout."


class XPlaneVersionNotSupported(Exception):
    args = "XPlane version not supported."


class XPlaneBeacon:
    """
    Get data from XPlane via network.
    Use a class to implement RAI Pattern for the UDP socket.
    """

    # constants
    MCAST_GRP = "239.255.1.1"
    MCAST_PORT = 49707  # (MCAST_PORT was 49000 for XPlane10)
    BEACON_TIMEOUT = 3.0  # seconds

    def __init__(self):
        # Open a UDP Socket to receive on Port 49000
        self.socket = None

        self.beacon_data = {}

        self.should_not_connect = None  # threading.Event()
        self.connect_thread = None  # threading.Thread()

    @property
    def connected(self):
        return "IP" in self.beacon_data.keys()

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
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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

    def start(self):
        logger.warning("nothing to start")

    def stop(self):
        logger.warning("nothing to stop")

    def cleanup(self):
        logger.warning("nothing to clean up")

    def connect_loop(self):
        """
        Trys to connect to X-Plane indefinitely until self.should_not_connect is set.
        If a connection fails, drops, disappears, will try periodically to restore it.
        """
        logger.debug("starting..")
        WARN_FREQ = 10
        cnt = 0
        while self.should_not_connect is not None and not self.should_not_connect.is_set():
            if not self.connected:
                try:
                    self.FindIp()
                    if self.connected:
                        logger.info(self.beacon_data)
                        logger.debug("..connected, starting dataref listener..")
                        self.start()
                        logger.info("..dataref listener started..")
                except XPlaneVersionNotSupported:
                    self.beacon_data = {}
                    logger.error("..X-Plane Version not supported..")
                except XPlaneIpNotFound:
                    self.beacon_data = {}
                    if cnt % WARN_FREQ == 0:
                        logger.error(f"..X-Plane instance not found on local network.. ({datetime.datetime.now().strftime('%H:%M:%S')})")
                    cnt = cnt + 1
                if not self.connected:
                    self.should_not_connect.wait(RECONNECT_TIMEOUT)
                    logger.debug("..trying..")
            else:
                self.should_not_connect.wait(RECONNECT_TIMEOUT)  # could be n * RECONNECT_TIMEOUT
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
            self.connect_thread = threading.Thread(target=self.connect_loop)
            self.connect_thread.name = "XPlaneBeacon::connect_loop"
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
            self.cleanup()
            self.beacon_data = {}
            self.should_not_connect.set()
            wait = RECONNECT_TIMEOUT
            logger.debug(f"..asked to stop connect_loop.. (this may last {wait} secs.)")
            self.connect_thread.join(timeout=wait)
            if self.connect_thread.is_alive():
                logger.warning(f"..thread may hang..")
            self.should_not_connect = None
            logger.debug("..disconnected")
        else:
            if self.connected:
                self.beacon_data = {}
                logger.debug("..connect_loop not running..disconnected")
            else:
                logger.debug("..not connected")


class XPlane(Simulator, XPlaneBeacon):
    """
    Get data from XPlane via network.
    Use a class to implement RAI Pattern for the UDP socket.
    """

    # constants
    MCAST_GRP = "239.255.1.1"
    MCAST_PORT = 49707  # (MCAST_PORT was 49000 for XPlane10)
    BEACON_TIMEOUT = 3.0  # seconds

    def __init__(self, cockpit):
        Simulator.__init__(self, cockpit=cockpit)
        self.cockpit.set_logging_level(__name__)

        XPlaneBeacon.__init__(self)
        self.collector = DatarefSetCollector(self)

        self.no_dref_listener = None

        # list of requested datarefs with index number
        self.datarefidx = 0
        self.datarefs = {}  # key = idx, value = dataref path
        self._max_monitored = 0
        self.init()

    def init(self):
        dref = Dataref(AIRCRAFT_DATAREF_IPC)
        dref.add_listener(self.cockpit)  # Wow wow wow
        self.register(dref)
        logger.info(f"internal aircraft dataref is {AIRCRAFT_DATAREF_IPC}")

    def __del__(self):
        for i in range(len(self.datarefs)):
            self.add_dataref_to_monitor(next(iter(self.datarefs.values())), freq=0)
        self.disconnect()

    def get_dataref(self, path):
        if path in self.all_datarefs.keys():
            return self.all_datarefs[path]
        return self.register(Dataref(path))

    def write_dataref(self, dataref, value, vtype="float"):
        """
        Write Dataref to XPlane
        DREF0+(4byte byte value)+dref_path+0+spaces to complete the whole message to 509 bytes
        DREF0+(4byte byte value of 1)+ sim/cockpit/switches/anti_ice_surf_heat_left+0+spaces to complete to 509 bytes
        """
        path = dataref
        if Dataref.is_internal_dataref(path):
            d = self.get_dataref(path)
            d.update_value(new_value=value, cascade=True)
            logger.debug(f"written local dataref ({path}={value})")
            return

        if not self.connected:
            logger.warning(f"no connection ({path}={value})")
            return

        if path in NOT_A_DATAREF:
            logger.warning(f"not a dataref ({path})")
            return

        cmd = b"DREF\x00"
        path = path + "\x00"
        string = path.ljust(500).encode()
        message = "".encode()
        if vtype == "float":
            message = struct.pack("<5sf500s", cmd, value, string)
        elif vtype == "int":
            message = struct.pack("<5si500s", cmd, value, string)
        elif vtype == "bool":
            message = struct.pack("<5sI500s", cmd, int(value), string)

        assert len(message) == 509
        logger.debug(f"({self.beacon_data['IP']}, {self.beacon_data['Port']}): {path}={value} ..")
        logger.log(SPAM_LEVEL, f"write_dataref: {path}={value}")
        self.socket.sendto(message, (self.beacon_data["IP"], self.beacon_data["Port"]))
        logger.debug(".. sent")

    def add_dataref_to_monitor(self, path, freq=None):
        """
        Configure XPlane to send the dataref with a certain frequency.
        You can disable a dataref by setting freq to 0.
        """
        if Dataref.is_internal_dataref(path):
            logger.debug(f"{path} is local and does not need X-Plane monitoring")
            return False

        if not self.connected:
            logger.warning(f"no connection ({path}, {freq})")
            return False

        if path in NOT_A_DATAREF:
            logger.warning(f"not a path ({path})")
            return False

        idx = -9999
        if freq is None:
            freq = DEFAULT_REQ_FREQUENCY

        if path in self.datarefs.values():
            idx = list(self.datarefs.keys())[list(self.datarefs.values()).index(path)]
            if freq == 0:
                if path in self.simdrefValues.keys():
                    del self.simdrefValues[path]
                del self.datarefs[idx]
        else:
            if freq != 0 and len(self.datarefs) > MAX_DREF_COUNT:
                logger.warning(f"requesting too many datarefs ({len(self.datarefs)})")
                return False

            idx = self.datarefidx
            self.datarefs[self.datarefidx] = path
            self.datarefidx += 1

        self._max_monitored = max(self._max_monitored, len(self.datarefs))

        cmd = b"RREF\x00"
        string = path.encode()
        message = struct.pack("<5sii400s", cmd, freq, idx, string)
        assert len(message) == 413
        self.socket.sendto(message, (self.beacon_data["IP"], self.beacon_data["Port"]))
        if self.datarefidx % 100 == 0:
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
            data, addr = self.socket.recvfrom(1472)  # maximum bytes of an RREF answer X-Plane will send (Ethernet MTU - IP hdr - UDP hdr)
            # Decode Packet
            retvalues = {}
            check = set()
            # * Read the Header "RREFO".
            header = data[0:5]
            if header != b"RREF,":  # (was b"RREFO" for XPlane10)
                logger.warning(f"{binascii.hexlify(data)}")
            else:
                # * We get 8 bytes for every dataref sent:
                #    An integer for idx and the float value.
                values = data[5:]
                lenvalue = 8
                numvalues = int(len(values) / lenvalue)
                for i in range(0, numvalues):
                    singledata = data[(5 + lenvalue * i) : (5 + lenvalue * (i + 1))]
                    (idx, value) = struct.unpack("<if", singledata)
                    if idx in self.datarefs.keys():
                        # convert -0.0 values to positive 0.0
                        if value < 0.0 and value > -0.001:
                            value = 0.0
                        retvalues[self.datarefs[idx]] = value
                        check.add(idx)
            self.simdrefValues.update(retvalues)
            # logger.debug(f"{datetime.datetime.now()}, datarefs sent:{check}")
            # logger.debug(f"{datetime.datetime.now()}, datarefs sent:{list(retvalues.keys())}")
            # logger.debug(f"{datetime.datetime.now()}, updated {len(retvalues)} values.")
        except:
            raise XPlaneTimeout
        return self.simdrefValues

    def execute_command(self, command: Command):
        if command is None:
            logger.warning(f"no command")
            return
        elif not command.has_command():
            logger.warning(f"command '{command}' not sent (command placeholder, no command, do nothing)")
            return
        if not self.connected:
            logger.warning(f"no connection ({command})")
            return
        message = "CMND0" + command.path
        self.socket.sendto(message.encode(), (self.beacon_data["IP"], self.beacon_data["Port"]))
        logger.log(SPAM_LEVEL, f"execute_command: executed {command}")

    def dataref_listener(self):
        logger.debug("starting..")
        i = 0
        total_to = 0
        j1, j2 = 0, 0
        tot1, tot2 = 0.0, 0.0
        while not self.no_dref_listener.is_set():
            nexttime = DATA_REFRESH
            i = i + 1
            if LOOP_ALIVE is not None and i % LOOP_ALIVE == 0 and j1 > 0:
                logger.debug(f"{i}: {datetime.datetime.now()}, avg_get={round(tot2/j2, 6)}, avg_not={round(tot1/j1, 6)}")
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
                    logger.info(f"XPlaneTimeout received ({total_to}/{MAX_TIMEOUT_COUNT})")  # ignore
                    if total_to >= MAX_TIMEOUT_COUNT:  # attemps to reconnect
                        logger.warning("too many times out, disconnecting, dataref listener terminated")  # ignore
                        self.beacon_data = {}
                        self.no_dref_listener.set()

            if not self.no_dref_listener.is_set() and nexttime > 0:
                self.no_dref_listener.wait(nexttime)
        self.no_dref_listener = None
        logger.debug("..terminated")

    # ################################
    # X-Plane Interface
    #
    def commandOnce(self, command: Command):
        self.execute_command(command)

    def commandBegin(self, command: Command):
        self.execute_command(Command(command.path + "/begin"))

    def commandEnd(self, command: Command):
        self.execute_command(Command(command.path + "/end"))

    def remove_local_datarefs(self, datarefs) -> list:
        return list(filter(lambda d: not Dataref.is_internal_dataref(d), datarefs))

    def clean_datarefs_to_monitor(self):
        if not self.connected:
            logger.warning("no connection")
            return
        for i in range(len(self.datarefs)):
            self.add_dataref_to_monitor(next(iter(self.datarefs.values())), freq=0)
        super().clean_datarefs_to_monitor()
        logger.debug("done")

    def add_datarefs_to_monitor(self, datarefs):
        if not self.connected:
            logger.warning("no connection")
            logger.debug(f"would add {self.remove_local_datarefs(datarefs.keys())}")
            return
        # Add those to monitor
        super().add_datarefs_to_monitor(datarefs)
        prnt = []
        for d in datarefs.values():
            if d.is_internal():
                logger.debug(f"local dataref {d.path} is not monitored")
                continue
            if self.add_dataref_to_monitor(d.path, freq=d.update_frequency):
                prnt.append(d.path)

        # Add aircraft
        dref_ipc = self.get_dataref(AIRCRAFT_DATAREF_IPC)
        if self.add_dataref_to_monitor(dref_ipc.path, freq=dref_ipc.update_frequency):
            prnt.append(dref_ipc.path)
            super().add_datarefs_to_monitor({dref_ipc.path: dref_ipc})

        logger.log(SPAM_LEVEL, f"add_datarefs_to_monitor: added {prnt}")
        logger.debug(f">>>>> monitoring++{len(self.datarefs)}/{self._max_monitored}")

    def remove_datarefs_to_monitor(self, datarefs):
        if not self.connected and len(self.datarefs_to_monitor) > 0:
            logger.warning("no connection")
            logger.debug(f"would remove {datarefs.keys()}/{self._max_monitored}")
            return
        # Add those to monitor
        prnt = []
        for d in datarefs.values():
            if d.is_internal():
                logger.debug(f"local dataref {d.path} is not monitored")
                continue
            if d.path in self.datarefs_to_monitor.keys():
                if self.datarefs_to_monitor[d.path] == 1:  # will be decreased by 1 in super().remove_datarefs_to_monitor()
                    if self.add_dataref_to_monitor(d.path, freq=0):
                        prnt.append(d.path)
                else:
                    logger.debug(f"{d.path} monitored {self.datarefs_to_monitor[d.path]} times")
            else:
                logger.debug(f"no need to remove {d.path}")

        # Add aircraft path
        dref_ipc = self.get_dataref(AIRCRAFT_DATAREF_IPC)
        if self.add_dataref_to_monitor(dref_ipc.path, freq=0):
            prnt.append(dref_ipc.path)
            super().remove_datarefs_to_monitor({dref_ipc.path: dref_ipc})

        logger.debug(f"removed {prnt}")
        super().remove_datarefs_to_monitor(datarefs)
        logger.debug(f">>>>> monitoring--{len(self.datarefs)}")

    def remove_all_datarefs(self):
        if not self.connected and len(self.all_datarefs) > 0:
            logger.warning("no connection")
            logger.debug(f"would remove {self.all_datarefs.keys()}")
            return
        # Not necessary:
        # self.remove_datarefs_to_monitor(self.all_datarefs)
        super().remove_all_datarefs()

    def add_collections_to_monitor(self, collections):
        # if not self.connected:
        #   logger.warning(f"no connection")
        #   logger.debug(f"would add collection {collections.keys()} to monitor")
        #   return
        for k, v in collections.items():
            self.collector.add_collection(v, start=False)
            logger.debug(f"added collection {k}")

    def remove_collections_to_monitor(self, collections):
        # if not self.connected:
        #   logger.warning(f"no connection")
        #   logger.debug(f"would remove collection {collections.keys()} from monitor")
        #   return
        for k, v in collections.items():
            self.collector.remove_collection(v, start=False)
            logger.debug(f"removed collection {k}")

    def remove_all_collections(self):
        # if not self.connected:
        #   logger.warning(f"no connection")
        #   logger.debug(f"would remove all collections from monitor")
        #   return
        self.collector.remove_all_collections()
        logger.debug("removed all collections from monitor")

    def add_all_datarefs_to_monitor(self):
        if not self.connected:
            logger.warning("no connection")
            return
        # Add those to monitor
        prnt = []
        for path in self.datarefs_to_monitor.keys():
            if self.add_dataref_to_monitor(path, freq=DATA_SENT):
                prnt.append(path)
        logger.log(SPAM_LEVEL, f"added {prnt}")

        # Add collector ticker
        # self.collector.add_ticker()
        # logger.info("..dataref sets collector ticking..")

    def cleanup(self):
        """
        Called when before disconnecting.
        Just before disconnecting, we try to cancel dataref UDP reporting in X-Plane
        """
        self.clean_datarefs_to_monitor()

    def start(self):
        if not self.connected:
            logger.warning("no IP address. could not start.")
            return
        if self.no_dref_listener is None:
            self.no_dref_listener = threading.Event()
            self.thread = threading.Thread(target=self.dataref_listener)
            self.thread.name = "XPlaneUDP::datarefs_listener"
            self.thread.start()
            logger.info("XPlaneUDP started")
        else:
            logger.info("XPlaneUDP already running.")
        # When restarted after network failure, should clean all datarefs
        # then reload datarefs from current page of each deck
        self.clean_datarefs_to_monitor()
        self.add_all_datarefs_to_monitor()
        logger.info("reloading pages")
        self.cockpit.reload_pages()  # to take into account updated values

    def stop(self):
        if self.no_dref_listener is not None:
            self.no_dref_listener.set()
            logger.debug("stopping..")
            wait = SOCKET_TIMEOUT
            logger.debug(f"..asked to stop dataref listener (this may last {wait} secs. for UDP socket to timeout)..")
            self.thread.join(wait)
            if self.thread.is_alive():
                logger.warning("..thread may hang in socket.recvfrom()..")
            self.no_dref_listener = None
            logger.debug("..stopped")
        else:
            logger.debug("not running")

    # ################################
    # Cockpit interface
    #
    def terminate(self):
        logger.debug(f"currently {'not ' if self.no_dref_listener is None else ''}running. terminating..")
        self.remove_all_collections()  # this does not destroy datarefs, only unload current collection
        self.remove_all_datarefs()
        logger.info("terminating..disconnecting..")
        self.disconnect()
        logger.info("..stopping..")
        self.stop()
        if self.collector is not None:
            logger.info("..terminating Collector..")
            self.collector.terminate()
        else:
            logger.info("..no Collector..")
        logger.info("..terminated")
