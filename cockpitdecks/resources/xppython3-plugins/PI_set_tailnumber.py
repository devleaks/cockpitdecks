# Attempts to locate a file named tailnum.txt in the livery folder;
# File should only contain the tail number of that aircraft.
# If found, will set the tail number.
# Otherwise, set the default tail number hardcoded in this file.
#
# Enjoy.
#
import os
import xp
from traceback import print_exc

PLUGIN_VERSION = "1.0.0"

# ###########################################################
# S E T   T A I L   N U M B E R
#
RELEASE = "1.0.1"  # local version number
#
# Changelog:
#
# 26-SEP-2024: 1.0.1: getDatas returns error if count=-1
# 03-SEP-2024: 1.0.0: Initial version

TAIL_NUMBER = "OO-PMA"
LIVERY_DATAREF = "sim/aircraft/view/acf_livery_path"
TAILNUM_DATAREF = "sim/aircraft/view/acf_tailnum"


class PythonInterface:
    def __init__(self):
        self.Name = "Set Tail Number"
        self.Sig = "xppython3.settailnum"
        self.Desc = self.Name + f" (Rel. {PLUGIN_VERSION})"
        self.Info = self.Name + f" (rel. {PLUGIN_VERSION})"
        self.enabled = False
        self.trace = True  # produces extra debugging in XPPython3.log for this class

    def XPluginStart(self):
        if self.trace:
            print(self.Info, "XPluginStart: starting..")
        print(self.Info, "XPluginStart: ..started.")
        return self.Name, self.Sig, self.Desc

    def XPluginStop(self):
        if self.trace:
            print(self.Info, "XPluginStop: stopping..")

        print(self.Info, "XPluginStop: ..stopped.")
        return None

    def XPluginEnable(self):
        self.enabled = True
        self.set_tail_number("")
        return 1

    def XPluginDisable(self):
        self.enabled = False
        return None

    def XPluginReceiveMessage(self, inFromWho, inMessage, inParam):
        """
        When we receive a message that an aircraft was loaded, if it is the user aircraft,
        we try to load the aicraft deskconfig.
        If it does not exist, we default to a screen saver type of screen for the deck.
        """
        if inMessage == xp.MSG_PLANE_LOADED and inParam == 0:  # 0 is for the user aircraft, greater than zero will be for AI aircraft.
            print(self.Info, "XPluginReceiveMessage: user aircraft received")
            try:
                ac = xp.getNthAircraftModel(0)  # ('Cessna_172SP.acf', '/Volumns/SSD1/X-Plane/Aircraft/Laminar Research/Cessna 172SP/Cessna_172SP.acf')
                if len(ac) == 2:
                    acpath = os.path.split(ac[1])  # ('/Volumns/SSD1/X-Plane/Aircraft/Laminar Research/Cessna 172SP', 'Cessna_172SP.acf')
                    if self.trace:
                        print(
                            self.Info,
                            "XPluginReceiveMessage: trying " + acpath[0] + "..",
                        )
                    self.set_tail_number(acpath=acpath[0])
                    if self.trace:
                        print(
                            self.Info,
                            "XPluginReceiveMessage: .. " + acpath[0] + " done.",
                        )
                    return None
                print(
                    self.Info,
                    "XPluginReceiveMessage: getNthAircraftModel: aircraft not found.",
                )
            except:
                if self.trace:
                    print(self.Info, "XPluginReceiveMessage: exception.")
                print_exc()
                self.enabled = False
        return None

    def set_tail_number(self, acpath):
        # pylint: disable=unused-argument
        if not self.enabled:
            print(self.Info, "set_tail_number: not enabled.")
            return 0

        dref = xp.findDataRef(LIVERY_DATAREF)
        if dref is not None:
            livery = xp.getDatas(dref, count=100)  # count=-1 gets error
            fn = os.path.join(livery, "tailnum.txt")
            reg = TAIL_NUMBER
            if os.path.exists(fn):
                with open(fn, "r") as fp:
                    reg = fp.read()
                print(self.Info, f"set_tail_number: tail number {reg} found in {fn}.")
                reg = reg.strip()
            else:
                print(self.Info, f"set_tail_number: file not found {fn}, using default tail number {TAIL_NUMBER}.")

            dref = xp.findDataRef(TAILNUM_DATAREF)
            if dref is not None:
                xp.setDatas(dref, TAIL_NUMBER)
                print(self.Info, f"set_tail_number: {acpath}, {livery}: set to {reg}.")
            else:
                print(self.Info, f"set_tail_number: {TAILNUM_DATAREF} dataref not found")
        else:
            print(self.Info, f"set_tail_number: {LIVERY_DATAREF} dataref not found")

        return 0
