# ###########################
# Mapping between button types and deck capabilities
#
from .button_core import Button, ButtonNone, ButtonPage, ButtonReload, ButtonInspect
from .button_core import ButtonPush, ButtonDual, ButtonLongpress
from .button_core import ButtonUpDown, ButtonAnimate

from .button_knob import KnobNone, Knob, KnobPush, KnobPushPull, KnobPushTurnRelease, KnobDataref, KnobLED
from .button_loupe import ColoredButton, ButtonSide
from .button_airbus import AirbusButton, AirbusButtonPush, AirbusButtonAnimate
from .button_data import DataButton


STREAM_DECK_BUTTON_TYPES = {
    "none": Button,
    "button-none": ButtonNone,
    "page": ButtonPage,
    "inspect": ButtonInspect,
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
    "button-none": ButtonNone,
    "page": ButtonPage,
    "inspect": ButtonInspect,
    "push": ButtonPush,
    "dual": ButtonDual,
    "long-press": ButtonLongpress,
    "updown": ButtonUpDown,
    "animate": ButtonAnimate,
    "knob-none": KnobNone,
    "knob": Knob,
    "knob-push": KnobPush,
    "knob-push-pull": KnobPushPull,
    "knob-dataref": KnobDataref,
    "button": ColoredButton,
    "side": ButtonSide,
    "airbus": AirbusButton,
    "airbus-push": AirbusButtonPush,
    "airbus-animate": AirbusButtonAnimate,
    "data": DataButton,
    "reload": ButtonReload
}

XTOUCH_MINI_BUTTON_TYPES = {
    "none": Button,
    "inspect": ButtonInspect,
    "push": ButtonPush,
    "dual": ButtonDual,
    "long-press": ButtonLongpress,
    "knob-none": KnobNone,
    "knob": Knob,
    "knob-led": KnobLED,
    "knob-push": KnobPush,
    "knob-push-pull": KnobPushPull,
    "knob-push-turn-release": KnobPushTurnRelease
}
