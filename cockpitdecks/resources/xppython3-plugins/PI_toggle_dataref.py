# Creates pair of commandBegin/commandEnd for some commands.
# New commands for "command" are "command/begin" and "command/end".
#
import os
import glob
import ruamel
from ruamel.yaml import YAML
from traceback import print_exc

from XPPython3 import xp

ruamel.yaml.representer.RoundTripRepresenter.ignore_aliases = lambda x, y: True
yaml = YAML(typ="safe", pure=True)

# from decks.constant import CONFIG_DIR, CONFIG_FILE, DEFAULT_LAYOUT
# Copied here to make this script independent
CONFIG_DIR = "deckconfig"
CONFIG_FILE = "config.yaml"
DEFAULT_LAYOUT = "default"

#
#
# Commands extracted from these button types
# will get a command/begin command/end helper command.
#
#
REF = "cmdref"
FUN = "cmdfun"
HDL = "cmdhdl"

RELEASE = "1.0.0"  # local version number

# Changelog:
#
# 23-JUL-2024: 1.0.0: Initial version
#


class PythonInterface:
    def __init__(self):
        self.Name = "Set/Unset/Toggle writable «boolean» datarefs"
        self.Sig = "xppython3.cockpitdeckshelper"
        self.Desc = f"Make a boolean writable dataref settable by commands set/unset/toggle. (Rel. {RELEASE})"
        self.Info = self.Name + f" (rel. {RELEASE})"
        self.enabled = False
        self.trace = True  # produces extra print/debugging in XPPython3.log for this class
        self.commands = {}

    def XPluginStart(self):
        """
        Do nothing. Work is done upon aircraft loading
        """
        if self.trace:
            print(self.Info, f"PI::XPluginStart: started.")
        return self.Name, self.Sig, self.Desc

    def XPluginStop(self):
        for k, v in self.commands.items():
            if FUN in v:  # cached commands have no FUN
                xp.unregisterCommandHandler(v[REF], v[FUN], 1, None)
            if self.trace:
                print(self.Info, "PI::XPluginStop: unregistered", k)
        if self.trace:
            print(self.Info, "PI::XPluginStop: stopped.")
        return None

    def XPluginEnable(self):
        try:
            ac = xp.getNthAircraftModel(0)  # ('Cessna_172SP.acf', '/Volumns/SSD1/X-Plane/Aircraft/Laminar Research/Cessna 172SP/Cessna_172SP.acf')
            if len(ac) == 2:
                acpath = os.path.split(ac[1])  # ('/Volumns/SSD1/X-Plane/Aircraft/Laminar Research/Cessna 172SP', 'Cessna_172SP.acf')
                print(self.Info, "PI::XPluginEnable: trying " + acpath[0] + " ..")
                self.load(acpath=acpath[0])
                print(self.Info, "PI::XPluginEnable: " + acpath[0] + " done.")
                self.enabled = True
                return 1
            print(self.Info, "PI::XPluginEnable: getNthAircraftModel: aircraft not found.")
            return 1
        except:
            if self.trace:
                print(self.Info, "PI::XPluginEnable: exception.")
            print_exc()
            self.enabled = False
        return 0

    def XPluginDisable(self):
        self.enabled = False
        if self.trace:
            print(self.Info, "PI::XPluginDisable: disabled.")
        return None

    def XPluginReceiveMessage(self, inFromWho, inMessage, inParam):
        """
        When we receive a message that an aircraft was loaded, if it is the user aircraft,
        we try to load the aicraft deskconfig.
        If it does not exist, we default to a screen saver type of screen for the deck.
        """
        if inMessage == xp.MSG_PLANE_LOADED and inParam == 0:  # 0 is for the user aircraft, greater than zero will be for AI aircraft.
            print(self.Info, "PI::XPluginReceiveMessage: user aircraft received")
            try:
                ac = xp.getNthAircraftModel(0)  # ('Cessna_172SP.acf', '/Volumns/SSD1/X-Plane/Aircraft/Laminar Research/Cessna 172SP/Cessna_172SP.acf')
                if len(ac) == 2:
                    acpath = os.path.split(ac[1])  # ('/Volumns/SSD1/X-Plane/Aircraft/Laminar Research/Cessna 172SP', 'Cessna_172SP.acf')
                    if self.trace:
                        print(
                            self.Info,
                            "PI::XPluginReceiveMessage: trying " + acpath[0] + "..",
                        )
                    self.load(acpath=acpath[0])
                    if self.trace:
                        print(
                            self.Info,
                            "PI::XPluginReceiveMessage: .. " + acpath[0] + " done.",
                        )
                    return None
                print(
                    self.Info,
                    "PI::XPluginReceiveMessage: getNthAircraftModel: aircraft not found.",
                )
            except:
                if self.trace:
                    print(self.Info, "PI::XPluginReceiveMessage: exception.")
                print_exc()
                self.enabled = False
        return None

    def command(self, command: str, begin: bool | None) -> int:
        # Execute a long press command
        #
        try:
            if command in self.commands:
                cmdref = self.commands[command][REF]
                dtype = xp.getDataRefTypes(cmdref)

                val = 0
                if begin is None:  # toggle value
                    if bool(dtype & xp.Type_Float):
                        val = xp.getDataf(cmdref)
                    elif bool(dtype & xp.Type_Int):
                        val = xp.getDataf(cmdref)
                    val = 0 if val == 1 else 1  # invert value
                else:
                    val = 0 if not begin else 1

                if bool(dtype & xp.Type_Float):
                    val = float(val)
                    xp.setDataf(cmdref, val)
                elif bool(dtype & xp.Type_Int):
                    val = int(val)
                    xp.setDataf(cmdref, val)

            else:
                cmdref = xp.findDataRef(command)
                if cmdref is not None:
                    if xp.canWriteDataRef(cmdref):
                        self.commands[command] = {}  # cache it
                        self.commands[command][REF] = cmdref
                        dtype = xp.getDataRefTypes(cmdref)

                        val = 0
                        if begin is None:  # toggle value
                            if bool(dtype & xp.Type_Float):
                                val = xp.getDataf(cmdref)
                            elif bool(dtype & xp.Type_Int):
                                val = xp.getDataf(cmdref)
                            val = 0 if val == 1 else 1  # invert value
                        else:
                            val = 0 if not begin else 1

                        if bool(dtype & xp.Type_Float):
                            val = float(val)
                            xp.setDataf(cmdref, val)
                        elif bool(dtype & xp.Type_Int):
                            val = int(val)
                            xp.setDataf(cmdref, val)
                    else:
                        print(self.Info, f"PI::command: {command} not writable")
                else:
                    print(self.Info, f"PI::command: {command} not found")
        except:
            if self.trace:
                print(self.Info, "PI::command: exception:")
            print_exc()
        return 0  # callback must return 0 or 1.

    def load(self, acpath):
        # Unload previous aircraft's command set.
        # Load current aircraft command set.
        #
        # remove previous command set
        for k, v in self.commands.items():
            try:
                if FUN in v:  # cached commands have no FUN
                    xp.unregisterCommandHandler(v[REF], v[FUN], 1, None)
                if self.trace:
                    print(self.Info, f"PI::load: unregistered {k}")
            except:
                if self.trace:
                    print(self.Info, "PI::load: exception:")
                print_exc()
                continue

        # install this aircraft's set
        commands = self.get_settable_datarefs(acpath)
        if len(commands) > 0:
            for command in commands:
                command = command.replace("[", "_").replace("]", "")  # array[6] -> array_6
                try:
                    # cmdref = xp.findCommand(command)
                    # if cmdref is not None:
                    # As such, we only check for command existence at execution time.
                    cmd = command + "/set"
                    self.commands[cmd] = {}
                    self.commands[cmd][REF] = xp.createCommand(cmd, "Set " + cmd)
                    self.commands[cmd][FUN] = lambda *args, cmd=command: self.command(command, True)
                    # self.commands[cmd][FUN] = lambda *args: (xp.commandBegin(cmdref), 0)[1]  # callback must return 0 or 1
                    self.commands[cmd][HDL] = xp.registerCommandHandler(self.commands[cmd][REF], self.commands[cmd][FUN], 1, None)
                    if self.trace:
                        print(self.Info, f"PI::load: added {cmd}")
                    cmd = command + "/unset"
                    self.commands[cmd] = {}
                    self.commands[cmd][REF] = xp.createCommand(cmd, "Unset " + cmd)
                    self.commands[cmd][FUN] = lambda *args, cmd=command: self.command(command, False)
                    # self.commands[cmd][FUN] = lambda *args: (xp.commandEnd(cmdref), 0)[1]  # callback must return 0 or 1
                    self.commands[cmd][HDL] = xp.registerCommandHandler(self.commands[cmd][REF], self.commands[cmd][FUN], 1, None)
                    if self.trace:
                        print(self.Info, f"PI::load: added {cmd}")
                    cmd = command + "/toggle"
                    self.commands[cmd] = {}
                    self.commands[cmd][REF] = xp.createCommand(cmd, "Toggle " + cmd)
                    self.commands[cmd][FUN] = lambda *args, cmd=command: self.command(command, None)
                    # self.commands[cmd][FUN] = lambda *args: (xp.commandEnd(cmdref), 0)[1]  # callback must return 0 or 1
                    self.commands[cmd][HDL] = xp.registerCommandHandler(self.commands[cmd][REF], self.commands[cmd][FUN], 1, None)
                    if self.trace:
                        print(self.Info, f"PI::load: added {cmd}")
                    # else:
                    #     print(self.Info, f"PI::load: {command} not found")
                except Exception as e:
                    if self.trace:
                        print(self.Info, "PI::load: exception:")
                    print_exc()
        else:
            if self.trace:
                print(self.Info, f"PI::load: no command to add.")

        if self.trace:
            print(self.Info, f"PI::load: {len(self.commands)} commands installed.")

    def get_settable_datarefs(self, acpath):
        # Scans an aircraft deckconfig and collects long press commands.
        #
        # Internal constants (keywords in yaml file)
        #
        commands = [
            "AirbusFBW/ADIRUSwitchArray[0]",
            "AirbusFBW/ADIRUSwitchArray[1]",
            "AirbusFBW/ADIRUSwitchArray[2]",
        ]

        return commands
