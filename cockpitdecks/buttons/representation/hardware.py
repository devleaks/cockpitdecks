"""
Special represenations for web decks, to draw a "hardware" button
"""

import logging

from PIL import Image

from .icon import IconBase

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

NO_ICON = "no-icon"


# ####################################################
#
# SPECIAL VIRTUAL WEB DECKS REPRESENTATIONS FOR «HARDWARE» PARTS (non images)
#
#
# GENERIC
#
class HardwareRepresentation(IconBase):
    """Uniform color or texture icon

    Attributes:
        REPRESENTATION_NAME: "virtual-encoder"
    """

    REPRESENTATION_NAME = "hardware-icon"

    def __init__(self, button: "Button"):
        button._config[NO_ICON] = True
        IconBase.__init__(self, button=button)

        self.hardware = self.button._definition.hardware_representation
        self.highlight_color = self.hardware.get("highlight-color", "#ffffff10")
        self.flash_color = self.hardware.get("flash-color", "#0f80ffb0")
        self.flash_duration = self.hardware.get("flash-duration", 100)  # msec

        dimension = self.button._definition.dimension
        if type(dimension) in (int, float):
            self.radius = dimension
            self.width = 2 * dimension
            self.height = 2 * dimension
        else:
            self.radius = 0
            self.width = dimension[0]
            self.height = dimension[1]

    def get_meta(self):
        return {
            "name": self.REPRESENTATION_NAME,
            "hardware": self.hardware,
            "highlight-color": self.highlight_color,
            "flash-color": self.flash_color,
            "flash-duration": self.flash_duration,
        }


class VirtualEncoder(HardwareRepresentation):
    """Uniform color or texture icon

    Attributes:
        REPRESENTATION_NAME: "virtual-encoder"
    """

    REPRESENTATION_NAME = "virtual-encoder"

    def __init__(self, button: "Button"):
        HardwareRepresentation.__init__(self, button=button)

        self.rotation = self.hardware.get("rotation-start", 0)
        self.rotation_step = self.hardware.get("rotation-step", 10)
        self.knob_fill_color = self.hardware.get("knob-fill-color", "black")
        self.knob_stroke_color = self.hardware.get("knob-stroke-color", "silver")
        self.knob_stroke_width = self.hardware.get("knob-stroke-width", 1)
        self.mark_fill_color = self.hardware.get("mark-fill-color", "silver")
        self.mark_size = self.hardware.get("mark-size", 1)

    def get_image(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        image, draw = self.double_icon(width=2 * self.radius, height=2 * self.radius)
        # knob
        draw.ellipse(
            [0, 0] + [2 * self.radius, 2 * self.radius],
            fill=self.knob_fill_color,
            outline=self.knob_stroke_color,
            width=self.knob_stroke_width,
        )
        # marker
        if type(self.mark_size) is int:
            draw.ellipse(
                [self.knob_stroke_width + int(self.mark_size / 2), self.radius - int(self.mark_size / 2)]
                + [self.knob_stroke_width + 3 * int(self.mark_size / 2), self.radius + int(self.mark_size / 2)],
                fill=self.mark_fill_color,
            )
        else:
            draw.ellipse(
                [self.knob_stroke_width + int(self.mark_size[0] / 2), self.radius - int(self.mark_size[1] / 2)]
                + [self.knob_stroke_width + 3 * int(self.mark_size[0] / 2), self.radius + int(self.mark_size[1] / 2)],
                fill=self.mark_fill_color,
            )
        # rotate
        self.rotation = self.button._activation._turns * self.rotation_step
        return image.rotate(self.rotation - 90)

    def describe(self) -> str:
        return "The representation places a rotating virtual enconder."


class VirtualLED(HardwareRepresentation):
    """Uniform color or texture icon, arbitrary size

    Attributes:
        REPRESENTATION_NAME: "virtual-xtm-led"
    """

    REPRESENTATION_NAME = "virtual-led"

    def __init__(self, button: "Button"):
        HardwareRepresentation.__init__(self, button=button)

        self.color = self.hardware.get("color", (207, 229, 149))
        self.off_color = self.hardware.get("off-color", "ghostwhite")

    def get_image(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        color = self.color if self.button.value != 0 else self.off_color
        image = Image.new(mode="RGBA", size=(self.width, self.height), color=color)
        return image

    def describe(self) -> str:
        return "The representation return a uniform color icon at the position of the hardware led on or off."
