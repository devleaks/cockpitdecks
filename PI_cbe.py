# Creates pair of commands for commandBegin/CommentEnd
#
import xp
from traceback import print_exc

RELEASE = "0.0.1"

COMMANDS = [
    "AirbusFBW/FireTestAPU"
]

class PythonInterface:

    def __init__(self):
        self.Name = "Command Begin End"
        self.Sig = "commandbeginend.xppython3"
        self.Desc = "Decompose commands in begin and end. (Rel. " + RELEASE + ")"
        self.enabled = False
        self.trace = True  # produces extra debugging in XPPython3.log for this class
        self.commands = {}

    def XPluginStart(self):
        """
        For each command in COMMANDS, registers 2 commands with name "{command}/begin" and "{command}/end".
        """
        for command in COMMANDS:
            try:
                cmdref = xp.findCommand(command)
                cmd = command + '/begin'
                self.commands[cmd] = {}
                self.commands[cmd]["cmdRef"] = xp.createCommand(cmd, 'Begin '+cmd)
                self.commands[cmd]["cmd"] = xp.registerCommandHandler(self.commands[cmd]["cmdRef"], lambda: xp.XPLMCommandBegin(cmdref), 1, None)
                if self.trace:
                    print(self.Name, f"PI::XPluginStart: added {cmd}")
                cmd = command + '/end'
                self.commands[cmd] = {}
                self.commands[cmd]["cmdRef"] = xp.createCommand(cmd, 'End '+cmd)
                self.commands[cmd]["cmd"] = xp.registerCommandHandler(self.commands[cmd]["cmdRef"], lambda: xp.XPLMCommandEnd(cmdref), 1, None)
                if self.trace:
                    print(self.Name, f"PI::XPluginStart: added {cmd}")
            except:
                if self.trace:
                    print(self.Name, "PI::XPluginStart: exception:")
                print_exc()
                continue

        if self.trace:
            print(self.Name, f"PI::XPluginStart: {len(self.commands)} commands installed.")

        return self.Name, self.Sig, self.Desc

    def XPluginStop(self):
        for k, v in self.commands.items():
            xp.unregisterCommandHandler(v["cmdRef"], v["cmd"], 1, None)
        if self.trace:
            print(self.Name, "PI::XPluginStop: stopped.")
        return None

    def XPluginEnable(self):
        self.enabled = True
        if self.trace:
            print(self.Name, "PI::XPluginEnable: enabled.")
        return 1

    def XPluginDisable(self):
        self.enabled = False
        if self.trace:
            print(self.Name, "PI::XPluginDisable: disabled.")
        return None

    def XPluginReceiveMessage(self, inFromWho, inMessage, inParam):
        pass
