"""
Button action and activation abstraction
"""

from .activation import Activation, ACTIVATION_VALUE
from .cockpit_activation import LoadPage, Reload, Inspect, Stop
from .deck_activation import Push, OnOff, UpDown
from .deck_activation import BeginEndPress
from .deck_activation import Encoder, EncoderPush, EncoderOnOff, EncoderValue, EncoderToggle
from .deck_activation import EncoderValueExtended
from .deck_activation import Slider, Swipe

from cockpitdecks import DECK_ACTIONS


def get_activations_for(action: DECK_ACTIONS, all_activations) -> list:
    return [a for a in all_activations.values() if action in a.get_required_capability()]
