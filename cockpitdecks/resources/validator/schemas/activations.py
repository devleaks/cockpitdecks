# ACTIVATION SCHEMAS

# ######################
# COMMON
#
SCHEMA_LABEL = {
    "label": {"type": "string", "meta": {"label": "Label"}},
    "label-size": {"type": "integer", "meta": {"label": "Lbl size"}},
    "label-font": {"type": "font", "meta": {"label": "Lbl font", "default": "DIN.ttf"}},
    "label-position": {"type": "string", "meta": {"label": "Lbl position"}, "allowed": ["lt", "ct", "rt", "lm", "cm", "rm", "lb", "cb", "rb"]},
    "label-color": {"type": "color", "meta": {"label": "Lbl color"}},
}

# ######################
# ACTIVATION
#
# COMMON BLOCKS
SCHEMA_PUSH_AUTOREPEAT = {
    "auto-repeat": {"type": "boolean", "meta": {"label": "Auto-repeat"}},
    "auto-repeat-delay": {"type": "float", "meta": {"label": "Auto-repeat delay", "hint": "Delay after press before repeat"}},
    "auto-repeat-speed": {"type": "float", "meta": {"label": "Auto-repeat speed", "hint": "Speed of repeat"}},
}

SCHEMA_COMMAND_BLOCK = {
    "command": {"type": "string", "meta": {"label": "Command"}},
    "set-dataref": {"type": "string", "meta": {"label": "Set Simulator Value"}},
    "delay": {"type": ["integer", "float"], "meta": {"label": "Delay"}},
    "condition": {"type": ["string", "boolean", "integer"], "meta": {"label": "Condition"}},
}

SCHEMA_COMMANDS = {
    "type": "list",
    "schema": {
        "oneof": [
            {"type": "string"},
            {"type": "dict", "schema": SCHEMA_COMMAND_BLOCK},
        ]
    },
}

SCHEMA_COMMAND_WITH_MACRO = {
    "command": {
        "oneof": [
            {"type": "string", "meta": {"label": "Command"}},  # single commmand
            {"type": "dict", "schema": SCHEMA_COMMAND_BLOCK},  # single command block
            SCHEMA_COMMANDS,  # list of commands (Macro Command)
        ]
    },
}

ACTIVATION_NAMES = [
    "note: last updated 2025-12-15, alphabetical order",
    "activation-template",
    "base",
    "begin-end-command",
    "dimmer",
    "encoder",
    "encoder-onoff",
    "encoder-push",
    "encoder-toggle",
    "encoder-value",
    "encoder-value-extended",
    "inspect",
    "mosaic",
    "none",
    "obs",
    "onoff",
    "page",
    "push",
    "random",
    "reload",
    "short-or-long-press",
    "simulator",
    "slider",
    "stop",
    "swipe",
    "theme",
    "updown",
]

ACTIVATION_ATTRIBUTES = [
    "note: last updated 2025-12-15, alphabetical order",
    "action",
    "auto-repeat",
    "auto-repeat-delay",
    "auto-repeat-speed",
    "command",
    "command-long",
    "command-short",
    "commands",
    "condition",
    "dataref",
    "deck",
    "delay",
    "dimmer",
    "formula",
    "guard",
    "initial-value",
    "long-press",
    "long-time",
    "options",
    "page",
    "set-dataref",
    "sound",
    "step",
    "step-xl",
    "stepxl",
    "stops",
    "theme",
    "value",
    "value-max",
    "value-min",
    "vibrate",
    "view",
    "what",
]

# ######################
# OBSERVABLE
#

# @todo: Add schema for Observable definition

# - command: cockpitdecks-accumulator
#   name: test
#   save: 60
#   variables:
#     - sim/flightmodel/position/latitude
#     - sim/flightmodel/position/longitude
#     - sim/flightmodel2/position/pressure_altitude
