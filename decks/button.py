"""
Different button classes for different purpose.
Button base class does not perform any action, it mainly is an ABC.

Buttons do
1. Execute zero or more X-Plane command
2. Optionally update their representation to confirm the action

Button phases:
1. button_value() compute the unique value that will become an index in an array.
   Value is stored in current_value
2. if current_value has changed, provoke render()
3. render: set_key_icon(): get the key icon from the array of available icons and the index (current_value)
   render: get_image(): builds an image from the key icon and text overlay(s)
   render returns the image to the deck for display in the proper key.

"""
from .button_core import Button, ButtonPage, ButtonReload
from .button_core import ButtonPush, ButtonDual, ButtonLongpress
from .button_core import ButtonUpDown, ButtonAnimate

from .button_knob import KnobPush, KnobPushPull, KnobPushTurnRelease, KnobDataref

from .button_loupe import ColoredButton, ButtonSide

from .button_airbus import AirbusButton, AirbusButtonPush, AirbusButtonAnimate



# ###########################
# Mapping between button types and classes
#
STREAM_DECK_BUTTON_TYPES = {
    "none": Button,
    "page": ButtonPage,
    "push": ButtonPush,
    "dual": ButtonDual,
    "long-press": ButtonLongpress,
    "updown": ButtonUpDown,
    "animate": ButtonAnimate,
    "airbus": AirbusButton,
    "airbus-push": AirbusButtonPush,
    "airbus-animate": AirbusButtonAnimate,
    "reload": ButtonReload
}

LOUPEDECK_BUTTON_TYPES = {
    "none": Button,
    "page": ButtonPage,
    "push": ButtonPush,
    "dual": ButtonDual,
    "long-press": ButtonLongpress,
    "updown": ButtonUpDown,
    "animate": ButtonAnimate,
    "knob": KnobPush,
    "knob-push-pull": KnobPushPull,
    "knob-push-turn-release": KnobPushTurnRelease,
    "knob-dataref": KnobDataref,
    "button": ColoredButton,
    "side": ButtonSide,
    "airbus": AirbusButton,
    "airbus-push": AirbusButtonPush,
    "airbus-animate": AirbusButtonAnimate,
    "reload": ButtonReload
}

XTOUCH_MINI_BUTTON_TYPES = {
    "none": Button,
    "push": ButtonPush,
    "dual": ButtonDual,
    "long-press": ButtonLongpress,
    "knob": KnobPush,
    "knob-push-pull": KnobPushPull
}
