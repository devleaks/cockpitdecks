# Python Plugin To Save Toliss Situations on request.
# Enjoy.
#
import xp

PLUGIN_VERSION = "1.0.0"

# ###########################################################
# S E T   R E G I S T R A T I O N
#
RELEASE = "1.0.0"  # local version number
#
# Changelog:
#
# 03-SEP-2024: 1.0.0: Initial version

TAIL_NUMBER = "OO-PMA"
TAILNUM_DATAREF = "sim/aircraft/view/acf_tailnum"

class PythonInterface:
    def __init__(self):
        self.Name = "Ste Tail Number"
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
        self.set_tail_number()
        return 1

    def XPluginDisable(self):
        self.enabled = False
        return None

    def XPluginReceiveMessage(self, inFromWho, inMessage, inParam):
        pass

    def set_tail_number(self):
        # pylint: disable=unused-argument
        if not self.enabled:
            print(self.Info, "setTailNumber:not enabled.")
            return 0

        dref = xp.findDataRef(TAILNUM_DATAREF)
        if dref is not None:
            xp.setDatas(dref, TAIL_NUMBER)
            print(self.Info, f"setTailNumber:set to {TAIL_NUMBER}.")

        return 0
