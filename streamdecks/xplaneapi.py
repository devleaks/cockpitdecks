# Class to get dataref values from XPlane Flight Simulator via network. 
# License: GPLv3
import logging

import sys
sys.path.append('/Users/pierre/Developer/xppythonstubs')
import xp

from .XPDref import XPDref

logger = logging.getLogger("XPlaneApi")


class XPlaneApi:
    '''
    Get data from XPlane via direct API calls.
    '''

    def __init__(self):
        self.datarefs = {} # key = idx, value = dataref
        # values from xplane
        self.xplaneValues = {}
        self.defaultFreq = 1

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
            self.datarefs[dataref] = freq


    def GetValues(self):
        """
        Gets the values from X-Plane for each dataref in self.datarefs.
        """
        try:
            pass
        except:
            raise XPlaneTimeout
        return self.xplaneValues

    def ExecuteCommand(self, command: str):
        message = 'CMND0' + command
        self.socket.sendto(message.encode("ascii"), (self.BeaconData["IP"], self.BeaconData["Port"]))

    def commandOnce(self, command: str):
        cmdref = xp.findCommand(command)
        xp.XPLMCommandOnce(cmdref)
        logger.debug(f"commandOnce: executed {command}")

    def commandBegin(self, command: str):
        cmdref = xp.findCommand(command)
        xp.XPLMCommandBegin(cmdref)
        logger.debug(f"commandBegin: executing {command}")

    def commandEnd(self, command: str):
        cmdref = xp.findCommand(command)
        xp.XPLMCommandEnd(cmdref)
        logger.debug(f"commandEnd: executing {command}")

    def read(self, dataref: str):
        return XPDref(dataref)
