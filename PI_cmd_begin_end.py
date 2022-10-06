  # Creates pair of commandBegin/commandEnd for some commands.
# New commands for "command" are "command/begin" and "command/end".
#
import xp
from traceback import print_exc


RELEASE = "1.0.0"

REF = "cmdref"
FUN = "cmdfun"
HDL = "cmdhdl"

COMMANDS_TO_REGISTER = [
    "AirbusFBW/FireTestAPU"
]

class PythonInterface:

    def __init__(self):
        self.Name = "Command Begin End Helper"
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
        self.registerCommands()
        if self.trace:
            print(self.Info, f"PI::XPluginStart: started.")
        return self.Name, self.Sig, self.Desc

    def XPluginStop(self):
        self.unregisterCommands()
        if self.trace:
            print(self.Info, "PI::XPluginStop: stopped.")
        return None

    def XPluginEnable(self):
        self.enabled = True
        print(self.Info, "PI::XPluginEnable: enabled.")
        return 1

    def XPluginDisable(self):
        self.enabled = False
        if self.trace:
            print(self.Info, "PI::XPluginDisable: disabled.")
        return None

    def XPluginReceiveMessage(self, inFromWho, inMessage, inParam):
        return None

    def executeCommand(self, command: str, begin: bool) -> int:
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
                    print(self.Info, f"PI::executeCommand: {command} not found")
        except:
            if self.trace:
                print(self.Info, "PI::executeCommand: exception:")
            print_exc()
        return 0  # callback must return 0 or 1.

    def unregisterCommands(self):
        for k, v in self.commands.items():
            try:
                if FUN in v:  # cached commands have no FUN
                    xp.unregisterCommandHandler(v[REF], v[RUN], 1, None)
                if self.trace:
                    print(self.Info, f"PI::unregisterCommands: unregistered {k}")
            except:
                if self.trace:
                    print(self.Info, "PI::unregisterCommands: exception:")
                print_exc()
                continue

    def registerCommands(self):
        commands = self.listCommands()
        if len(commands) > 0:
            for command in commands:
                try:
                    cmd = command + '/begin'
                    self.commands[cmd] = {}
                    self.commands[cmd][REF] = xp.createCommand(cmd, 'Begin '+cmd)
                    self.commands[cmd][FUN] = lambda *args: self.executeCommand(command, True)
                    self.commands[cmd][HDL] = xp.registerCommandHandler(self.commands[cmd][REF], self.commands[cmd][FUN], 1, None)
                    if self.trace:
                        print(self.Info, f"PI::registerCommands: registered {cmd}")
                    cmd = command + '/end'
                    self.commands[cmd] = {}
                    self.commands[cmd][REF] = xp.createCommand(cmd, 'End '+cmd)
                    self.commands[cmd][FUN] = lambda *args: self.executeCommand(command, False)
                    self.commands[cmd][HDL] = xp.registerCommandHandler(self.commands[cmd][REF], self.commands[cmd][FUN], 1, None)
                    if self.trace:
                        print(self.Info, f"PI::registerCommands: registered {cmd}")
                except Exception as e:
                    if self.trace:
                        print(self.Info, "PI::registerCommands: exception:")
                    print_exc()
        else:
            if self.trace:
                print(self.Info, f"PI::registerCommands: no command to add.")

        if self.trace:
            print(self.Info, f"PI::registerCommands: {len(self.commands)} commands installed.")


    def listCommands(self):
        return  COMMANDS_TO_REGISTER
