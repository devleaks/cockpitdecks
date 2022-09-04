# Class to get dataref values from XPlane Flight Simulator via network. 
# License: GPLv3
import logging

import sys
sys.path.append('/Users/pierre/Developer/xppythonstubs')
import xp

from .xplane import XPlane
from .XPDref import XPDref

logger = logging.getLogger("XPlaneSDK")

DATA_REFRESH = 5   # secs


class XPlaneSDK(XPlane):
    '''
    Get data from XPlane via direct API calls.
    '''

    def __init__(self, decks):
        XPlane.__init__(self, decks=decks)

        self.datarefs = {} # key = idx, value = dataref
        # values from xplane
        self.xplaneValues = {}
        self.defaultFreq = 1
        self.ref = "Streamdecks:loop"

    def __del__(self):
        pass

    def WriteDataRef(self, dataref, value, vtype='float'):
        '''
        Write Dataref to XPlane
        DREF0+(4byte byte value)+dref_path+0+spaces to complete the whole message to 509 bytes
        DREF0+(4byte byte value of 1)+ sim/cockpit/switches/anti_ice_surf_heat_left+0+spaces to complete to 509 bytes
        '''
        pass

    def GetValues(self):
        """
        Gets the values from X-Plane for each dataref in self.datarefs.
        """
        for d in self.datarefs.keys():
            self.xplaneValues[d] = self.datarefs[d].value
        return self.xplaneValues

    def loop(self):
        if len(self.datarefs) > 0:
            self.current_values = self.GetValues()
            self.detect_changed()
        return DATA_REFRESH  # next iteration in DATA_REFRESH seconds

    # ################################
    # X-Plane Interface
    #
    def commandOnce(self, command: str):
        cmdref = xp.findCommand(command)
        if cmdref is not None:
            xp.XPLMCommandOnce(cmdref)
        else:
            logging.warning(f"commandOnce: command {command} not found")

    def commandBegin(self, command: str):
        cmdref = xp.findCommand(command)
        if cmdref is not None:
            xp.XPLMCommandBegin(cmdref)
        else:
            logging.warning(f"commandBegin: command {command} not found")

    def commandEnd(self, command: str):
        cmdref = xp.findCommand(command)
        if cmdref is not None:
            xp.XPLMCommandEnd(cmdref)
        else:
            logging.warning(f"XPLMCommandEnd: command {command} not found")

    def get_value(self, dataref: str):
        return self.xplaneValues.get(dataref)

    def set_datarefs(self, datarefs):
        self.datarefs_to_monitor = datarefs
        self.datarefs = {}
        for d in self.datarefs_to_monitor:
            ref = xp.findDataRef(d)
            if ref is not None:
                self.datarefs[d] = XPDref(d)
            else:
                logger.warning(f"set_datarefs: {d} not found")
        logger.debug(f"set_datarefs: set {datarefs.keys()}")

    # ################################
    # Streamdecks interface
    #
    def start(self):
        phase = xp.FlightLoop_Phase_AfterFlightModel
        if not self.running:
            params = [phase, self.loop, self.ref]
            self.fl = xp.createFlightLoop(params)
            xp.scheduleFlightLoop(self.fl, DATA_REFRESH, 1)
            self.running = True
            logging.debug("start: flight loop started.")
        else:
            logging.debug("start: flight loop running.")

    def terminate(self):
        if self.running:
            xp.destroyFlightLoop(self.fl)
            self.running = False
            logging.debug("stop: flight loop stopped.")
        else:
            logging.debug("stop: flight loop not running.")
