"""
All representations for Icon/image based.
"""

import logging

from PIL import Image, ImageDraw, ImageFont

from cockpitdecks.resources.color import (
    TRANSPARENT_PNG_COLOR,
    convert_color,
    has_ext,
    add_ext,
    DEFAULT_COLOR,
)
from cockpitdecks import CONFIG_KW, DECK_KW, DECK_FEEDBACK
from .icon import Icon

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

DEFAULT_VALID_TEXT_POSITION = "cm"  # text centered on icon (center, middle)
NO_ICON = "no-icon"


# ####################################################
#
# SPECIAL VIRTUAL WEB DECKS REPRESENTATIONS
#
#
# X-TOUCH MINI
#
class VirtualXTMLED(Icon):
    """Uniform color or texture icon, arbitrary size

    Attributes:
        REPRESENTATION_NAME: "virtual-xtm-led"
    """

    REPRESENTATION_NAME = "virtual-xtm-led"

    def __init__(self, config: dict, button: "Button"):
        config[NO_ICON] = True
        Icon.__init__(self, config=config, button=button)
        self.width = self.button._def.dimension[0]
        self.height = self.button._def.dimension[1]
        self.color = "palegoldenrod"
        self.off_color = "back"

    def get_image(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        color = self.color if self.button.get_current_value() != 0 else self.off_color
        image = Image.new(mode="RGBA", size=(self.width, self.height), color=color)
        return image

    def describe(self) -> str:
        return "The representation places a uniform color icon for X-Touch Mini buttons."


class VirtualXTMMCLED(VirtualXTMLED):
    """Uniform color or texture icon, arbitrary size

    Attributes:
        REPRESENTATION_NAME: "virtual-xtm-mcled"
    """

    REPRESENTATION_NAME = "virtual-xtm-mcled"

    def __init__(self, config: dict, button: "Button"):
        VirtualXTMLED.__init__(self, config=config, button=button)
        self.color = "green"

    def describe(self) -> str:
        return "The representation places a specific encoder led arragement for X-Touch Mini encoders."


class VirtualXTMEncoderLED(Icon):
    """Uniform color or texture icon, no square!

    Attributes:
        REPRESENTATION_NAME: "virtual-xtm-encoderled"
    """

    REPRESENTATION_NAME = "virtual-xtm-encoderled"

    def __init__(self, config: dict, button: "Button"):
        config[NO_ICON] = True
        Icon.__init__(self, config=config, button=button)
        self.width = 0
        self.height = 0
        self.color = convert_color("white")

    def get_image(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        image = Image.new(mode="RGBA", size=(self.width, self.height), color=self.color)
        return image

    def describe(self) -> str:
        return "The representation places a uniform color icon for X-Touch Mini Mackie mode."


#
# LOUPEDECKLIVE
#
class VirtualLLColoredButton(Icon):
    """Uniform color or texture icon

    Attributes:
        REPRESENTATION_NAME: "virtual-ll-coloredbutton"
    """

    REPRESENTATION_NAME = "virtual-ll-coloredbutton"

    def __init__(self, config: dict, button: "Button"):
        config[NO_ICON] = True
        Icon.__init__(self, config=config, button=button)
        self.radius = self.button._def.dimension
        self.knob_fill_color = "black"
        self.knob_stroke_color = "white"
        self.knob_stroke_width = 1

        self.number = int(self.button.num_index)  # static
        self.number_color = self.button._representation.render()

    def get_image(self):
        image = Image.new(mode="RGBA", size=(2 * self.radius, 2 * self.radius), color=TRANSPARENT_PNG_COLOR)
        draw = ImageDraw.Draw(image)
        # knob
        draw.ellipse(
            [1, 1] + [2 * self.radius - 1, 2 * self.radius - 1],
            fill=self.knob_fill_color,
            outline=self.knob_stroke_color,
            width=self.knob_stroke_width,
        )
        # marker
        self.number_color = self.button._representation.render()
        if self.number == 0:  # special marker for 0
            size = int(self.radius * 0.9)
            draw.ellipse(
                [self.radius - int(size / 2), self.radius - int(size / 2)] + [self.radius + int(size / 2), self.radius + int(size / 2)],
                outline=self.number_color,
                width=2,
            )
            size = 4
            draw.ellipse(
                [self.radius - int(size / 2), self.radius - int(size / 2)] + [self.radius + int(size / 2), self.radius + int(size / 2)], fill=self.number_color
            )
        else:
            font = self.get_font("DIN", int(self.radius))  # (standard font)
            draw.text(
                (self.radius, self.radius),
                text=str(self.number),
                fill=self.number_color,
                font=font,
                anchor="mm",
                align="center",
            )
        return image

    def describe(self) -> str:
        return "The representation places a color button with number for LoupedeckLive colored button."


#
# GENERIC
#
class VirtualEncoder(Icon):
    """Uniform color or texture icon

    Attributes:
        REPRESENTATION_NAME: "virtual-encoder"
    """

    REPRESENTATION_NAME = "virtual-encoder"

    def __init__(self, config: dict, button: "Button"):
        config[NO_ICON] = True
        Icon.__init__(self, config=config, button=button)
        self.radius = self.button._def.dimension
        self.color = "white"
        self.rotation = 0
        self.rotation_step = 10
        self.knob_fill_color = "black"
        self.knob_stroke_color = "peachpuff"
        self.knob_stroke_width = 2
        self.mark_fill_color = "white"

    def get_image(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        image = Image.new(mode="RGBA", size=(2 * self.radius, 2 * self.radius), color=TRANSPARENT_PNG_COLOR)
        draw = ImageDraw.Draw(image)
        # knob
        draw.ellipse(
            [0, 0] + [2 * self.radius, 2 * self.radius],
            fill=self.knob_fill_color,
            outline=self.knob_stroke_color,
            width=self.knob_stroke_width,
        )
        # marker
        size = 4
        draw.ellipse(
            [self.knob_stroke_width + int(size / 2), self.radius - int(size / 2)] + [self.knob_stroke_width + 3 * int(size / 2), self.radius + int(size / 2)],
            fill=self.mark_fill_color,
        )
        # rotate
        self.rotation = self.button._activation._turns * self.rotation_step
        return image.rotate(self.rotation)

    def describe(self) -> str:
        return "The representation places a rotating virtual enconder."
