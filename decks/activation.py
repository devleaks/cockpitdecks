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

