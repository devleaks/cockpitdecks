"""
All representations for Icon/image based.
"""

import logging
import math

from PIL import Image, ImageDraw, ImageFont

try:
    from XTouchMini.Devices.xtouchmini import LED_MODE

    class VirtualXTMEncoderLED(VirtualEncoder):
        """Uniform color or texture icon, no square!

        Attributes:
            REPRESENTATION_NAME: "virtual-xtm-encoderled"
        """

        REPRESENTATION_NAME = "virtual-xtm-encoderled"

        def __init__(self, button: "Button"):
            VirtualEncoder.__init__(self, button=button)

            self.width = 2 * self.radius  # final dimension, 2 x radius of circle
            self.height = self.width  # force final image to be a square icon with. circle in it

            self.ltot = int(ICON_SIZE / 2)  # button will be created in ICON_SIZE x ICON_SIZE
            self.lext = 120
            self.lint = 84
            self.lstart = -130  # angles
            self.lend = -self.lstart
            self.lwidth = 12  # led
            self.lheight = 20
            self.rounded_corder = int(self.lwidth / 2)

            self.color = self.hardware.get("color", "gold")
            self.off_color = self.hardware.get("off-color", (30, 30, 30))

            self.led_count = 13
            self.mackie = True  # cannot change it for xtouchmini package (does not work otherwise)

        def is_on(self, led, value, mode) -> bool:
            # class LED_MODE(Enum):
            #     SINGLE = 0
            #     TRIM = 1
            #     FAN = 2
            #     SPREAD = 3
            led_count1 = self.led_count - 1
            led_limit = led_count1 - 1 if self.mackie else led_count1  # last led to turn on

            if self.mackie and led in [0, led_count1]:  # LED 0 and 12 never used in Mackie mode...
                return False

            if value <= 0:
                return False

            if value > led_limit:
                value = led_limit

            if mode == LED_MODE.SINGLE:
                return led == value
            if mode == LED_MODE.FAN:
                return led <= value
            middle = math.floor(self.led_count / 2)
            if mode == LED_MODE.SPREAD:
                if value > middle:
                    value = middle
                value = value - 1
                return middle - value <= led <= middle + value
            # LED_MODE.TRIM
            if led <= middle:
                return value <= led <= middle
            return middle <= led <= value

        def get_image(self):
            value, mode = self.button.get_representation()
            center = (self.ltot, self.ltot)

            tl = (self.ltot - self.lwidth / 2, self.ltot - self.lext)
            br = (self.ltot + self.lwidth / 2, self.ltot - self.lint)
            image = Image.new(mode="RGBA", size=(ICON_SIZE, ICON_SIZE), color=TRANSPARENT_PNG_COLOR)

            # Add surrounding leds
            image_on = Image.new(mode="RGBA", size=(ICON_SIZE, ICON_SIZE), color=TRANSPARENT_PNG_COLOR)
            one_mark_on = ImageDraw.Draw(image_on)
            one_mark_on.rounded_rectangle(tl + br, radius=self.rounded_corder, fill=self.color, outline=self.off_color, width=1)

            # Add bleed
            # s = 2
            # tl = [x-s for x in tl]
            # br = [x+s for x in br]
            image_off = Image.new(mode="RGBA", size=(ICON_SIZE, ICON_SIZE), color=TRANSPARENT_PNG_COLOR)
            one_mark_off = ImageDraw.Draw(image_off)
            one_mark_off.rounded_rectangle(tl + br, radius=self.rounded_corder, fill=self.off_color, outline=self.off_color, width=1)

            step_angle = (self.lend - self.lstart) / (self.led_count - 1)
            angle = self.lend
            for i in range(self.led_count):
                this_led = image_on.copy() if self.is_on(led=i, value=value, mode=mode) else image_off.copy()
                this_led = this_led.rotate(angle, center=center)
                angle = angle - step_angle
                image.alpha_composite(this_led)

            # Resize
            image = image.resize((self.width, self.height))
            # paste encoder in middle
            self.radius = 27
            encoder = super().get_image()  # paste in center
            image.alpha_composite(encoder, (int(image.width / 2 - encoder.width / 2), int(image.height / 2 - encoder.height / 2)))
            return image

        def describe(self) -> str:
            return "The representation places a uniform color icon for X-Touch Mini Mackie mode."

except:
    pass

from cockpitdecks import CONFIG_KW, DECK_KW, DECK_FEEDBACK, ICON_SIZE
from cockpitdecks.resources.color import (
    TRANSPARENT_PNG_COLOR,
    convert_color,
)
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
class HardwareIcon(IconBase):
    """Uniform color or texture icon

    Attributes:
        REPRESENTATION_NAME: "virtual-encoder"
    """

    REPRESENTATION_NAME = "hardware-icon"

    def __init__(self, button: "Button"):
        button._config[NO_ICON] = True
        IconBase.__init__(self, button=button)

        self.hardware = self.button._def.hardware_representation
        self.highlight_color = self.hardware.get("highlight-color", "#ffffff10")
        self.flash_color = self.hardware.get("flash-color", "#0f80ffb0")
        self.flash_duration = self.hardware.get("flash-duration", 100)  # msec

        dimension = self.button._def.dimension
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


class VirtualEncoder(HardwareIcon):
    """Uniform color or texture icon

    Attributes:
        REPRESENTATION_NAME: "virtual-encoder"
    """

    REPRESENTATION_NAME = "virtual-encoder"

    def __init__(self, button: "Button"):
        HardwareIcon.__init__(self, button=button)

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


class VirtualLED(HardwareIcon):
    """Uniform color or texture icon, arbitrary size

    Attributes:
        REPRESENTATION_NAME: "virtual-xtm-led"
    """

    REPRESENTATION_NAME = "virtual-led"

    def __init__(self, button: "Button"):
        HardwareIcon.__init__(self, button=button)

        self.color = self.hardware.get("color", (207, 229, 149))
        self.off_color = self.hardware.get("off-color", "ghostwhite")

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
        return "The representation return a uniform color icon at the position of the hardware led on or off."


# ####################################################
#
# X-TOUCH MINI
#
class VirtualXTMLED(VirtualLED):
    """Uniform color or texture icon, arbitrary size

    Attributes:
        REPRESENTATION_NAME: "virtual-xtm-led"
    """

    REPRESENTATION_NAME = "virtual-xtm-led"

    def __init__(self, button: "Button"):
        VirtualLED.__init__(self, button=button)

        self.color = self.hardware.get("color", (207, 229, 149))
        self.off_color = self.hardware.get("off-color", "ghostwhite")

    def describe(self) -> str:
        return "The representation places a uniform color icon for X-Touch Mini buttons."


class VirtualXTMMCLED(VirtualLED):
    """Uniform color or texture icon, arbitrary size

    Attributes:
        REPRESENTATION_NAME: "virtual-xtm-mcled"
    """

    REPRESENTATION_NAME = "virtual-xtm-mcled"

    def __init__(self, button: "Button"):
        VirtualLED.__init__(self, button=button)

        self.color = self.hardware.get("color", "gold")
        self.off_color = self.hardware.get("off-color", (30, 30, 30))

    def describe(self) -> str:
        return "The representation places a specific Mackie Mode led for X-Touch Mini encoders."


# ####################################################
#
# STREAMDECK
#
class VirtualSDNeoLED(VirtualLED):
    """Uniform color or texture icon, arbitrary size

    Attributes:
        REPRESENTATION_NAME: "virtual-xtm-mcled"
    """

    REPRESENTATION_NAME = "virtual-sd-neoled"

    def __init__(self, button: "Button"):
        VirtualLED.__init__(self, button=button)

        self.color = self.hardware.get("color", "lime")
        self.off_color = self.hardware.get("off-color", "silver")

    def describe(self) -> str:
        return "The representation places a specific led for Stream Deck Neo."


# ####################################################
#
# LOUPEDECKLIVE
#
class VirtualLLColoredButton(HardwareIcon):
    """Uniform color or texture icon

    Attributes:
        REPRESENTATION_NAME: "virtual-ll-coloredbutton"
    """

    REPRESENTATION_NAME = "virtual-ll-coloredbutton"

    def __init__(self, button: "Button"):
        HardwareIcon.__init__(self, button=button)

        self.knob_fill_color = self.hardware.get("knob-fill-color", "#21211f")
        self.knob_stroke_color = self.hardware.get("knob-stroke-color", "black")
        self.knob_stroke_width = self.hardware.get("knob-stroke-width", 1)

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
            font = self.get_font(self.get_attribute("font"), int(self.radius))  # (standard font)
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
