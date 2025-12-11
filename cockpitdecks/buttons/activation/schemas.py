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

SCHEMA_COMMANDS = {
    "type": "list",
    "schema": {
        "oneof": [
            {"type": "string"},
            {
                "type": "dict",
                "schema": {
                    "command": {"type": "string"},
                    "condition": {"type": "string"},
                    "delay":{"type": ["integer", "float"]}
                }
            }
        ]
    }
}


SCHEMA_COMMAND_BLOCK = {
    "command": {"type": "string", "meta": {"label": "Command"}},
    "set-dataref": {"type": "string", "meta": {"label": "Set Simulator Value"}},
    "delay": {"type": "string", "meta": {"label": "Delay"}},
    "condition": {"type": "string", "meta": {"label": "Condition"}},
}

SCHEMA_SETVALUE_BLOCK = {
    "set-dataref": {"type": "string", "meta": {"label": "Set Simulator Value"}},
    "delay": {"type": "string", "meta": {"label": "Delay"}},
    "condition": {"type": "string", "meta": {"label": "Condition"}},
}

SCHEMA_PUSH_AUTOREPEAT = {
    "auto-repeat": {"type": "boolean", "meta": {"label": "Auto-repeat"}},
    "auto-repeat-delay": {"type": "float", "meta": {"label": "Auto-repeat delay", "hint": "Delay after press before repeat"}},
    "auto-repeat-speed": {"type": "float", "meta": {"label": "Auto-repeat speed", "hint": "Speed of repeat"}},
}

# list on nov. 2025
# activation-template
# base
# begin-end-command
# dimmer
# encoder
# encoder-onoff
# encoder-push
# encoder-toggle
# encoder-value
# encoder-value-extended
# inspect
# mosaic
# none
# obs
# onoff
# page
# push
# random
# reload
# short-or-long-press
# simulator
# slider
# stop
# swipe
# theme
# updown


# ######################
# OBSERVABLE
#
# - command: cockpitdecks-accumulator
#   name: test
#   save: 60
#   variables:
#     - sim/flightmodel/position/latitude
#     - sim/flightmodel/position/longitude
#     - sim/flightmodel2/position/pressure_altitude
