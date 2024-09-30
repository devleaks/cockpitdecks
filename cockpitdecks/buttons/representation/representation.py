"""
Button display and rendering abstraction.
All representations are listed at the end of this file.
"""

import logging

from cockpitdecks import ID_SEP, DECK_KW, DECK_FEEDBACK, DEFAULT_ATTRIBUTE_PREFIX, parse_options


logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


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

    def __init__(self, button: "Button"):
        self.button = button
        self._representation_config = button._config.get(self.name(), {})
        if type(self._representation_config) is not dict:  # repres: something -> {"repres": something}
            self._representation_config = {self.name(): self._representation_config}

        self._vibrate = self.get_attribute("vibrate")
        self._sound = self.get_attribute("sound")
        self._cached = None
        self.datarefs = None

        self.button.deck.cockpit.set_logging_level(__name__)

        self.options = parse_options(button._config.get("options"))

        if type(self.REQUIRED_DECK_FEEDBACKS) not in [list, tuple]:
            self.REQUIRED_DECK_FEEDBACKS = [self.REQUIRED_DECK_FEEDBACKS]

        self.init()

    @property
    def _config(self):
        return self.button._config

    def init(self):  # ~ABC
        pass

    def clean_cache(self):
        self._cached = None

    def can_render(self) -> bool:
        button_cap = self.button._def[DECK_KW.FEEDBACK.value]
        if button_cap not in self.get_required_capability():
            logger.warning(f"button {self.button_name()} has feedback capability {button_cap}, representation expects {self.REQUIRED_DECK_FEEDBACKS}.")
            return False
        return True

    def get_id(self):
        return ID_SEP.join([self.button.get_id(), type(self).__name__])

    def inc(self, name: str, amount: float = 1.0, cascade: bool = True):
        self.button.sim.inc_internal_dataref(path=ID_SEP.join([self.get_id(), name]), amount=amount, cascade=cascade)

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

    def get_text_detail(self, config, which_text):
        return self.button.get_text_detail(config, which_text)

    def inspect(self, what: str | None = None):
        logger.info(f"{type(self).__name__}:")
        logger.info(f"{self.is_valid()}")

    def is_valid(self):
        if self.button is None:
            logger.warning(f"representation {type(self).__name__} has no button")
            return False
        return True

    def has_option(self, option):
        # Check whether a button has an option.
        for opt in self.options:
            if opt.split("=")[0].strip() == option:
                return True
        return False

    def option_value(self, option, default=None):
        # Return the value of an option or the supplied default value.
        for opt in self.options:
            opt = opt.split("=")
            name = opt[0]
            if name == option:
                if len(opt) > 1:
                    return opt[1]
                else:  # found just the name, so it may be a boolean, True if present
                    return True
        return default

    def get_simulator_data(self) -> set:
        return set()

    def get_button_value(self):
        # shortcut for representations
        return self.button.value

    def get_status(self):
        return {"representation_type": type(self).__name__, "sound": self._vibrate}

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
        return self._vibrate

    def clean(self):
        # logger.warning(f"button {self.button_name()}: no cleaning")
        pass

    def describe(self) -> str:
        return "The button does not produce any output."
