"""
Button display and rendering abstraction.
All representations are listed at the end of this file.
"""

import logging
import colorsys

from enum import Enum

from PIL import ImageDraw, ImageFont

from XTouchMini.Devices.xtouchmini import LED_MODE

from cockpitdecks.resources.color import (
    convert_color,
    is_integer,
    has_ext,
    add_ext,
    DEFAULT_COLOR,
)
from cockpitdecks import CONFIG_KW, DECK_FEEDBACK
from cockpitdecks.buttons.representation import Representation

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

DEFAULT_VALID_TEXT_POSITION = "cm"  # text centered on icon (center, middle)


class EncoderLEDs(Representation):
    """
    Ring of 13 LEDs surrounding X-Touch Mini encoders
    """

    REPRESENTATION_NAME = "encoder-leds"
    REQUIRED_DECK_FEEDBACKS = DECK_FEEDBACK.ENCODER_LEDS

    def __init__(self, button: "Button"):
        Representation.__init__(self, button=button)

        mode = self._config.get("encoder-leds", LED_MODE.SINGLE.name)

        self.mode = LED_MODE.SINGLE
        if is_integer(mode) and int(mode) in [l.value for l in LED_MODE]:
            self.mode = LED_MODE(mode)
        elif type(mode) is str and mode.upper() in [l.name for l in LED_MODE]:
            mode = mode.upper()
            self.mode = LED_MODE[mode]
        else:
            logger.warning(f"{type(self).__name__}: invalid mode {mode}")

    def is_valid(self):
        maxval = 7 if self.mode == LED_MODE.SPREAD else 13
        value = self.get_current_value()
        if value >= maxval:
            logger.warning(f"button {self.button_name()}: {type(self).__name__}: value {value} too large for mode {self.mode}")
        return super().is_valid()

    def render(self):
        maxval = 7 if self.mode == LED_MODE.SPREAD else 13
        v = min(int(self.get_current_value()), maxval)
        return (v, self.mode)

    def clean(self):
        self.button.set_current_value(0)
        self.button.render()

    def describe(self) -> str:
        """
        Describe what the button does in plain English
        """
        a = [f"The representation turns multiple LED ON or OFF around X-Touch Mini encoders"]
        return "\n\r".join(a)
