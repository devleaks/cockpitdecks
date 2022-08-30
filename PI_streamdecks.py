# Stream Deck XP11 Python3 Plugin Interface
#
from traceback import print_exc
import xp
from streamdeck import Streamdecks

RELEASE = "0.0.1"

class PythonInterface:

    def __init__(self):
        self.Name = "Stream Deck"
        self.Sig = "streamdeck.xppython3"
        self.Desc = "Stream Deck Controller. (Rel. " + RELEASE + ")"
        self.enabled = False
        self.trace = True  # produces extra debugging in XPPython3.log for this class
        self.menuIdx = None
        self.streamdeck = None
        self.streamDeckCmdRef = None

    def XPluginStart(self):
        self.streamDeckCmdRef = xp.createCommand('xppython3/streamdeck/toggle', 'Open or close Stream Deck Controller window')
        xp.registerCommandHandler(self.streamDeckCmdRef, self.streamDeckCmd, 1, None)
        self.menuIdx = xp.appendMenuItemWithCommand(xp.findPluginsMenu(), self.Name, self.streamDeckCmdRef)
        if self.trace:
            print(self.Name, "PI::XPluginStop: menu added.")
        if self.trace:
            print(self.Name, "PI::XPluginStart: started.")
        return self.Name, self.Sig, self.Desc

    def XPluginStop(self):
        if self.streamDeckCmdRef:
            xp.unregisterCommandHandler(self.streamDeckCmdRef,
                                        self.streamDeckCmd,
                                        1, None)
            self.streamDeckCmdRef = None
        if self.menuIdx:
            xp.removeMenuItem(xp.findPluginsMenu(), self.menuIdx)
            self.menuIdx = None
            if self.trace:
                print(self.Name, "PI::XPluginStop: menu removed.")
        if self.streamdeck:
            try:
                self.streamdeck.stop()
                self.streamdeck = None
                if self.trace:
                    print(self.Name, "PI::XPluginStop: stopped.")
            except:
                if self.trace:
                    print(self.Name, "PI::XPluginStop: exception.")
                print_exc()
        return None

    def XPluginEnable(self):
        try:
            self.streamdeck = Streamdecks(self)
            self.enabled = True
            if self.trace:
                print(self.Name, "PI::XPluginEnable: enabled.")
            return 1
        except:
            if self.trace:
                print(self.Name, "PI::XPluginEnable: exception.")
            print_exc()
        return 0

    def XPluginDisable(self):
        try:
            if self.enabled and self.streamdeck:
                self.streamdeck.disable()
                self.streamdeck = None

            self.enabled = False
            if self.trace:
                print(self.Name, "PI::XPluginDisable: disabled.")
            return None
        except:
            if self.trace:
                print(self.Name, "PI::XPluginDisable: exception.")
            print_exc()
            self.enabled = False
            return None
        self.enabled = False
        return None

    def XPluginReceiveMessage(self, inFromWho, inMessage, inParam):
        pass


    def streamDeckCmd(self, *args, **kwargs):
        # pylint: disable=unused-argument
        if not self.enabled:
            print(self.Name, "PI::streamDeckCmd: not enabled.")
            return 0

        # When mapped on a keystroke, StreamDeck only starts on begin of command (phase=0).
        # Phase=1 (continuous press) and phase=2 (release key) are ignored.
        # If phase not found, report it in log and assume phase=0 (i.e. work will be done.)
        commandPhase = 0
        if len(args) > 2:
            commandPhase = args[1]
            if self.trace:
                print(self.Name, "PI::streamDeckCmd: COMMAND PHASE", commandPhase)
        else:
            print(self.Name, "PI::streamDeckCmd: NO COMMAND PHASE", len(args))

        if not self.streamdeck:
            try:
                self.streamdeck = Streamdecks(self)
                if self.trace:
                    print(self.Name, "PI::streamDeckCmd: created.")
            except:
                if self.trace:
                    print(self.Name, "PI::streamDeckCmd: exception.")
                print_exc()
                return 0

        if self.streamdeck and commandPhase == 0:
            if self.trace:
                print(self.Name, "PI::streamDeckCmd: available.")
            try:
                self.streamdeck.start()
                if self.trace:
                    print(self.Name, "PI::streamDeckCmd: started.")
                return 1
            except:
                if self.trace:
                    print(self.Name, "PI::streamDeckCmd: exception(2).")
                print_exc()
                return 0
        elif not self.streamdeck:
            print(self.Name, "PI::streamDeckCmd: Error: could not create StreamDeck.")

        return 0
