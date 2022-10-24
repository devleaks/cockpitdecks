# ###########################
# Mapping between button types and deck capabilities
#
from .button_core import Button, ButtonPage, ButtonReload, ButtonInspect
from .button_core import ButtonPush, ButtonDual, ButtonLongpress
from .button_core import ButtonUpDown, ButtonAnimate

from .button_knob import KnobPush, KnobPushPull, KnobPushTurnRelease, KnobDataref
from .button_loupe import ColoredButton, ButtonSide
from .button_airbus import AirbusButton, AirbusButtonPush, AirbusButtonAnimate


STREAM_DECK_BUTTON_TYPES = {
    "none": Button,
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
    "page": ButtonPage,
    "inspect": ButtonInspect,
    "push": ButtonPush,
    "dual": ButtonDual,
    "long-press": ButtonLongpress,
    "updown": ButtonUpDown,
    "animate": ButtonAnimate,
    "knob": KnobPush,
    "knob-push-pull": KnobPushPull,
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
    "inspect": ButtonInspect,
    "push": ButtonPush,
    "dual": ButtonDual,
    "long-press": ButtonLongpress,
    "knob": KnobPush,
    "knob-push-pull": KnobPushPull,
    "knob-push-turn-release": KnobPushTurnRelease
}
