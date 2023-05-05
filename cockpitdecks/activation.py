"""
Button action and activation abstraction
"""
from .button_activation import Activation
from .button_activation import LoadPage, Reload, Inspect, Stop
from .button_activation import Push, Longpress, OnOff, UpDown
from .button_activation import Encoder, EncoderPush, EncoderOnOff, EncoderValue
from .button_activation import Slider, Swipe

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

#
# ###############################
# DECK ACTIVATION MAP
#
#
# This estabishes the link between deck capabilities and Activations
#
push = ["page", "reload", "inspect", "stop", "push", "longpress", "onoff", "updown"]
encoder = ["encoder", "encoder-push", "encoder-onoff", "encoder-value", "knob"]

DECK_ACTIVATIONS = {
    "push": push,
    "encoder": encoder,
    "encoder-push": push + encoder,
    "slider": ["slider"],
    "cursor": ["cursor"],
    "swipe": push + ["swipe"]
}
