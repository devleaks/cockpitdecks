# Cockpit Python3 Plugin Interface
# Cockpit is a XPPython Plugin to configure and use Elgato Stream Decks, Loupedeck LoupedeckLive, and Behringer X-Touch Mini in X-Plane
#
import logging
import os
import xp
from traceback import print_exc

# we prepend our own implementation of StreamDeck package
# with a flightloop rather than a threading.Thread + time.sleep.
# import sys
# sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib", "StreamDeck"))


from decks import Cockpit, __version__ as RELEASE
from decks.xplanesdk import XPlaneSDK

logging.basicConfig(level=logging.DEBUG, filename="decks.log", filemode='a')


class PythonInterface:

    def __init__(self):
        self.Name = "Cockpitdecks"
        self.Sig = "cockpitdecks.xppython3"
        self.Desc = "Elgato Stream Deck, Loupedeck LoupedeckLive, and X-Touch Mini controllers for X-Plane (Rel. " + RELEASE + ")"
        self.enabled = False
        self.trace = True  # produces extra debugging in XPPython3.log for this class
        self.menuIdx = None
        self.decks = None
        self.cockpitCmdRef = None

    def XPluginStart(self):
        self.cockpitCmdRef = xp.createCommand('xppython3/decks/reload', 'Reload decks for aircraft')
        xp.registerCommandHandler(self.cockpitCmdRef, self.cockpitCmd, 1, None)
        if self.trace:
            print(self.Name, "PI::XPluginStart: command added.")
        self.menuIdx = xp.appendMenuItemWithCommand(xp.findPluginsMenu(), self.Name, self.cockpitCmdRef)
        if self.menuIdx > -1:
            xp.checkMenuItem(xp.findPluginsMenu(), self.menuIdx, xp.Menu_Unchecked)
            if self.trace:
                print(self.Name, "PI::XPluginStart: menu added.")
        else:
            print(self.Name, "PI::XPluginStart: menu not added.")
        if self.trace:
            print(self.Name, "PI::XPluginStart: started.")
        return self.Name, self.Sig, self.Desc

    def XPluginStop(self):
        if self.menuIdx:
            xp.removeMenuItem(xp.findPluginsMenu(), self.menuIdx)
            self.menuIdx = None
            if self.trace:
                print(self.Name, "PI::XPluginStop: menu removed.")
        if self.cockpitCmdRef:
            xp.unregisterCommandHandler(self.cockpitCmdRef,
                                        self.cockpitCmd,
                                        1, None)
            self.cockpitCmdRef = None
            if self.trace:
                print(self.Name, "PI::XPluginStop: command removed.")
        if self.decks:
            try:
                self.decks.stop()
                self.decks = None
                if self.trace:
                    print(self.Name, "PI::XPluginStop: stopped.")
            except:
                if self.trace:
                    print(self.Name, "PI::XPluginStop: exception.")
                print_exc()
        return None

    def XPluginEnable(self):
        try:
            if self.decks is None:
                self.decks = Cockpit(XPlaneSDK)
            if self.loadCurrentAircraft():
                self.enabled = True
                xp.checkMenuItem(xp.findPluginsMenu(), self.menuIdx, xp.Menu_Checked)
                if self.trace:
                    print(self.Name, "PI::XPluginEnable: enabled.")
                return 1
            else:
                print(self.Name, "PI::XPluginEnable: aircraft not loaded.", ac)
        except:
            if self.trace:
                print(self.Name, "PI::XPluginEnable: exception:")
            print_exc()
        return 0

    def XPluginDisable(self):
        try:
            if self.enabled and self.decks:
                self.decks.disable()
        except:
            if self.trace:
                print(self.Name, "PI::XPluginDisable: exception.")
            print_exc()
        self.enabled = False
        xp.checkMenuItem(xp.findPluginsMenu(), self.menuIdx, xp.Menu_Unchecked)
        if self.trace:
            print(self.Name, "PI::XPluginDisable: disabled.")
        return None

    def XPluginReceiveMessage(self, inFromWho, inMessage, inParam):
        """
        When we receive a message that an aircraft was loaded, if it is the user aircraft,
        we try to load the aicraft esdconfig. If it does not exist, we default to a screen saver.
        """
        if inMessage == xp.MSG_PLANE_LOADED and inParam == 0:  # 0 is for the user aircraft, greater than zero will be for AI aircraft.
            print(self.Name, "PI::XPluginReceiveMessage: user aircraft received")
            try:
                if self.decks:
                    if self.loadCurrentAircraft():
                        self.enabled = True
                else:
                    print(self.Name, "PI::XPluginReceiveMessage: no Cockpit")
            except:
                if self.trace:
                    print(self.Name, "PI::XPluginReceiveMessage: exception.")
                print_exc()
                self.enabled = False

    def loadCurrentAircraft(self):
        ac = xp.getNthAircraftModel(0)      # ('Cessna_172SP.acf', '/Volumns/SSD1/X-Plane/Aircraft/Laminar Research/Cessna 172SP/Cessna_172SP.acf')
        if len(ac) == 2:
            acpath = os.path.split(ac[1])   # ('/Volumns/SSD1/X-Plane/Aircraft/Laminar Research/Cessna 172SP', 'Cessna_172SP.acf')
            print(self.Name, "PI::loadCurrentAircraft: trying " + acpath[0] + "..")
            self.decks.load(acpath=acpath[0])
            print(self.Name, "PI::loadCurrentAircraft: .. " + acpath[0] + " done.")
            return True
        print(self.Name, "PI::loadCurrentAircraft: not found.")
        return False


    def cockpitCmd(self, *args, **kwargs):
        """
        Command hook to either start or reload current aircraft esdconfig.
        """
        # pylint: disable=unused-argument
        if not self.enabled:
            print(self.Name, "PI::cockpitCmd: not enabled.")
            return 0

        # When mapped on a keystroke, StreamDeck only starts on begin of command (phase=0).
        # Phase=1 (continuous press) and phase=2 (release key) are ignored.
        # If phase not found, report it in log and assume phase=0 (i.e. work will be done.)
        commandPhase = 0
        if len(args) > 2:
            commandPhase = args[1]
            if self.trace:
                print(self.Name, "PI::cockpitCmd: command phase", commandPhase)
        else:
            print(self.Name, "PI::cockpitCmd: no command phase", len(args))

        if not self.decks:
            try:
                self.decks = Cockpit(XPlaneSDK)
                if self.trace:
                    print(self.Name, "PI::cockpitCmd: created.")
            except:
                if self.trace:
                    print(self.Name, "PI::cockpitCmd: exception(creating).")
                print_exc()
                return 0

        if self.decks and commandPhase == 0:
            if self.trace:
                print(self.Name, "PI::cockpitCmd: available.")
            try:
                if self.loadCurrentAircraft():
                    if self.trace:
                        print(self.Name, "PI::cockpitCmd: started.")
                    return 1
                if self.trace:
                    print(self.Name, "PI::cockpitCmd: aircraft not found.")
                return 0
            except:
                if self.trace:
                    print(self.Name, "PI::cockpitCmd: exception(loading).")
                print_exc()
                return 0
        elif not self.decks:
            print(self.Name, "PI::cockpitCmd: Error: could not create Cockpit.")

        return 0
