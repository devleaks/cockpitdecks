# Class to get dataref values from XPlane Flight Simulator via network. 
# License: GPLv3
import logging
from traceback import print_exc
from datetime import datetime
import re

import xp

from .xplane import XPlane
from .button import Button
from .xpdref import XPDref

logger = logging.getLogger("XPlaneSDK")


DATA_REFRESH = 3.0   # secs, we poll for data every 3 seconds.


class XPlaneSDK(XPlane):
    '''
    Get data from XPlane via direct API calls.
    '''

    def __init__(self, decks):
        XPlane.__init__(self, decks=decks)

        self.defaultFreq = DATA_REFRESH

        self.datarefs = {}          # key = dataref-path, value = Dataref()

    def get_dataref(self, path):
        return XPDref(path)

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
            # logging.debug(f"loop: getting {dataref.path}..")
            self.xplaneValues[dataref.path] = dataref.value
            # logging.debug(f"loop: .. got {dataref.path} = {self.xplaneValues[dataref.path]}.")
        return self.xplaneValues

    def loop(self, elapsedSinceLastCall, elapsedTimeSinceLastFlightLoop, counter, inRefcon):
        while self.running:
            try:
                if len(self.datarefs) > 0:
                    # logging.debug(f"loop: getting values..")
                    self.current_values = self.GetValues()
                    # logging.debug(f"loop: ..done")
                    self.detect_changed()
                else:
                    logging.debug(f"loop: no dataref")
            except:
                logging.error(f"loop: has exception")
                print_exc()
                logging.error(f"loop: stopped scheduling (no more schedule)")
                return 0

            # logging.debug(f"loop: completed at {datetime.now()}")
            return self.defaultFreq  # next iteration in self.defaultFreq seconds
        logging.info(f"loop: stopped scheduling (no more schedule)")
        return 0

    # ################################
    # X-Plane Interface
    #
    def commandOnce(self, command: str):
        cmdref = xp.findCommand(command)
        if cmdref is not None:
            xp.commandOnce(cmdref)
        else:
            logging.warning(f"commandOnce: command {command} not found")

    def commandBegin(self, command: str):
        cmdref = xp.findCommand(command)
        if cmdref is not None:
            xp.commandBegin(cmdref)
        else:
            logging.warning(f"commandBegin: command {command} not found")

    def commandEnd(self, command: str):
        cmdref = xp.findCommand(command)
        if cmdref is not None:
            xp.commandEnd(cmdref)
        else:
            logging.warning(f"XPLMCommandEnd: command {command} not found")

    def set_datarefs(self, datarefs):
        logger.debug(f"set_datarefs: need to set {self.datarefs_to_monitor.keys()}")
        self.datarefs_to_monitor = datarefs
        self.datarefs = {}
        for d in self.datarefs_to_monitor.values():
            if d.exists():
                self.datarefs[d.path] = d
        logger.debug(f"set_datarefs: set {self.datarefs.keys()}")

    # ################################
    # Streamdecks interface
    #
    def start(self):
        if not self.running:
            self.fl = xp.createFlightLoop([xp.FlightLoop_Phase_AfterFlightModel, self.loop, None])
            self.running = True
            xp.scheduleFlightLoop(self.fl, self.defaultFreq, 0)
            logging.debug("start: flight loop started.")
        else:
            logging.debug("start: flight loop running.")

    def terminate(self):
        if self.running:
            self.running = False
            xp.destroyFlightLoop(self.fl)
            logging.debug("stop: flight loop stopped.")
        else:
            logging.debug("stop: flight loop not running.")
