"""
Button display and rendering abstraction.
All representations are listed at the end of this file.
"""

import logging
import colorsys

from enum import Enum

from PIL import ImageDraw, ImageFont

from cockpitdecks.resources.color import (
    convert_color,
    is_integer,
    has_ext,
    add_ext,
    DEFAULT_COLOR,
)
from cockpitdecks import CONFIG_KW, DECK_KW, DECK_FEEDBACK, DEFAULT_ATTRIBUTE_PREFIX

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

DEFAULT_VALID_TEXT_POSITION = "cm"  # text centered on icon (center, middle)


# ##########################################
# REPRESENTATION
#
class Representation:
    """
    Base class for all representations
    """

    REPRESENTATION_NAME = "none"
    REQUIRED_DECK_FEEDBACKS = DECK_FEEDBACK.NONE

    PARAMETERS = {}

    @classmethod
    def parameters(cls) -> dict:
        return cls.PARAMETERS

    @classmethod
    def name(cls) -> str:
        return cls.REPRESENTATION_NAME

    @classmethod
    def get_required_capability(cls) -> list | tuple:
        r = cls.REQUIRED_DECK_FEEDBACKS
        return r if type(r) in [list, tuple] else [r]

    def __init__(self, config: dict, button: "Button"):
        self._config = config
        self._representation_config = config.get(self.name(), {})
        if type(self._representation_config) is not dict:  # repres: something -> {"repres": something}
            self._representation_config = {self.name(): self._representation_config}
        self.button = button
        self._sound = self.get_attribute("vibrate")
        self.datarefs = None

        self.button.deck.cockpit.set_logging_level(__name__)

        if type(self.REQUIRED_DECK_FEEDBACKS) not in [list, tuple]:
            self.REQUIRED_DECK_FEEDBACKS = [self.REQUIRED_DECK_FEEDBACKS]

        self.init()

    def init(self):  # ~ABC
        pass

    def can_render(self) -> bool:
        button_cap = self.button._def[DECK_KW.FEEDBACK.value]
        if button_cap not in self.get_required_capability():
            logger.warning(f"button {self.button_name()} has feedback capability {button_cap}, representation expects {self.REQUIRED_DECK_FEEDBACKS}.")
            return False
        return True

    def button_name(self):
        return self.button.name if self.button is not None else "no button"

    def get_attribute(self, attribute: str, default=None, propagate: bool = True, silence: bool = True):
        # Is there such an attribute directly in the button defintion?
        if attribute.startswith(DEFAULT_ATTRIBUTE_PREFIX):
            logger.warning(f"button {self.button_name()}: representation fetched default attribute {attribute}")

        value = self._representation_config.get(attribute)
        if value is not None:  # found!
            if silence:
                logger.debug(f"button {self.button_name()} representation returning {attribute}={value}")
            else:
                logger.info(f"button {self.button_name()} representation returning {attribute}={value}")
            return value

        if propagate:  # we just look at the button level if allowed, not above.
            if not silence:
                logger.info(f"button {self.button_name()} representation propagate to button for {attribute}")
            return self.button.get_attribute(attribute, default=default, propagate=propagate, silence=silence)

        if not silence:
            logger.warning(f"button {self.button_name()}: representation attribute not found {attribute}, returning default ({default})")

        return default

    def inspect(self, what: str | None = None):
        logger.info(f"{type(self).__name__}:")
        logger.info(f"{self.is_valid()}")

    def is_valid(self):
        if self.button is None:
            logger.warning(f"representation {type(self).__name__} has no button")
            return False
        return True

    def get_datarefs(self) -> list:
        return []

    def get_current_value(self):
        return self.button.get_current_value()

    def get_status(self):
        return {"representation_type": type(self).__name__, "sound": self._sound}

    def render(self):
        """
        This is the main rendering function for all representations.
        It returns what is appropriate to the button render() function which passes
        it to the deck's render() function which takes appropriate action
        to pass the returned value to the appropriate device function for display.
        """
        logger.debug(f"button {self.button_name()}: {type(self).__name__} has no rendering")
        return None

    def vibrate(self):
        return self.get_vibration()

    def get_vibration(self):
        return self._sound

    def clean(self):
        # logger.warning(f"button {self.button_name()}: no cleaning")
        pass

    def describe(self) -> str:
        return "The button does not produce any output."
