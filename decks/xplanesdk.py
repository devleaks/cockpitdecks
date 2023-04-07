# Class for interface with X-Plane using X-Plane SDK
# To be used when run as a XPPython3 plugin.
#
import logging
from datetime import datetime
from queue import Queue, Empty
import re

import xp

from .xplane import XPlane
from .button import Button
from .xpdref import XPDref

logger = logging.getLogger("XPlaneSDK")
# logger.setLevel(logging.DEBUG)

class XPlaneSDK(XPlane):
    '''
    Get data from XPlane via direct API calls.
    '''

    def __init__(self, decks):
        XPlane.__init__(self, decks=decks)
        self.use_flight_loop = True

        self.events = Queue()

        self.drflref = None
        self.procflref = None

        self.drflfreq = 1.0
        self.procflfreq = 0.5

        self.datarefs = {}          # key = dataref-path, value = Dataref()

    @property
    def connected(self):
        return True

    def get_dataref(self, path):
        if path in self.all_datarefs.keys():
            return self.all_datarefs[path]
        return self.register(XPDref(path))

    # ################################
    # Dataref values reading (poll loop)
    #
    def GetValues(self):
        """
        Gets the values from X-Plane for each dataref in self.datarefs.
        Only returns {dataref-name: value} dict.
        """
        self.xplaneValues = {}
        for dataref in self.datarefs.values():
            # logger.debug(f"GetValues: getting {dataref.path}.")
            self.xplaneValues[dataref.path] = dataref.value
            # logger.debug(f"GetValues: .. got {dataref.path} = {self.xplaneValues[dataref.path]}")
        return self.xplaneValues

    def dataref_fl(self, elapsedSinceLastCall, elapsedTimeSinceLastFlightLoop, counter, inRefcon):
        if not self.running:
            logger.info(f"dataref_fl: stopped scheduling (no more schedule)")
            return 0

        try:
            if len(self.datarefs) > 0:
                # logger.debug(f"dataref_fl: getting values..")
                self.current_values = self.GetValues()
                # logger.debug(f"dataref_fl: ..done")
                self.detect_changed()
            else:
                logger.debug(f"dataref_fl: no dataref")
        except:
            logger.error(f"dataref_fl: exception:", exc_info=1)
            logger.error(f"dataref_fl: stopped scheduling (no more schedule)")
            return 0

        # logger.debug(f"dataref_fl: completed at {datetime.now()}")
        return self.drflfreq  # next iteration in self.drflfreq seconds

    def processing_fl(self, elapsedSinceLastCall, elapsedTimeSinceLastFlightLoop, counter, inRefcon):
        if not self.running:
            logger.info(f"processing_fl: stopped scheduling (no more schedule)")
            return 0

        while not self.events.empty():
            e = self.events.get()
            # logger.debug(f"processing_fl: processing {e}")
            try:
                deck = self.cockpit.cockpit[e[0]]
                deck.key_change_processing(deck.device, e[1], e[2])
            except:
                logger.error(f"processing_fl: exception:", exc_info=1)
                logger.error(f"processing_fl: continuing")

        # logger.debug(f"processing_fl: completed at {datetime.now()}")
        return self.procflfreq

    # ################################
    # X-Plane Interface
    #
    def commandOnce(self, command: str):
        cmdref = xp.findCommand(command)
        if cmdref is not None:
            xp.commandOnce(cmdref)
        else:
            logger.warning(f"commandOnce: command {command} not found")

    def commandBegin(self, command: str):
        cmdref = xp.findCommand(command)
        if cmdref is not None:
            xp.commandBegin(cmdref)
        else:
            logger.warning(f"commandBegin: command {command} not found")

    def commandEnd(self, command: str):
        cmdref = xp.findCommand(command)
        if cmdref is not None:
            xp.commandEnd(cmdref)
        else:
            logger.warning(f"XPLMCommandEnd: command {command} not found")

    def clean_datarefs_to_monitor(self):
        self.datarefs = {}
        super().clean_datarefs_to_monitor()
        logger.debug(f"clean_datarefs_to_monitor: done")

    def add_datarefs_to_monitor(self, datarefs):
        super().add_datarefs_to_monitor(datarefs)
        for d in datarefs.values():
            if d.exists():
                self.datarefs[d.path] = d
        logger.debug(f"add_datarefs_to_monitor: added {self.datarefs.keys()}")

    def remove_datarefs_to_monitor(self, datarefs):
        for d in datarefs.values():
            if d.path in self.datarefs:
                del self.datarefs[d.path]
        super().remove_datarefs_to_monitor(datarefs)
        logger.debug(f"remove_datarefs_to_monitor: removed {self.datarefs.keys()}")

    # ################################
    # Cockpit interface
    #
    def start(self):
        if not self.running:
            self.running = True
            self.drflref = xp.createFlightLoop([xp.FlightLoop_Phase_AfterFlightModel, self.dataref_fl, None])
            xp.scheduleFlightLoop(self.drflref, self.drflfreq, 0)
            self.procflref = xp.createFlightLoop([xp.FlightLoop_Phase_AfterFlightModel, self.processing_fl, None])
            xp.scheduleFlightLoop(self.procflref, self.procflfreq, 0)
            logger.debug("start: flight loops started")
        else:
            logger.debug("start: flight loops running")

    def terminate(self):
        if self.running:
            self.running = False
            xp.destroyFlightLoop(self.drflref)
            xp.destroyFlightLoop(self.procflref)
            logger.debug("stop: flight loops stopped")
        else:
            logger.debug("stop: flight loops not running")
