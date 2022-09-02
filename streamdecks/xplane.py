import threading
import logging
import time

from .xplaneudp import XPlaneUdp, XPlaneVersionNotSupported, XPlaneIpNotFound
from .xplaneapi import XPlaneApi

logger = logging.getLogger("Xplane")


DATA_REFRESH = 0.1 # secs
DATA_SENT    = 10  # times per second


class XPlane:
    """
    Abstract class for execution of operations in X-Plane
    """
    def __init__(self, decks):
        self.decks = decks
        self.running = False
        self.previous_values = {}
        self.current_values = {}

    def start(self):
        self.thread = threading.Thread(target=self.get_values)
        self.running = True
        self.thread.start()

    def get_values(self):
        logger.debug(f"get_values: started")
        while self.running:
            self.current_values = self.xp.GetValues()
            now = time.time()
            self.notify_changed()
            later = time.time()
            nexttime = DATA_REFRESH - (later - now)
            if nexttime > 0:
                time.sleep(nexttime)
        if self.finished is not None:
            self.finished.set()
            logger.debug(f"get_values: allowed deletion")
        logger.debug(f"get_values: terminated")

    def notify_changed(self):
        for d in self.current_values.keys():
            if d not in self.previous_values.keys() or self.current_values[d] != self.previous_values[d]:
                for deck in self.decks.decks.values():
                    if d in deck.current_page.datarefs.keys():  # do we need to update a button currently displayed?
                        deck.current_page.update_dataref(d)
        self.previous_values = self.current_values.copy()

    def terminate(self):
        self.finished = threading.Event()
        self.running = False
        logger.debug(f"terminate: wait permission to delete")
        self.finished.wait(timeout=10)
        del self.xp
        logger.debug(f"terminate: XPlaneUDP terminated")


    # X-Plane Interface
    #
    #
    def commandOnce(self, command: str):
        self.xp.ExecuteCommand(command)
        logger.debug(f"commandOnce: executed {command}")

    def commandBegin(self, command: str):
        pass

    def commandContinue(self, command: str):
        # cmdref = xp.findCommand(command)
        # xp.XPLMCommandBegin(cmdref)
        logger.debug(f"commandContinue: executing {command}")

    def commandEnd(self, command: str):
        pass

    def read(self, dataref: str):
        return None


class XPlaneAPI(XPlane):
    """
    Perform requested operations through XPPython X-Plane API calls
    """
    def __init__(self, decks):
        XPlane.__init__(self, decks=decks)

        self.xp = XPlaneApi()

        self.start()

    # X-Plane Interface
    #
    #
    def commandBegin(self, command: str):
        self.xp.ExecuteBeginCommand(command)
        logger.debug(f"commandBegin: executing {command}")

    def commandContinue(self, command: str):
        # cmdref = xp.findCommand(command)
        # xp.XPLMCommandBegin(cmdref)
        logger.debug(f"commandBegin: executing {command}")

    def commandEnd(self, command: str):
        self.xp.ExecuteEndCommand(command)
        logger.debug(f"commandEnd: executing {command}")

    def read(self, dataref: str):
        if dataref not in self.current_values:
            self.xp.AddDataRef(dataref)
            self.current_values = self.xp.GetValues()
        logger.debug(f"read: got {dataref}={self.current_values.get(dataref)}")
        return self.current_values.get(dataref)


class XPlaneUDP(XPlane):
    """
    Perform requested operations through UDP send/receive
    """
    def __init__(self, decks, config=None):
        XPlane.__init__(self, decks=decks)

        self.config = config
        self.xp = XPlaneUdp()

        try:
            beacon = self.xp.FindIp()
            logger.info(beacon)
        except XPlaneVersionNotSupported:
            logger.error("XPlane Version not supported.")
        except XPlaneIpNotFound:
            logger.error("XPlane IP not found. Probably there is no XPlane running in your local network.")

        self.start()

    # X-Plane Interface
    #
    #
    def commandOnce(self, command: str):
        self.xp.ExecuteCommand(command)
        logger.debug(f"commandOnce: executed {command}")

    def commandBegin(self, command: str):
        self.xp.ExecuteCommand(command+"/begin")
        logger.debug(f"commandBegin: executing {command}")

    def commandContinue(self, command: str):
        # cmdref = xp.findCommand(command)
        # xp.XPLMCommandBegin(cmdref)
        logger.debug(f"commandBegin: executing {command}")

    def commandEnd(self, command: str):
        self.xp.ExecuteCommand(command+"/end")
        logger.debug(f"commandEnd: executing {command}")

    def read(self, dataref: str):
        if dataref not in self.current_values:
            self.xp.AddDataRef(dataref, freq=DATA_SENT)
            self.current_values = self.xp.GetValues()
        logger.debug(f"read: got {dataref}={self.current_values.get(dataref)}")
        return self.current_values.get(dataref)
