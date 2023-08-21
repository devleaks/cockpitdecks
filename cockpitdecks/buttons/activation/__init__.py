"""
Button action and activation abstraction
"""
from .activation import Activation
from .activation import LoadPage, Reload, Inspect, Stop
from .activation import Push, Longpress, OnOff, UpDown
from .activation import Encoder, EncoderPush, EncoderOnOff, EncoderValue
from .activation import Slider, Swipe

# ###############################
# format is activation: Classname
#
#   - index: e2
#     name: FCU Baro
#     type: encoder-onoff         <--------
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
    "knob": EncoderValue,
    "slider": Slider,
    "cursor": Slider,
    "swipe": Swipe
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
push = ["page", "reload", "inspect", "stop", "push", "longpress", "onoff", "updown", "dref-collector"]
encoder = ["encoder", "encoder-push", "encoder-onoff", "encoder-value", "knob"]

# ###############################
# format is action: [ activation ]
# action is used in deck definitions
#
DECK_ACTIVATIONS = {
    "push": push,
    "encoder": encoder,
    "encoder-push": encoder + push,
    "cursor": ["cursor", "slider"],
    "swipe": ["swipe"] + push
}
