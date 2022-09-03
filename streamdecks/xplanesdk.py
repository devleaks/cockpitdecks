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
        self.thread = None

    def __del__(self):
        pass

    def WriteDataRef(self, dataref, value, vtype='float'):
        '''
        Write Dataref to XPlane
        DREF0+(4byte byte value)+dref_path+0+spaces to complete the whole message to 509 bytes
        DREF0+(4byte byte value of 1)+ sim/cockpit/switches/anti_ice_surf_heat_left+0+spaces to complete to 509 bytes
        '''
        pass

    def AddDataRef(self, dataref, freq = None):
        '''
        Configure XPlane to send the dataref with a certain frequency.
        You can disable a dataref by setting freq to 0.
        '''
        if dataref not in self.datarefs.keys():
            d = XPDref(dataref)
            if d.dref:
                self.datarefs[dataref] = d
            else:
                logger.debug(f"AddDataRef: {dataref} not found")

    def GetValues(self):
        """
        Gets the values from X-Plane for each dataref in self.datarefs.
        """
        for d in self.datarefs.keys():
            self.xplaneValues[d] = self.datarefs[d].value
        return self.xplaneValues

    def ExecuteCommand(self, command: str):
        cmdref = xp.findCommand(command)
        xp.XPLMCommandOnce(cmdref)
        logger.debug(f"ExecuteCommand: executing {command}")

    def ExecuteBeginCommand(self, command: str):
        cmdref = xp.findCommand(command)
        xp.XPLMCommandBegin(cmdref)
        logger.debug(f"ExecuteBeginCommand: executing {command}")

    def ExecuteEndCommand(self, command: str):
        cmdref = xp.findCommand(command)
        xp.XPLMCommandEnd(cmdref)
        logger.debug(f"ExecuteEndCommand: executing {command}")

    def startFlightLoop(self):
        phase = xp.FlightLoop_Phase_AfterFlightModel
        if not self.running:
            params = [phase, self.get_values, self.ref]
            self.fl = xp.createFlightLoop(params)
            xp.scheduleFlightLoop(self.fl, DATA_REFRESH, 1)
            self.running = True
            logging.debug("startFlightLoop: started.")
        else:
            logging.debug("startFlightLoop: running.")

    def stopFlightLoop(self):
        if self.running:
            xp.destroyFlightLoop(self.fl)
            self.running = False
            logging.debug("stopFlightLoop: stopped.")
        else:
            logging.debug("stopFlightLoop: not running.")

    def get_values(self):
        dummy = self.GetValues()
        return DATA_REFRESH