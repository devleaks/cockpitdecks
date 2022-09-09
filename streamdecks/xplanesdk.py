# Class to get dataref values from XPlane Flight Simulator via network. 
# License: GPLv3
import logging
from traceback import print_exc
from datetime import datetime
import re

import sys
sys.path.append('/Users/pierre/Developer/xppythonstubs')
import xp

from .xplane import XPlane
from .button import Button
from .xpdref import XPDref

logger = logging.getLogger("XPlaneSDK")

DATA_REFRESH = 5.0   # secs


class ButtonAnimate(Button):
    """
    """
    def __init__(self, config: dict, page: "Page"):
        Button.__init__(self, config=config, page=page)
        self.thread = None
        self.running = False
        self.speed = float(self.option_value("animation_speed", 1))
        self.counter = 0  # loop over images
        self.ref = "Streamdecks:button"+self.name+":loop"  # could be the same loop for all buttons...

    def loop(self, elapsedSinceLastCall, elapsedTimeSinceLastFlightLoop, counter, inRefcon):
        try:
            if self.running:
                self.render()
                self.counter = self.counter + 1
        except:
            logging.error(f"loop: has exception ({self.name})")
            print_exc()
            return 0.0

        return self.speed

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

        self.defaultFreq = DATA_REFRESH

        self.datarefs = {}
        self.xplaneValues = {}

    def get_button_animate(self):
        return ButtonAnimate

    # ################################
    # Dataref values reading (poll loop)
    #
    def GetValues(self):
        """
        Gets the values from X-Plane for each dataref in self.datarefs.
        """
        self.xplaneValues = {}
        for dataref in self.datarefs.values():
            logging.debug(f"loop: getting {dataref.path}..")
            self.xplaneValues[dataref.path] = dataref.value
            logging.debug(f"loop: .. got {dataref.path} = {self.xplaneValues[dataref.path]}.")
        return self.xplaneValues

    def loop(self, elapsedSinceLastCall, elapsedTimeSinceLastFlightLoop, counter, inRefcon):
        try:
            if len(self.datarefs) > 0:
                logging.debug(f"loop: getting values..")
                self.current_values = self.GetValues()
                logging.debug(f"loop: ..done")
                self.detect_changed()
            else:
                logging.debug(f"loop: no dataref")
        except:
            logging.error(f"loop: has exception")
            print_exc()
            return 0

        logging.debug(f"loop: completed at {datetime.now()}")
        return self.defaultFreq  # next iteration in self.defaultFreq seconds

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
        self.datarefs_to_monitor = datarefs
        self.datarefs = {}
        logger.debug(f"set_datarefs: need to set {self.datarefs_to_monitor.keys()}")
        for d in self.datarefs_to_monitor.values():
            try:
                name = d.dataref
                ref = xp.findDataRef(name)
                if ref is not None:
                    self.datarefs[d.path] = XPDref(d, ref)
                else:
                    logger.warning(f"set_datarefs: {name} not found")
            except:
                logging.error(f"set_datarefs: has exception ({d})")
                print_exc()

        logger.debug(f"set_datarefs: set {self.datarefs.keys()}")

    # ################################
    # Streamdecks interface
    #
    def start(self):
        if not self.running:
            self.fl = xp.createFlightLoop([xp.FlightLoop_Phase_AfterFlightModel, self.loop, None])
            xp.scheduleFlightLoop(self.fl, self.defaultFreq, 0)
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
