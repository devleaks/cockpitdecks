"""
Button action and activation abstraction
"""

from .activation import Activation
from .activation import LoadPage, Reload, Inspect, Stop
from .activation import Push, Longpress, OnOff, UpDown
from .activation import Encoder, EncoderPush, EncoderOnOff, EncoderValue, EncoderToggle
from .activation import EncoderValueExtended
from .activation import Slider, Swipe

from cockpitdecks import DECK_ACTIONS, all_subclasses


ACTIVATIONS = {s.name(): s for s in all_subclasses(Activation)} | {DECK_ACTIONS.NONE.value: Activation}


def get_activations_for(action: DECK_ACTIONS) -> list:
    return [a for a in ACTIVATIONS.values() if action in a.get_required_capability()]
