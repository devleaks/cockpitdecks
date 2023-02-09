# ###########################
# Mapping between button types and deck capabilities
#
from .button_core import Button, ButtonNone, ButtonPage, ButtonReload, ButtonInspect
from .button_core import ButtonPush, ButtonDual, ButtonLongpress
from .button_core import ButtonUpDown, ButtonAnimate

from .button_knob import KnobNone, Knob, KnobPush, KnobPushPull, KnobPushTurnRelease, KnobDataref, KnobLED, Slider
from .button_loupe import ColoredButton, ButtonSide, ButtonStop
from .button_annunciators import AnnunciatorButton, AnnunciatorButtonPush, AnnunciatorButtonAnimate
from .button_data import DataButton, WeatherButton


# Special button names
#
COLORED_BUTTON = "button"
BUTTON_STOP = "stop"


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
    "annunciator": AnnunciatorButton,
    "annunciator-push": AnnunciatorButtonPush,
    "annunciator-animate": AnnunciatorButtonAnimate,
    "reload": ButtonReload
}

LOUPEDECK_BUTTON_TYPES = {
    "none": Button,
    "button-none": ButtonNone,
    "page": ButtonPage,
    BUTTON_STOP: ButtonStop,
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
    COLORED_BUTTON: ColoredButton,
    "side": ButtonSide,
    "annunciator": AnnunciatorButton,
    "annunciator-push": AnnunciatorButtonPush,
    "annunciator-animate": AnnunciatorButtonAnimate,
    "data": DataButton,
    "weather": WeatherButton,
    "reload": ButtonReload
}

XTOUCH_MINI_BUTTON_TYPES = {
    "none": Button,
    "page": ButtonPage,
    "inspect": ButtonInspect,
    "push": ButtonPush,
    "dual": ButtonDual,
    "long-press": ButtonLongpress,
    "knob-none": KnobNone,
    "knob": Knob,
    "knob-led": KnobLED,
    "knob-push": KnobPush,
    "knob-push-pull": KnobPushPull,
    "knob-push-turn-release": KnobPushTurnRelease,
    "slider": Slider,
    "reload": ButtonReload
}
