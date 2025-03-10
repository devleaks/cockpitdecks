# Python Plugin To Save Toliss Situations on request.
# Enjoy.
#
import os
import glob
import time
from datetime import datetime

import xp

TIME_COMMAND = "xppython3/use_system_time_toggle"
TIME_COMMAND_DESC = "Toggle use system time"
TIME_DREF = "sim/time/use_system_time"

# ###########################################################
# S A V E   T O L I S S   S I T U A T I O N
#
PLUGIN_VERSION = "1.0.1"
#
# Changelog:
#
# 30-SEP-2024: 1.0.1: Minimized widget window to left side of time
# 03-SEP-2024: 1.0.0: Initial version, port from FWL script (I made)
#
TIME_DREFS = {
    "lh": "sim/cockpit2/clock_timer/local_time_hours",
    "lm": "sim/cockpit2/clock_timer/local_time_minutes",
    "ls": "sim/cockpit2/clock_timer/local_time_seconds",
    "zh": "sim/cockpit2/clock_timer/zulu_time_hours",
    "zm": "sim/cockpit2/clock_timer/zulu_time_minutes",
    "zs": "sim/cockpit2/clock_timer/zulu_time_seconds",
}


class PythonInterface:
    def __init__(self):
        self.Name = "Time of Day"
        self.Sig = "xppython3.timeofday"
        self.Desc = TIME_COMMAND_DESC + " (Rel. " + PLUGIN_VERSION + ")"
        self.Info = self.Name + f" (rel. {PLUGIN_VERSION})"
        self.enabled = False
        self.trace = True  # produces extra debugging in XPPython3.log for this class
        self.useSystemTimeCmdRef = None
        self.systemTimeDref = None
        self.color = (1.0, 1.0, 1.0)
        self.clockDrefs = {}
        self.widgetID = None

    def XPluginStart(self):
        if self.trace:
            print(self.Info, "XPluginStart: starting..")

        self.useSystemTimeCmdRef = xp.createCommand(TIME_COMMAND, TIME_COMMAND_DESC)
        xp.registerCommandHandler(self.useSystemTimeCmdRef, self.useSystemTime, 1, None)

        self.systemTimeDref = xp.findDataRef(TIME_DREF)
        if self.systemTimeDref is not None:
            curr = xp.getDatai(self.systemTimeDref)
            self.color = (0.0, 1.0, 0.0) if curr == 1 else (1.0, 0.0, 0.0)
            if self.trace:
                print(self.Info, f"load: added string dataref {TIME_DREF}, value={curr}")
        else:
            print(self.Info, f"load: dataref {TIME_DREF} not found")

        self.clockDrefs = {k: xp.findDataRef(v) for k, v in TIME_DREFS.items()}

        print(self.Info, "XPluginStart: ..started.")
        return self.Name, self.Sig, self.Desc

    def callback(self, message, widgetID, param1, param2):
        if message == xp.Msg_MouseDown:
            curr = xp.getDatai(self.systemTimeDref)
            nextval = 0 if curr == 1 else 1
            xp.setDatai(self.systemTimeDref, nextval)
            self.color = (0.0, 1.0, 0.0) if nextval == 1 else (1.0, 0.0, 0.0)
            # print(self.Info, "clicked", param1, "now", nextval)
        return 0

    def XPluginStop(self):
        if self.trace:
            print(self.Info, "XPluginStop: stopping..")

        if self.useSystemTimeCmdRef:
            xp.unregisterCommandHandler(self.useSystemTimeCmdRef, self.useSystemTime, 1, None)
            self.useSystemTimeCmdRef = None

        print(self.Info, "XPluginStop: ..stopped.")
        return None

    def XPluginEnable(self):
        if self.systemTimeDref is not None:
            curr = xp.getDatai(self.systemTimeDref)
            self.color = (0.0, 1.0, 0.0) if curr == 1 else (1.0, 0.0, 0.0)
        # self.widgetID = xp.createWidget(15, 60, 90, 45, 1, "", 1, 0, xp.WidgetClass_MainWindow)
        self.widgetID = xp.createWidget(5, 58, 15, 18, 1, "", 1, 0, xp.WidgetClass_MainWindow)
        xp.setWidgetProperty(self.widgetID, xp.Property_MainWindowType, xp.MainWindowStyle_Translucent)
        xp.addWidgetCallback(self.widgetID, self.callback)
        xp.registerDrawCallback(self.show_time)
        self.enabled = True
        return 1

    def XPluginDisable(self):
        xp.unregisterDrawCallback(self.show_time)
        if self.widgetID:
            xp.destroyWidget(self.widgetID, 1)
            self.widgetID = None
        self.enabled = False
        return None

    def XPluginReceiveMessage(self, inFromWho, inMessage, inParam):
        pass

    def show_time(self, phase, after, refCon):
        xloc = 20
        yloc = 20
        str = ""
        xp.setGraphicsState(0, 1, 0, 0, 0, 0, 0)
        xp.drawString(self.color, xloc - 3, yloc + 30, "TIME OF DAY")
        dt = {k: xp.getDatai(v) for k, v in self.clockDrefs.items()}
        lt = f"{dt['lh']:02d}:{dt['lm']:02d}:{dt['ls']:02d}"
        xp.drawString((1.0, 1.0, 0.0), xloc + 5, yloc + 15, lt)
        zt = f"{dt['zh']:02d}:{dt['zm']:02d}:{dt['zs']:02d}"
        xp.drawString((1.0, 0.8, 0.0), xloc + 5, yloc, zt)

    def useSystemTime(self, *args, **kwargs):
        # pylint: disable=unused-argument
        if not self.enabled:
            print(self.Info, "useSystemTime: not enabled.")
            return 0

        command_phase = 0
        if len(args) > 2:
            command_phase = args[1]
            if self.trace:
                print(self.Info, "useSystemTime: command phase", command_phase)
        else:
            print(self.Info, "useSystemTime: no command phase", len(args))

        if command_phase == 0:
            try:
                curr = xp.getDatai(self.systemTimeDref)
                nextval = 0 if curr == 1 else 1
                self.color = (0.0, 1.0, 0.0) if nextval == 1 else (1.0, 0.0, 0.0)
                xp.setDatai(self.systemTimeDref, nextval)
                return 1
            except:
                print(self.Info, "useSystemTime: exception")
                print_exc()

        return 0
