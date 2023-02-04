"""
Button display and rendering abstraction
"""
import logging
import re
import logging
import threading
import time

from PIL import ImageDraw, ImageFont

from .XTouchMini.Devices.xtouchmini import LED_MODE
from .color import convert_color


logger = logging.getLogger("Representation")
# logger.setLevel(logging.DEBUG)


def add_ext(name: str, ext: str):
    rext = ext if not ext.startswith(".") else ext[1:]  # remove leading period from extension if any
    narr = name.split(".")
    if len(narr) < 2:  # has no extension
        return name + "." + rext
    nameext = narr[-1]
    if nameext.lower() == rext.lower():
        return ".".join(narr[:-1]) + "." + rext  # force extension to what is should
    else:  # did not finish with extention, so add it
        return name + "." + rext  # force extension to what is should


# ##########################################
# REPRESENTATION
#
class Representation:
    """
    Base class for all representations
    """
    def __init__(self, config: dict, button: "Button"):
        self._config = config
        self.button = button



        self.button.register_representation(self)

    def is_valid(self) -> bool:
        return True

    def render(self):
        logger.debug(f"render: {type(self).__name__} has no rendering")
        return None

    def has_label(self) -> bool:
        return self.label is not None

    def set_current_value(self, value):
        self.current_value = value
#
# ###############################
# ICON TYPE REPRESENTATION
#
#
class Icon(Representation):

    def __init__(self, config: dict, button: "Button"):
        Representation.__init__(self, config=config, button=button)

        deck = self.button.deck
        self.label = config.get("label")
        self.label_format = config.get("label-format")
        self.label_font = config.get("label-font", deck.default_label_font)
        self.label_size = int(config.get("label-size", deck.default_label_size))
        self.label_color = config.get("label-color", deck.default_label_color)
        self.label_color = convert_color(self.label_color)
        self.label_position = config.get("label-position", "cm")
        if self.label_position[0] not in "lcr" or self.label_position[1] not in "tmb":
            logger.warning(f"__init__: button {self.name}: invalid label position code {self.label_position}, using default")
            self.label_position = "cm"

        self.icon_color = config.get("icon-color", button.page.default_icon_color)
        self.icon = config.get("icon")
        deck = self.button.deck

        if self.icon is not None:  # 2.1 if supplied, use it
            self.icon = add_ext(self.icon, ".png")
            if self.icon not in deck.icons.keys():
                logger.warning(f"__init__: {type(self).__name__}: icon not found {self.icon}")
                self.icon = None

        if self.icon is None:
            self.icon_color = config.get("icon-color")
            if self.icon_color is not None:
                self.icon = f"_default_{self.page.name}_{self.name}_icon.png"
                deck.create_icon(self.icon, self.icon_color)
                logger.warning(f"__init__: {type(self).__name__}: create colored icon {self.icon}={self.icon_color}")

        # self.icon_color = convert_color(self.icon_color)
        # # the icon size varies for center "buttons" and left and right side "buttons".
        # if type(self.deck.device).__name__.startswith("StreamDeck"):
        #     imgtype = self.deck.device
        # else:
        #     imgtype = "button" if self.index not in ["left", "right"] else self.index
        # # self.default_icon_image = self.deck.pil_helper.create_image(deck=imgtype, background=self.icon_color)
        # if self.deck.pil_helper is not None:
        #     self.default_icon_image = self.deck.pil_helper.create_image(deck=imgtype, background=self.icon_color)
        #     self.default_icon = f"_default_{self.page.name}_{self.name}_icon.png"
        # # self.default_icon = add_ext(self.default_icon, ".png")
        # # logger.debug(f"__init__: button {self.name}: creating icon '{self.default_icon}' with color {self.icon_color}")
        # # register it globally
        #     self.deck.cockpit.icons[self.default_icon] = self.default_icon_image
        # # add it to icon for this deck too since it was created at proper size
        #     self.deck.icons[self.default_icon] = self.default_icon_image
        #     self.icon = self.default_icon

    def render(self):
        return self.icon

    def get_font(self, fontname = None):
        """
        Helper function to get valid font, depending on button or global preferences
        """
        if fontname is None:
            fontname = self.label_font
        deck = self.button.deck
        fonts_available = deck.cockpit.fonts.keys()


        # 1. Tries button specific font
        if fontname is not None:
            narr = fontname.split(".")
            if len(narr) < 2:  # has no extension
                fontname = add_ext(fontname, ".ttf")  # should also try .otf

            if fontname in fonts_available:
                return deck.cockpit.fonts[fontname]
            else:
                logger.warning(f"get_font: button {type(self).__name__}: button label font '{fontname}' not found")

        # 2. Tries deck default font
        if deck.default_label_font is not None and deck.default_label_font in fonts_available:
            logger.info(f"get_font: button {type(self).__name__}: using deck default font '{deck.default_label_font}'")
            return deck.cockpit.fonts[deck.default_label_font]
        else:
            logger.warning(f"get_font: button {type(self).__name__}: deck default label font '{fontname}' not found")

        # 3. Tries streamdecks default font
        if deck.cockpit.default_label_font is not None and deck.cockpit.default_label_font in fonts_available:
            logger.info(f"get_font: button {type(self).__name__}: using cockpit default font '{deck.cockpit.default_label_font}'")
            return deck.cockpit.fonts[deck.cockpit.default_label_font]
        logger.error(f"get_font: button {type(self).__name__}: cockpit default label font not found, tried {fontname}, {deck.default_label_font}, {deck.cockpit.default_label_font}")
        return None

    def get_image_for_icon(self):
        image = None
        icon = self.render()
        deck = self.button.deck
        if icon in deck.icons.keys():  # look for properly sized image first...
            image = deck.icons[icon]
        elif icon in deck.cockpit.icons.keys(): # then icon, but need to resize it if necessary
            image = deck.cockpit.icons[icon]
            image = deck.pil_helper.create_scaled_image("button", image)
        return image

    def get_image(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        image = self.get_image_for_icon()

        if image is not None:
            draw = None
            # Add label if any
            label = self.button.get_label()
            if label is not None:
                fontname = self.get_font()
                if fontname is None:
                    logger.warning(f"get_image: no font, cannot overlay label")
                else:
                    # logger.debug(f"get_image: font {fontname}")
                    image = image.copy()  # we will add text over it
                    draw = ImageDraw.Draw(image)
                    font = ImageFont.truetype(fontname, self.label_size)
                    inside = round(0.04 * image.width + 0.5)
                    w = image.width / 2
                    p = "m"
                    a = "center"
                    if self.label_position[0] == "l":
                        w = inside
                        p = "l"
                        a = "left"
                    elif self.label_position[0] == "r":
                        w = image.width - inside
                        p = "r"
                        a = "right"
                    h = image.height / 2
                    if self.label_position[1] == "t":
                        h = inside + self.label_size / 2
                    elif self.label_position[1] == "r":
                        h = image.height - inside - self.label_size / 2
                    # logger.debug(f"get_image: position {(w, h)}")
                    draw.multiline_text((w, h),  # (image.width / 2, 15)
                              text=label,
                              font=font,
                              anchor=p+"m",
                              align=a,
                              fill=self.label_color)
            # Add little check mark if not valid/fake
            if not self.is_valid() or self.has_option("placeholder"):
                if draw is None:  # no label
                    image = image.copy()  # we will add text over it
                    draw = ImageDraw.Draw(image)
                c = round(0.97 * image.width)  # % from edge
                s = round(0.1 * image.width)   # size
                pologon = ( (c, c), (c, c-s), (c-s, c) )  # lower right corner
                draw.polygon(pologon, fill="red", outline="white")
            return image
        else:
            logger.warning(f"get_image: button {self.name}: icon {self.key_icon} not found")
            # logger.debug(f"{deck.icons.keys()}")
        return None

    def clean(self):
        return None


class IconSide(Representation):

    def __init__(self, config: dict, button: "Button"):
        Representation.__init__(self, config=config, button=button)

        self.labels = config.get("labels")  # multi-labels



class MultiIcons(Icon):

    def __init__(self, config: dict, button: "Button"):
        Icon.__init__(self, config=config, button=button)

        self.multi_icons = config.get("multi-icons", [])
        if len(self.multi_icons) > 0:
            for i in range(len(self.multi_icons)):
                self.multi_icons[i] = add_ext(self.multi_icons[i], ".png")
                if self.multi_icons[i] not in self.button.deck.icons.keys():
                    logger.warning(f"__init__: {type(self).__name__}: icon not found {self.multi_icons[i]}")

    def is_valid(self):
        return len(self.multi_icons) > 0 and super().is_valid()

    def num_icons(self):
        return len(self.multi_icons)

    def render(self):
        if self.num_icons() > 0 and self.current_value < self.num_icons():
            return self.multi_icons[self.current_value]
        else:
            logger.warning(f"render: {type(self).__name__}: icon not found {self.current_value}/{self.num_icons()}")
        return None

class IconAnimation(MultiIcons):

    def __init__(self, config: dict, button: "Button"):
        MultiIcons.__init__(self, config=config, button=button)

        self.speed = float(config("animation-speed", 1))

        # Internal variables
        self.counter = 0
        self.thread = None
        self.running = False
        self.finished = None

    def loop(self):
        self.finished = threading.Event()
        while self.running:
            self.render()
            self.counter = self.counter + 1
            time.sleep(self.speed)
        self.finished.set()

    def should_run(self) -> bool:
        """
        Check conditions to animate the icon.
        """
        return self.current_value is not None and self.current_value != 0

    def anim_start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.loop)
            self.thread.name = f"ButtonAnimate::loop({self.name})"
            self.thread.start()
        else:
            logger.warning(f"anim_start: button {self.name}: already started")

    def anim_stop(self):
        if self.running:
            self.running = False
            if not self.finished.wait(timeout=2*self.speed):
                logger.warning(f"anim_stop: button {self.name}: did not get finished signal")
            self.render()
        else:
            logger.debug(f"anim_stop: button {self.name}: already stopped")

    def clean(self):
        self.anim_stop()

    def render(self):
        if self.is_valid():
            return self.multi_icons[(self.counter % len(self.multi_icons))]
        return None

#
# ###############################
# LED TYPE REPRESENTATION
#
#
class LED(Representation):

    def __init__(self, config: dict, button: "Button"):
        Representation.__init__(self, config=config, button=button)

    def render(self):
        return self.current_value is not None and self.current_value !=0


class ColoredLED(Representation):

    def __init__(self, config: dict, button: "Button"):
        Representation.__init__(self, config=config, button=button)

        self.color = convert_color("black")  # color should hold a tuple of 3 or 4 int or float

    def render(self):
        return self.color



class MultiLEDs(Representation):
    """
    Ring of 13 LEDs surrounding X-Touch Mini encoders
    """

    def __init__(self, config: dict, button: "Button"):
        Representation.__init__(self, config=config, button=button)

        self.mode = config.get("led-mode", LED_MODE.SINGLE)

    def is_valid(self):
        maxval = 7 if self.mode == LED_MODE.SPREAD else 13
        return self.current_value < maxval


    def render(self):
        maxval = 7 if self.mode == LED_MODE.SPREAD else 13
        v = min(int(self.current_value), maxval)
        return (v, self.mode.value)

#
# ###############################
# ANNUNCIATOR TYPE REPRESENTATION
#
#
class Annunciator(Representation):

    def __init__(self, config: dict, button: "Button"):
        Representation.__init__(self, config=config, button=button)



#
# ###############################
# REPRESENTATIONS
#
#
REPRESENTATIONS = {
    "none": Representation,
    "icon": Icon,
    "multi-icons": MultiIcons,
    "icon-animation": IconAnimation,
    "side": IconSide,
    "led": LED,
    "colored-led": ColoredLED,
    "multi-leds": MultiLEDs,
    "annunciator": Annunciator
}
