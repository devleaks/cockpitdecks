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
def all_subclasses(cls):

    if cls == type:
        raise ValueError("Invalid class - 'type' is not a class")

    subclasses = set()

    stack = []
    try:
        stack.extend(cls.__subclasses__())
    except (TypeError, AttributeError) as ex:
        raise ValueError("Invalid class" + repr(cls)) from ex

    while stack:
        sub = stack.pop()
        subclasses.add(sub)
        try:
            stack.extend(s for s in sub.__subclasses__() if s not in subclasses)
        except (TypeError, AttributeError):
           continue

    return list(subclasses)


ACTIVATIONS = {s.name(): s for s in all_subclasses(Activation)}

def get_activations_for(action: DECK_ACTIONS) -> list:
    # trick: *simultaneous* actions are in same word, "-" separated, example encoder-push.
    DASH = "-"
    if DASH in action.value:
        actions = action.value.split(DASH)
        ret = []
        for a in ACTIVATIONS.values():
            ok = True
            for actstr in actions:
                act = DECK_ACTIONS(actstr)
                if act not in a.get_required_capability():
                    ok = False
            if ok:
                ret.append(a)
        return ret

    return [a for a in ACTIVATIONS.values() if action in a.get_required_capability()]
