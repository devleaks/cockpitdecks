# Class for interface with X-Plane using UDP protocol.
#
import socket
import struct
import binascii
import platform
import threading
import logging
import time
from datetime import datetime, timedelta
from queue import Queue

from cockpitdecks import SPAM_LEVEL
from cockpitdecks.simulator import Simulator, Dataref, Command, NOT_A_DATAREF
from cockpitdecks.simulator import DatarefSetCollector

logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)  # To see which dataref are requested
# logger.setLevel(logging.DEBUG)

# Data too delicate to be put in constant.py
# !! adjust with care !!
# UDP sends at most ~40 to ~50 dataref values per packet.
DEFAULT_REQ_FREQUENCY = 1  # if no frequency is supplied (or forced to None), this is used
LOOP_ALIVE = 100  # report loop activity every 1000 executions on DEBUG, set to None to suppress output
RECONNECT_TIMEOUT = 10  # seconds
SOCKET_TIMEOUT = 5  # seconds
MAX_TIMEOUT_COUNT = 5  # after x timeouts, assumes connection lost, disconnect, and restart later
MAX_DREF_COUNT = 80  # Maximum number of dataref that can be requested to X-Plane, CTD around ~100 datarefs

# When this (internal) dataref changes, the loaded aircraft has changed
#
AIRCRAFT_DATAREF_IPC = Dataref.mk_internal_dataref("_aircraft_icao")
DATETIME_DATAREFS = ["sim/time/local_date_days", "sim/time/local_date_sec", "sim/time/zulu_time_sec", "sim/time/use_system_time"]
REPLAY_DATAREFS = ["sim/time/is_in_replay", "sim/time/sim_speed", "sim/time/sim_speed_actual"]


# XPlaneBeacon
# Beacon-specific error classes
class XPlaneIpNotFound(Exception):
    args = "Could not find any running XPlane instance in network."


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
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # SO_REUSEPORT?
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
                        logger.error(f"..X-Plane instance not found on local network.. ({datetime.now().strftime('%H:%M:%S')})")
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
    TERMINATE_QUEUE = "quit"

    def __init__(self, cockpit):
        # list of requested datarefs with index number
        self.datarefidx = 0
        self.datarefs = {}  # key = idx, value = dataref path
        self._max_monitored = 0

        self.udp_queue = Queue()
        self.udp_thread = None
        self.dref_thread = None
        self.no_upd_enqueue = None

        Simulator.__init__(self, cockpit=cockpit)
        self.cockpit.set_logging_level(__name__)

        XPlaneBeacon.__init__(self)
        self.collector = DatarefSetCollector(self)

        self.init()

    def init(self):
        if self._inited:
            return
        dref = Dataref(AIRCRAFT_DATAREF_IPC)
        dref.add_listener(self.cockpit)  # Wow wow wow
        self.register(dref)
        logger.info(f"internal aircraft dataref is {AIRCRAFT_DATAREF_IPC}")
        self.add_datetime_datarefs()
        self._inited = True

    def __del__(self):
        if not self._inited:
            return
        for i in range(len(self.datarefs)):
            self.add_dataref_to_monitor(next(iter(self.datarefs.values())), freq=0)
        self.disconnect()

    def add_datetime_datarefs(self):
        dtdrefs = {}
        for d in DATETIME_DATAREFS:
            dtdrefs[d] = self.get_dataref(d)
        self.add_datarefs_to_monitor(dtdrefs)
        logger.info("monitoring simulator date/time datarefs")

    def datetime(self, zulu: bool = False, system: bool = False) -> datetime:
        """Returns the simulator date and time"""
        if not DATETIME_DATAREFS[0] in self.all_datarefs.keys():  # hack, means dref not created yet
            return super().datetime(zulu=zulu, system=system)
        now = datetime.now().astimezone()
        days = self.get_dataref_value("sim/time/local_date_days")
        secs = self.get_dataref_value("sim/time/local_date_sec")
        if not system and days is not None and secs is not None:
            simnow = datetime(year=now.year, month=1, day=1, hour=0, minute=0, second=0, microsecond=0).astimezone()
            simnow = simnow + timedelta(days=days) + timedelta(days=secs)
            return simnow
        return now

    def get_dataref(self, path):
        if path in self.all_datarefs.keys():
            return self.all_datarefs[path]
        return self.register(Dataref(path))

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
        if command.path is not None:
            message = "CMND0" + command.path
            self.socket.sendto(message.encode(), (self.beacon_data["IP"], self.beacon_data["Port"]))
            logger.log(SPAM_LEVEL, f"execute_command: executed {command}")
        else:
            logger.warning("execute_command: no command")

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
            if freq == 0 and idx in self.datarefs.keys():
                # logger.debug(f">>>>>>>>>>>>>> {path} DELETING INDEX {idx}")
                del self.datarefs[idx]
        else:
            if freq != 0 and len(self.datarefs) > MAX_DREF_COUNT:
                # logger.warning(f"requesting too many datarefs ({len(self.datarefs)})")
                return False

            idx = self.datarefidx
            logger.debug(f">>>>>>>>>>>>>> {path} CREATING AT INDEX {idx}")
            self.datarefs[self.datarefidx] = path
            self.datarefidx += 1

        self._max_monitored = max(self._max_monitored, len(self.datarefs))

        cmd = b"RREF\x00"
        string = path.encode()
        message = struct.pack("<5sii400s", cmd, freq, idx, string)
        assert len(message) == 413
        self.socket.sendto(message, (self.beacon_data["IP"], self.beacon_data["Port"]))
        if self.datarefidx % LOOP_ALIVE == 0:
            time.sleep(0.2)
        return True

    def upd_enqueue(self):
        """Read and decode socket messages and enqueue dataref values

        Terminates after 5 timeouts.
        """
        logger.debug("starting..")
        total_to = 0
        total_reads = 0
        total_values = 0
        last_read_ts = datetime.now()
        total_read_time = 0.0
        while not self.no_upd_enqueue.is_set():
            if len(self.datarefs) > 0:
                try:
                    # Receive packet
                    self.socket.settimeout(SOCKET_TIMEOUT)
                    data, addr = self.socket.recvfrom(1472)  # maximum bytes of an RREF answer X-Plane will send (Ethernet MTU - IP hdr - UDP hdr)
                    # Decode Packet
                    # Read the Header "RREF,".
                    total_to = 0
                    total_reads = total_reads + 1
                    now = datetime.now()
                    delta = now - last_read_ts
                    total_read_time = total_read_time + delta.microseconds / 1000000
                    last_read_ts = now
                    header = data[0:5]
                    if header == b"RREF,":  # (was b"RREFO" for XPlane10)
                        # We get 8 bytes for every dataref sent:
                        # An integer for idx and the float value.
                        values = data[5:]
                        lenvalue = 8
                        numvalues = int(len(values) / lenvalue)
                        total_values = total_values + numvalues
                        for i in range(0, numvalues):
                            singledata = data[(5 + lenvalue * i) : (5 + lenvalue * (i + 1))]
                            (idx, value) = struct.unpack("<if", singledata)
                            self.udp_queue.put((idx, value))
                    else:
                        logger.warning(f"{binascii.hexlify(data)}")
                    if total_reads % 10 == 0:
                        logger.debug(
                            f"average socket time between reads {round(total_read_time / total_reads, 3)} ({total_reads} reads; {total_values} values sent)"
                        )  # ignore
                except:  # socket timeout
                    total_to = total_to + 1
                    logger.info(f"socket timeout received ({total_to}/{MAX_TIMEOUT_COUNT})")  # ignore
                    if total_to >= MAX_TIMEOUT_COUNT:  # attemps to reconnect
                        logger.warning("too many times out, disconnecting, upd_enqueue terminated")  # ignore
                        self.beacon_data = {}
                        if self.no_upd_enqueue is not None and not self.no_upd_enqueue.is_set():
                            self.no_upd_enqueue.set()
        self.no_upd_enqueue = None
        logger.debug("..terminated")

    def dataref_listener(self):
        logger.debug("starting..")
        dequeue_run = True
        total_updates = 0
        total_values = 0
        total_duration = 0.0
        total_update_duration = 0.0
        maxbl = 0

        while dequeue_run:
            values = self.udp_queue.get()
            bl = self.udp_queue.qsize()
            maxbl = max(bl, maxbl)
            if type(values) is str and values == XPlane.TERMINATE_QUEUE:
                dequeue_run = False
                continue
            try:
                before = datetime.now()
                d = self.datarefs.get(values[0])
                total_values = total_values + 1
                value = values[1]
                if value < 0.0 and value > -0.001:  # convert -0.0 values to positive 0.0
                    value = 0.0
                if d is not None:
                    if self.all_datarefs[d].update_value(value, cascade=d in self.datarefs_to_monitor.keys()):
                        total_updates = total_updates + 1
                        duration = datetime.now() - before
                        total_update_duration = total_update_duration + duration.microseconds / 1000000
                else:
                    logger.debug(f"no dataref ({values}), probably no longer monitored")
                duration = datetime.now() - before
                total_duration = total_duration + duration.microseconds / 1000000
                if total_values % LOOP_ALIVE == 0 and total_updates > 0:
                    logger.debug(
                        f"average update time {round(total_update_duration / total_updates, 3)} ({total_updates} updates), {round(total_duration / total_values, 5)} ({total_values} values), backlog {bl}/{maxbl}."
                    )  # ignore

            except RuntimeError:
                logger.warning(f"dataref_listener:", exc_info=True)

        logger.debug("..terminated")

    # ################################
    # X-Plane Interface
    #
    def commandOnce(self, command: Command):
        self.execute_command(command)

    def commandBegin(self, command: Command):
        if command.path is not None:
            self.execute_command(Command(command.path + "/begin"))
        else:
            logger.warning(f"no command")

    def commandEnd(self, command: Command):
        if command.path is not None:
            self.execute_command(Command(command.path + "/end"))
        else:
            logger.warning(f"no command")

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
        logger.debug(f">>>>> monitoring--{len(self.datarefs)}/{self._max_monitored}")

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
        self.collector.enqueue_collections()

    def remove_collections_to_monitor(self, collections):
        # if not self.connected:
        #   logger.warning(f"no connection")
        #   logger.debug(f"would remove collection {collections.keys()} from monitor")
        #   return
        for k, v in collections.items():
            self.collector.remove_collection(v, start=False)
            logger.debug(f"removed collection {k}")
        self.collector.enqueue_collections()

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
            d = self.all_datarefs.get(path)
            if d is not None:
                if self.add_dataref_to_monitor(d.path, freq=d.update_frequency):
                    prnt.append(d.path)
                else:
                    logger.warning(f"no dataref {path}")
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
        if self.no_upd_enqueue is None:
            self.no_upd_enqueue = threading.Event()
            self.udp_thread = threading.Thread(target=self.upd_enqueue)
            self.udp_thread.name = "XPlaneUDP::upd_enqueue"
            self.udp_thread.start()
            logger.info("XPlaneUDP started")
        else:
            logger.info("XPlaneUDP already running.")
        if self.dref_thread is None:
            self.dref_thread = threading.Thread(target=self.dataref_listener)
            self.dref_thread.name = "XPlaneUDP::dataref_listener"
            self.dref_thread.start()
            logger.info("dataref listener started")
        else:
            logger.info("dataref listener running.")
        # When restarted after network failure, should clean all datarefs
        # then reload datarefs from current page of each deck
        self.clean_datarefs_to_monitor()
        self.add_all_datarefs_to_monitor()
        logger.info("reloading pages")
        self.cockpit.reload_pages()  # to take into account updated values

    def stop(self):
        if self.udp_queue is not None and self.dref_thread is not None:
            self.udp_queue.put(XPlane.TERMINATE_QUEUE)
            self.dref_thread.join()
            self.dref_thread = None
            logger.debug("dataref listener stopped")
        if self.no_upd_enqueue is not None:
            self.no_upd_enqueue.set()
            logger.debug("stopping..")
            wait = SOCKET_TIMEOUT
            logger.debug(f"..asked to stop dataref listener (this may last {wait} secs. for UDP socket to timeout)..")
            self.udp_thread.join(wait)
            if self.udp_thread.is_alive():
                logger.warning("..thread may hang in socket.recvfrom()..")
            self.no_upd_enqueue = None
            logger.debug("..stopped")
        else:
            logger.debug("not running")

    # ################################
    # Cockpit interface
    #
    def terminate(self):
        logger.debug(f"currently {'not ' if self.no_upd_enqueue is None else ''}running. terminating..")
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
