"""
Button action and activation abstraction
"""

from .activation import Activation
from .activation import LoadPage, Reload, Inspect, Stop
from .activation import Push, Longpress, OnOff, UpDown
from .activation import Encoder, EncoderPush, EncoderOnOff, EncoderValue, EncoderToggle
from .activation import EncoderValueExtended
from .activation import Slider, Swipe

from cockpitdecks import DECK_ACTIONS

# ###############################
# format is activation: Classname
#
#   - index: e2
#     name: FCU Baro
#     _type_: encoder-onoff         <-------- remove _ for type
#     commands:
#       - toliss_airbus/capt_baro_push
#       - toliss_airbus/capt_baro_pull
#       - sim/instruments/barometer_down
#       - sim/instruments/barometer_up
#
ACTIVATIONS = {
    "none": Activation,
    "page": LoadPage,
    "reload": Reload,
    "inspect": Inspect,
    "stop": Stop,
    "push": Push,
    "longpress": Longpress,
    "onoff": OnOff,
    "updown": UpDown,
    "encoder": Encoder,
    "encoder-push": EncoderPush,
    "encoder-onoff": EncoderOnOff,
    "encoder-value": EncoderValue,
    "encoder-value-extended": EncoderValueExtended,
    "knob": EncoderValue,
    "slider": Slider,
    "cursor": Slider,
    "swipe": Swipe,
    "encoder-toggle": EncoderToggle,
}

DEFAULT_ACTIVATIONS = ["none"] + ["page", "reload", "inspect", "stop"]

#
# ###############################
# DECK ACTIVATION MAP
#
#
# This estabishes the link between deck capabilities (action) and Activations
#
# - name: 0
#   prefix: e
#   action: encoder-push         <--------
#   view: none
#   repeat: 6
#
push = [
    "page",
    "reload",
    "inspect",
    "stop",
    "push",
    "longpress",
    "onoff",
    "updown",
    "dref-collector",
]
encoder = [
    "encoder",
    "encoder-push",
    "encoder-onoff",
    "encoder-value",
    "encoder-value-extended",
    "knob",
    "encoder-toggle",
]

# ###############################
# format is action: [ activation ]
# action is used in deck definitions
#
DECK_ACTIVATIONS = {
    "push": push,
    "encoder": encoder,
    "encoder-push": encoder + push,
    "cursor": ["cursor", "slider"],
    "swipe": ["swipe"] + push,
}


def get_activations_for(action: DECK_ACTIONS):
    # trick: *simultaneous* actions are in same word, "-" separated, example encoder-push.
    DASH = "-"
    if DASH in action.value:
        actions = action.split(DASH)
        ret = []
        for a in ACTIVATIONS.values():
            ok = True
            for act in actions:
                if act not in a.REQUIRED_DECK_ACTIONS:
                    ok = False
            if ok:
                ret.append(a)
        return ret

    return [a for a in ACTIVATIONS.values() if action in a.REQUIRED_DECK_ACTIONS]
