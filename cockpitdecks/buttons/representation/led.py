"""
Representation for LED.
"""

import logging
import colorsys

from cockpitdecks.resources.color import convert_color
from cockpitdecks import CONFIG_KW, DECK_KW, DECK_FEEDBACK
from .representation import Representation

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


#
# ###############################
# LED TYPE REPRESENTATION
#
#
class LED(Representation):

    REPRESENTATION_NAME = "led"
    REQUIRED_DECK_FEEDBACKS = DECK_FEEDBACK.LED

    def __init__(self, button: "Button"):
        Representation.__init__(self, button=button)

        self.mode = self._config.get("led", "single")  # unused

    def render(self):
        value = self.get_current_value()
        v = value is not None and value != 0
        return (v, self.mode)

    def clean(self):
        self.button.set_current_value(0)
        self.button.render()

    def describe(self) -> str:
        """
        Describe what the button does in plain English
        """
        a = [f"The representation turns ON or OFF a single LED light"]
        return "\n\r".join(a)


class ColoredLED(Representation):

    REPRESENTATION_NAME = "colored-led"
    REQUIRED_DECK_FEEDBACKS = DECK_FEEDBACK.COLORED_LED

    def __init__(self, button: "Button"):
        self._color = button._config.get(DECK_FEEDBACK.COLORED_LED.value, button.get_attribute("cockpit-color"))
        self.color = (128, 128, 256)
        Representation.__init__(self, button=button)

    def init(self):
        if type(self._color) == dict:  # @todo: does not currently work
            self.datarefs = self.button.scan_datarefs(self._color)
            if self.datarefs is not None and len(self.datarefs) > 0:
                logger.debug(f"button {self.button_name()}: adding datarefs {self.datarefs} for color")
        else:
            self.color = convert_color(self._color)

    def get_color(self, base: dict | None = None):
        """
        Compute color from formula/datarefs if any
        the color can be a formula but no formula in it.
        """
        if base is None:
            base = self._config
        color_str = base.get("color")
        if color_str is None:
            return self.color
        # Formula in text
        KW_FORMULA_STR = f"${{{CONFIG_KW.FORMULA.value}}}"  # "${formula}"
        hue = 0  # red
        if KW_FORMULA_STR in str(color_str):
            dataref_rpn = base.get(CONFIG_KW.FORMULA.value)
            if dataref_rpn is not None:
                hue = self.button.execute_formula(formula=dataref_rpn)
        else:
            hue = int(color_str)
            logger.warning(f"button {self.button_name()}: color contains {KW_FORMULA_STR} but no {CONFIG_KW.FORMULA.value} attribute found")

        color_rgb = colorsys.hsv_to_rgb((int(hue) % 360) / 360, 1, 1)
        self.color = tuple([int(255 * i) for i in color_rgb])  # type: ignore
        logger.debug(f"{color_str}, {hue}, {[(int(hue) % 360)/360,1,1]}, {color_rgb}, {self.color}")
        return self.color

    def render(self):
        color = self.get_color()
        logger.debug(f"{type(self).__name__}: {color}")
        return color

    def clean(self):
        logger.debug(f"{type(self).__name__}")
        self.button.set_current_value(0)
        self.button.render()

    def describe(self) -> str:
        """
        Describe what the button does in plain English
        """
        a = [f"The representation turns ON or OFF a single LED light and changes the color of the LED."]
        return "\n\r".join(a)
