# Creates pair of commands for commandBegin/CommentEnd for some commands.
# New commands are command/begin and command/end.
#
# Principle:
# def a(b: str):
#     print(b)
# def execute(fun):
#     fun()
# todo = lambda: a("hello, world")
# execute(todo)
#
import os
import yaml
import xp
from traceback import print_exc
from streamdecks.constant import CONFIG_DIR, CONFIG_FILE, DEFAULT_LAYOUT


RELEASE = "0.0.10"  # local version number


class PythonInterface:

    def __init__(self):
        self.Name = "Streamdecks Helper"
        self.Sig = "commandbeginend.xppython3"
        self.Desc = f"Decompose commands in begin and end. (Rel. {RELEASE})"
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
            xp.unregisterCommandHandler(v["cmdRef"], v["cmd"], 1, None)
        if self.trace:
            print(self.Info, "PI::XPluginStop: stopped.")
        return None

    def XPluginEnable(self):
        try:
            ac = xp.getNthAircraftModel(0)      # ('Cessna_172SP.acf', '/Volumns/SSD1/X-Plane/Aircraft/Laminar Research/Cessna 172SP/Cessna_172SP.acf')
            if len(ac) == 2:
                acpath = os.path.split(ac[1])   # ('/Volumns/SSD1/X-Plane/Aircraft/Laminar Research/Cessna 172SP', 'Cessna_172SP.acf')
                print(self.Info, "PI::XPluginEnable: trying", acpath[0] + "..")
                self.load(acpath=acpath[0])
                print(self.Info, "PI::XPluginEnable: ", acpath[0] + "done.")
                self.enabled = True
                return 1
            print(self.Info, "PI::XPluginEnable: not found.")
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
        we try to load the aicraft esdconfig. If it does not exist, we default to a screen saver.
        """
        if inMessage == xp.MSG_PLANE_LOADED and inParam == 0:  # 0 is for the user aircraft, greater than zero will be for AI aircraft.
            print(self.Info, "PI::XPluginReceiveMessage: user aircraft received")
            try:
                ac = xp.getNthAircraftModel(0)      # ('Cessna_172SP.acf', '/Volumns/SSD1/X-Plane/Aircraft/Laminar Research/Cessna 172SP/Cessna_172SP.acf')
                if len(ac) == 2:
                    acpath = os.path.split(ac[1])   # ('/Volumns/SSD1/X-Plane/Aircraft/Laminar Research/Cessna 172SP', 'Cessna_172SP.acf')
                    if self.trace:
                        print(self.Info, "PI::XPluginReceiveMessage: trying", acpath[0] + "..")
                    self.load(acpath=acpath[0])
                    if self.trace:
                        print(self.Info, "PI::XPluginReceiveMessage: ", acpath[0] + "done.")
                    return None
                print(self.Info, "PI::XPluginReceiveMessage: aircraft not found.")
            except:
                if self.trace:
                    print(self.Info, "PI::XPluginReceiveMessage: exception.")
                print_exc()
                self.enabled = False
        return False

    def load(self, acpath):

        # remove previous command set
        for k, v in self.commands.items():
            try:
                xp.unregisterCommandHandler(v["cmdRef"], v["fun"], 1, None)
                if self.trace:
                    print(self.Info, f"PI::load: removed {k}")
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
                    cmdref = xp.findCommand(command)
                    cmd = command + '/begin'
                    self.commands[cmd] = {}
                    self.commands[cmd]["cmdRef"] = xp.createCommand(cmd, 'Begin '+cmd)
                    self.commands[cmd]["fun"] = lambda: xp.XPLMCommandBegin(cmdref)
                    self.commands[cmd]["cmdHdl"] = xp.registerCommandHandler(self.commands[cmd]["cmdRef"], self.commands[cmd]["fun"], 1, None)
                    if self.trace:
                        print(self.Info, f"PI::load: added {cmd}")
                    cmd = command + '/end'
                    self.commands[cmd] = {}
                    self.commands[cmd]["cmdRef"] = xp.createCommand(cmd, 'End '+cmd)
                    self.commands[cmd]["fun"] = lambda: xp.XPLMCommandEnd(cmdref)
                    self.commands[cmd]["cmdHdl"] = xp.registerCommandHandler(self.commands[cmd]["cmdRef"], self.commands[cmd]["fun"], 1, None)
                    if self.trace:
                        print(self.Info, f"PI::load: added {cmd}")
                except:
                    if self.trace:
                        print(self.Info, "PI::load: exception:")
                    print_exc()
                    continue
        else:
            if self.trace:
                print(self.Info, f"PI::load: no command to add.")

        if self.trace:
            print(self.Info, f"PI::load: {len(self.commands)} commands installed.")


    def get_beginend_commands(self, acpath):
        # Constants
        BUTTONS = "buttons"  # keywork in yaml file
        DECKS = "decks"
        LAYOUT = "layout"
        COMMAND = "command"
        MULTI_COMMANDS = "commands"
        NOTICABLE_BUTTON_TYPES = ["dual"]

        commands = []

        config_fn = os.path.join(acpath, CONFIG_DIR, CONFIG_FILE)
        if os.path.exists(config_fn):
            with open(config_fn, "r") as config_fp:
                config = yaml.safe_load(config_fp)
                if DECKS in config:
                    for deck in config[DECKS]:
                        layout = DEFAULT_LAYOUT
                        if LAYOUT in deck:
                            layout = deck[LAYOUT]
                        layout_dn = os.path.join(acpath, CONFIG_DIR, layout)
                        if not os.path.exists(layout_dn):
                            print(self.Info, f"PI::get_beginend_commands: stream deck has no layout folder '{layout}'")
                            continue
                        pages = os.listdir(layout_dn)
                        for page in pages:
                            if page.endswith("yaml") or page.endswith("yml"):
                                page_fn = os.path.join(layout_dn, page)
                                if os.path.exists(page_fn):
                                    with open(page_fn, "r") as page_fp:
                                        page_def = yaml.safe_load(page_fp)
                                        if not BUTTONS in page_def:
                                            print(f"load: {page_fn} has no action")
                                            continue
                                        for button_def in page_def[BUTTONS]:
                                            bty = None
                                            if "type" in button_def:
                                                bty = button_def["type"]
                                            if bty in NOTICABLE_BUTTON_TYPES:
                                                if COMMAND in button_def:
                                                    commands.append(button_def[COMMAND])
                                                if MULTI_COMMANDS in button_def:
                                                    for c in button_def[MULTI_COMMANDS]:
                                                        commands.append(c)
                                else:
                                    print(self.Info, f"PI::get_beginend_commands: file {page_fn} not found")
                            else:  # not a yaml file
                                print(self.Info, f"PI::get_beginend_commands: ignoring file {page}")
        else:
            print(self.Info, f"PI::get_beginend_commands: Looking in '{config_fn}' to scan for stream deck device layout: directory not found.")
        return commands