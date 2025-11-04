# PARAMETERS

# ######################
# COMMON
#
PARAM_DESCRIPTION = {
    "name": {"type": "string", "label": "Name"},
    "label": {"type": "string", "label": "Label"},
    "label-size": {"type": "string", "label": "Lbl size"},
    "label-font": {"type": "string", "label": "Lbl font"},
    "label-position": {"type": "lov", "label": "Lbl position", "lov": ["tl", "tc", "tr", "ml", "mc", "mr", "bl", "bc", "br"]},
    "label-color": {"type": "string", "label": "Lbl color"},
}

PARAM_INITIAL_VALUE = {
    "initial-value": {"type": "integer", "label": "Initial value"},
}

PARAM_DECK = {
    "sound": {"label": "Sound", "type": "string"},
    "vibrate": {"label": "Vibrate", "type": "string"},
}

# ######################
# ACTIVATION
#
# COMMON BLOCKS
PARAM_COMMAND_BLOCK = {
    "command": {"type": "string", "label": "Command"},
    "set-dataref": {"type": "string", "label": "Set Simulator Value"},
    "delay": {"type": "string", "label": "Delay"},
    "condition": {"type": "string", "label": "Condition"},
}

PARAM_SETVALUE_BLOCK = {
    "set-dataref": {"type": "string", "label": "Set Simulator Value"},
    "delay": {"type": "string", "label": "Delay"},
    "condition": {"type": "string", "label": "Condition"},
}

PARAM_PUSH_AUTOREPEAT = {
    "auto-repeat": {"type": "boolean", "label": "Auto-repeat"},
    "auto-repeat-delay": {"type": "float", "label": "Auto-repeat delay", "hint": "Delay after press before repeat"},
    "auto-repeat-speed": {"type": "float", "label": "Auto-repeat speed", "hint": "Speed of repeat"},
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
