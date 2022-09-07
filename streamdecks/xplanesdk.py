# Class to get dataref values from XPlane Flight Simulator via network. 
# License: GPLv3
import logging
from traceback import print_exc
from datetime import datetime

import sys
sys.path.append('/Users/pierre/Developer/xppythonstubs')
import xp

from .xplane import XPlane
from .button import Button
from .XPDref import XPDref

logger = logging.getLogger("XPlaneSDK")

DATA_REFRESH = 5.0   # secs


class ButtonAnimate(Button):
    """
    """
    def __init__(self, config: dict, deck: "Streamdeck"):
        Button.__init__(self, config=config, deck=deck)
        self.thread = None
        self.running = False
        self.speed = float(self.option_value("animation_speed", 1))
        self.counter = 0  # loop over images
        self.ref = "Streamdecks:button"+self.name+":loop"

    def loop(self):
        try:
            if self.running:
                self.render()
                self.counter = self.counter + 1
        except:
            logging.error(f"loop: has exception ({self.name})")
            print_exc()
            # return 0.0

        return self.sleep

    def get_image(self):
        """
        If button has more icons, select one from button current value
        """
        if self.running:
            self.key_icon = self.multi_icons[self.counter % len(self.multi_icons)]
        else:
            self.key_icon = self.icon  # off
        return super().get_image()

    def activate(self, state: bool):
        super().activate(state)
        if state:
            if self.is_valid():
                # self.label = f"pressed {self.current_value}"
                self.xp.commandOnce(self.command)
                if self.pressed_count % 2 == 0:
                    xp.destroyFlightLoop(self.thread)
                    self.running = False
                    self.render()
                else:
                    self.thread = xp.createFlightLoop([xp.FlightLoop_Phase_AfterFlightModel, self.loop, self.ref])
                    xp.scheduleFlightLoop(self.thread, self.speed, 1)
                    self.running = True


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

    def get_button_animate(self):
        return ButtonAnimate

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
        # try:
        #     if len(self.datarefs) > 0:
        #         self.current_values = self.GetValues()
        #         self.detect_changed()
        # except:
        #     logging.error(f"loop: has exception")
        #     print_exc()
        #     # return 0
        logging.debug(f"loop: completed at {datetime.now()}")

        return DATA_REFRESH  # next iteration in DATA_REFRESH seconds

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

    def get_value(self, dataref: str):
        return self.xplaneValues.get(dataref)

    def set_datarefs(self, datarefs):
        self.datarefs_to_monitor = datarefs
        self.datarefs = {}
        for d in self.datarefs_to_monitor:
            try:
                ref = xp.findDataRef(d)
                if ref is not None:
                    self.datarefs[d] = XPDref(d)
                else:
                    logger.warning(f"set_datarefs: {d} not found")
            except:
                logging.error(f"set_datarefs: has exception ({d})")
                print_exc()

        logger.debug(f"set_datarefs: set {datarefs.keys()}")

    # ################################
    # Streamdecks interface
    #
    def start(self):
        if not self.running:
            self.fl = xp.createFlightLoop([xp.FlightLoop_Phase_AfterFlightModel, self.loop, self.ref])
            # xp.scheduleFlightLoop(self.fl, DATA_REFRESH, 0)
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
