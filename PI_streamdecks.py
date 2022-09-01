# Streamdecks XP11 Python3 Plugin Interface
# Streamdecks is a XPPython Plugin to configure and use Elgato Stream Decks in X-Plane
#
#
import xp
from traceback import print_exc

from streamdecks import Streamdecks

RELEASE = "0.0.2"


class PythonInterface:

    def __init__(self):
        self.Name = "Streamdecks"
        self.Sig = "streamdecks.xppython3"
        self.Desc = "Stream Deck Controller. (Rel. " + RELEASE + ")"
        self.enabled = False
        self.trace = True  # produces extra debugging in XPPython3.log for this class
        self.menuIdx = None
        self.streamdecks = None
        self.streamDeckCmdRef = None

    def XPluginStart(self):
        self.streamDeckCmdRef = xp.createCommand('xppython3/streamdecks/reload', 'Reload Stream Decks for aircraft')
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
        if self.streamdecks:
            try:
                self.streamdecks.stop()
                self.streamdecks = None
                if self.trace:
                    print(self.Name, "PI::XPluginStop: stopped.")
            except:
                if self.trace:
                    print(self.Name, "PI::XPluginStop: exception.")
                print_exc()
        return None

    def XPluginEnable(self):
        try:
            self.streamdecks = Streamdecks(self)
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
            if self.enabled and self.streamdecks:
                self.streamdecks.disable()
                self.streamdecks = None

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
        """
        When we receive a message that an aircraft was loaded, if it is the user aircraft,
        we try to load the aicraft esdconfig. If it does not exist, we default to a screen saver.
        """
        if inMessage == xp.MSG_PLANE_LOADED and inParam == 0:  # 0 is for the user aircraft, greater than zero will be for AI aircraft.
            print(self.Name, "PI::XPluginReceiveMessage: user aircraft loaded")
            if self.streamdecks:
                ac = xp.getNthAircraftModel(0)  # ('Cessna_172SP.acf', '/Volumns/SSD1/X-Plane/Aircraft/Laminar Research/Cessna 172SP/Cessna_172SP.acf')
                acpath = os.path.split(ac[1])   # '/Volumns/SSD1/X-Plane/Aircraft/Laminar Research/Cessna 172SP'
                self.streamdecks.load(acpath=acpath)

    def streamDeckCmd(self, *args, **kwargs):
        """
        Command hook to either start or reload current aircraft esdconfig.
        """
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

        if not self.streamdecks:
            try:
                self.streamdecks = Streamdecks(self)
                if self.trace:
                    print(self.Name, "PI::streamDeckCmd: created.")
            except:
                if self.trace:
                    print(self.Name, "PI::streamDeckCmd: exception.")
                print_exc()
                return 0

        if self.streamdecks and commandPhase == 0:
            if self.trace:
                print(self.Name, "PI::streamDeckCmd: available.")
            try:
                self.streamdecks.start()
                if self.trace:
                    print(self.Name, "PI::streamDeckCmd: started.")
                return 1
            except:
                if self.trace:
                    print(self.Name, "PI::streamDeckCmd: exception(2).")
                print_exc()
                return 0
        elif not self.streamdecks:
            print(self.Name, "PI::streamDeckCmd: Error: could not create StreamDeck.")

        return 0
