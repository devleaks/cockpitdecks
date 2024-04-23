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
NOTICABLE_BUTTON_TYPES = ["long-press", "longpress"]
#
#

REF = "cmdref"
FUN = "cmdfun"
HDL = "cmdhdl"


RELEASE = "1.0.5"  # local version number

# Changelog:
#
# 21-APR-2024: 1.0.5: See https://pylint.readthedocs.io/en/latest/user_guide/messages/warning/cell-var-from-loop.html for correction.
#                     Correction by dlicudi.
# 28-NOV-2023: 1.0.4: Scanning page files with glob.
# 21-NOV-2023: 1.0.3: Switched to ruamel.YAML.
# 21-NOV-2023: 1.0.2: Added encoding to file open.
# 28-FEB-2023: 1.0.1: Adjusted for new Yaml file format and attributes.
# 25-OCT-2022: 1.0.0: Initial version
#


class PythonInterface:
    def __init__(self):
        self.Name = "Cockpitdecks Helper"
        self.Sig = "xppython3.cockpitdeckshelper"
        self.Desc = f"Decompose long press commands into command/begin and command/end. (Rel. {RELEASE})"
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
                        print(self.Info, "PI::XPluginReceiveMessage: trying " + acpath[0] + "..")
                    self.load(acpath=acpath[0])
                    if self.trace:
                        print(self.Info, "PI::XPluginReceiveMessage: .. " + acpath[0] + " done.")
                    return None
                print(self.Info, "PI::XPluginReceiveMessage: getNthAircraftModel: aircraft not found.")
            except:
                if self.trace:
                    print(self.Info, "PI::XPluginReceiveMessage: exception.")
                print_exc()
                self.enabled = False
        return None

    def command(self, command: str, begin: bool) -> int:
        # Execute a long press command
        #
        try:
            if command in self.commands:
                if begin:
                    xp.commandBegin(self.commands[command][REF])
                else:
                    xp.commandEnd(self.commands[command][REF])
            else:
                cmdref = xp.findCommand(command)
                if cmdref is not None:
                    self.commands[command] = {}  # cache it
                    self.commands[command][REF] = cmdref
                    if begin:
                        xp.commandBegin(self.commands[command][REF])
                    else:
                        xp.commandEnd(self.commands[command][REF])
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
        commands = self.get_beginend_commands(acpath)
        if len(commands) > 0:
            for command in commands:
                try:
                    # cmdref = xp.findCommand(command)
                    # if cmdref is not None:
                    # As such, we only check for command existence at execution time.
                    cmd = command + "/begin"
                    self.commands[cmd] = {}
                    self.commands[cmd][REF] = xp.createCommand(cmd, "Begin " + cmd)
                    self.commands[cmd][FUN] = lambda *args, cmd=command: self.command(cmd, True)
                    # self.commands[cmd][FUN] = lambda *args: (xp.commandBegin(cmdref), 0)[1]  # callback must return 0 or 1
                    self.commands[cmd][HDL] = xp.registerCommandHandler(self.commands[cmd][REF], self.commands[cmd][FUN], 1, None)
                    if self.trace:
                        print(self.Info, f"PI::load: added {cmd}")
                    cmd = command + "/end"
                    self.commands[cmd] = {}
                    self.commands[cmd][REF] = xp.createCommand(cmd, "End " + cmd)
                    self.commands[cmd][FUN] = lambda *args, cmd=command: self.command(cmd, False)
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

    def get_beginend_commands(self, acpath):
        # Scans an aircraft deckconfig and collects long press commands.
        #
        # Internal constants (keywords in yaml file)
        #
        BUTTONS = "buttons"  # keyword for button definitions on page
        DECKS = "decks"  # keyword to list decks used for this aircraft
        LAYOUT = "layout"  # keyword to detect layout for above deck
        TYPE = "type"  # keyword to detect the action of the button (intend)
        COMMAND = "command"  # keyword to detect (X-Plane) command in definition of the button
        MULTI_COMMANDS = "commands"  # same as above for multiple commands

        DEBUG = False

        config_dn = os.path.join(acpath, CONFIG_DIR)
        if not os.path.isdir(config_dn):
            print(self.Info, f"PI::get_beginend_commands: Cockpitdecks config directory '{config_dn}' not found in aircraft path '{acpath}'")
            return []

        config_fn = os.path.join(config_dn, CONFIG_FILE)
        if not os.path.exists(config_fn):
            print(self.Info, f"PI::get_beginend_commands: Cockpitdecks config file '{config_fn}' not found in Cockpitdecks config dir '{config_dn}'")
            return []

        commands = []
        with open(config_fn, "r", encoding="utf-8") as config_fp:
            config = yaml.load(config_fp)
            if DECKS in config:
                for deck in config[DECKS]:
                    if DEBUG:
                        print(self.Info, f"PI::get_beginend_commands: doing deck {deck.get('name')}..")
                    layout = DEFAULT_LAYOUT
                    if LAYOUT in deck:
                        layout = deck[LAYOUT]
                    layout_dn = os.path.join(config_dn, layout)
                    if not os.path.exists(layout_dn):
                        print(self.Info, f"PI::get_beginend_commands: ..deck {deck.get('name')}: layout folder '{layout}' not found in '{config_dn}'")
                        continue
                    pages = []
                    for ext in ["yaml", "yml"]:
                        pages = pages + glob.glob(os.path.join(layout_dn, "*." + ext))
                    for page in pages:
                        if os.path.basename(page) == CONFIG_FILE:
                            if DEBUG:
                                print(self.Info, f"PI::get_beginend_commands: skipping config file {page}")
                            continue
                        if DEBUG:
                            print(self.Info, f"PI::get_beginend_commands: doing page {os.path.basename(page)}..")  #  (file {page})
                        with open(page, "r", encoding="utf-8") as page_fp:
                            page_def = yaml.load(page_fp)
                            if BUTTONS not in page_def:
                                print(self.Info, f"PI::get_beginend_commands: page {os.path.basename(page)} has no button (file {page})")
                                continue
                            for button_def in page_def[BUTTONS]:
                                # if DEBUG:
                                #     print(self.Info, f"PI::get_beginend_commands: doing button {button_def.get('index')}..")
                                bty = button_def.get(TYPE)
                                if bty is None:
                                    if DEBUG:
                                        print(self.Info, f"PI::get_beginend_commands: button {button_def} has no type")
                                    continue
                                if bty in NOTICABLE_BUTTON_TYPES:
                                    if DEBUG:
                                        print(self.Info, f"PI::get_beginend_commands: doing button {button_def.get('index')}")
                                    if COMMAND in button_def:
                                        commands.append(button_def[COMMAND])
                                        if DEBUG:
                                            print(self.Info, f"PI::get_beginend_commands: added {button_def[COMMAND]}")
                                    if MULTI_COMMANDS in button_def:
                                        for c in button_def[MULTI_COMMANDS]:
                                            commands.append(c)
                                            if DEBUG:
                                                print(self.Info, f"PI::get_beginend_commands: added multi-command {c}")
                                # if DEBUG:
                                #     print(self.Info, f"PI::get_beginend_commands: ..done button {button_def.get('index')}")
                        if DEBUG:
                            print(self.Info, f"PI::get_beginend_commands: ..done page {os.path.basename(page)}")
                    if DEBUG:
                        print(self.Info, f"PI::get_beginend_commands: ..done deck {deck.get('name')}")
        return commands
