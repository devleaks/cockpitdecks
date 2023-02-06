"""
Button display and rendering abstraction
"""
import logging
import re
import logging
import threading
import time
import yaml

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

    def is_valid(self) -> bool:
        return True

    def inspect(self):
        logger.info(f"{self.button.name}:{type(self).__name__}:")
        logger.info(f"\n{yaml.dump(self._config)}")

    def render(self):
        logger.debug(f"render: button {self.button.name}: {type(self).__name__} has no rendering")
        return None

    def has_label(self) -> bool:
        return self.label is not None

    def get_current_value(self):
        return self.button.get_current_value()

    def clean(self):
        logger.warning(f"clean: button {self.button.name}: no cleaning")
        pass


#
# ###############################
# ICON TYPE REPRESENTATION
#
#
class Icon(Representation):

    def __init__(self, config: dict, button: "Button"):
        Representation.__init__(self, config=config, button=button)

        page = self.button.page
        self.label = config.get("label")
        self.label_format = config.get("label-format")
        self.label_font = config.get("label-font", page.default_label_font)
        self.label_size = int(config.get("label-size", page.default_label_size))
        self.label_color = config.get("label-color", page.default_label_color)
        self.label_color = convert_color(self.label_color)
        self.label_position = config.get("label-position", "cm")
        if self.label_position[0] not in "lcr" or self.label_position[1] not in "tmb":
            logger.warning(f"__init__: button {self.button.name}: {type(self).__name__} invalid label position code {self.label_position}, using default")
            self.label_position = "cm"

        self.icon_color = config.get("icon-color", page.default_icon_color)
        self.icon = config.get("icon")

        deck = self.button.deck
        if self.icon is not None:  # 2.1 if supplied, use it
            self.icon = add_ext(self.icon, ".png")
            if self.icon not in deck.icons.keys():
                logger.warning(f"__init__: button {self.button.name}: {type(self).__name__}: icon not found {self.icon}")
                self.icon = None

        # If we have no icon, but an icon-color, we create a uniform color icon and store it.
        if self.icon is None:
            self.icon_color = config.get("icon-color", page.default_icon_color)
            if self.icon_color is not None:
                self.icon_color = convert_color(self.icon_color)
                self.icon = f"_default_{button.page.name}_{button.name}_icon.png"
                deck.icons[self.icon] = deck.create_icon_for_key(self.button, colors=self.icon_color)
                logger.warning(f"__init__: button {self.button.name}: {type(self).__name__}: created colored icon {self.icon}={self.icon_color}")

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

    def is_valid(self):
        if self.button is None:
            logger.warning(f"is_valid: button {self.button.name}: {type(self).__name__}: no button")
            return False
        if self.icon is not None:
            if self.icon not in self.button.deck.icons.keys():
                logger.warning(f"is_valid: button {self.button.name}: {type(self).__name__}: icon {self.icon} not in deck")
                return False
            return True
        if self.icon_color is not None:
            return True
        logger.warning(f"is_valid: button {self.button.name}: {type(self).__name__}: no icon and no icon color")
        return False

    def render(self):
        return self.get_image()

    def get_text_detail(self, config, which_text):
        text = self.button.get_text(config, which_text)
        text_format = config.get("label-format")

        page = self.button.page
        text_font = config.get(f"{which_text}-font", page.default_label_font)
        text_size = config.get(f"{which_text}-size", page.default_label_size)

        text_color = config.get(f"{which_text}-color", page.default_label_color)
        text_color = convert_color(text_color)

        text_position = config.get(f"{which_text}-position", "cm")
        if text_position[0] not in "lcr" or text_position[1] not in "tmb":
            logger.warning(f"get_text_detail: button {self.button.name}: {type(self).__name__}: invalid label position code {text_position}, using default")

        return text, text_format, text_font, text_color, text_size, text_position

    def get_font(self, fontname):
        """
        Helper function to get valid font, depending on button or global preferences
        """
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
                logger.warning(f"get_font: button {self.button.name}: {type(self).__name__}: button label font '{fontname}' not found")

        # 2. Tries deck default font
        if deck.default_label_font is not None and deck.default_label_font in fonts_available:
            logger.info(f"get_font: button {self.button.name}: {type(self).__name__}: using deck default font '{deck.default_label_font}'")
            return deck.cockpit.fonts[deck.default_label_font]
        else:
            logger.warning(f"get_font: button {self.button.name}: {type(self).__name__} deck default label font '{fontname}' not found")

        # 3. Tries streamdecks default font
        if deck.cockpit.default_label_font is not None and deck.cockpit.default_label_font in fonts_available:
            logger.info(f"get_font: button {self.button.name}: {type(self).__name__} using cockpit default font '{deck.cockpit.default_label_font}'")
            return deck.cockpit.fonts[deck.cockpit.default_label_font]
        logger.error(f"get_font: button {self.button.name}: {type(self).__name__} cockpit default label font not found, tried {fontname}, {deck.default_label_font}, {deck.cockpit.default_label_font}")
        return None

    def get_image_for_icon(self):
        image = None
        deck = self.button.deck
        if self.icon in deck.icons.keys():  # look for properly sized image first...
            logger.info(f"get_image_for_icon: button {self.button.name}: {type(self).__name__}: found {self.icon} in deck")
            image = deck.icons[self.icon]
        elif self.icon in deck.cockpit.icons.keys(): # then icon, but need to resize it if necessary
            logger.info(f"get_image_for_icon: button {self.button.name}: {type(self).__name__}: found {self.icon} in cockpit")
            image = deck.cockpit.icons[self.icon]
            image = deck.pil_helper.create_scaled_image("button", image)
        else:
            logger.warning(f"get_image_for_icon: button {self.button.name}: {type(self).__name__}: {self.icon} not found")
        return image

    def get_image(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        image = self.get_image_for_icon()
        if image is None:
            logger.warning(f"get_image: button {self.button.name}: {type(self).__name__} no image")
            return None

        # Add little check mark if not valid/fake
        if not self.is_valid() or self.button.has_option("placeholder"):
            image = image.copy()  # we will add text over it
            draw = ImageDraw.Draw(image)
            c = round(0.97 * image.width)  # % from edge
            s = round(0.1 * image.width)   # size
            pologon = ( (c, c), (c, c-s), (c-s, c) )  # lower right corner
            draw.polygon(pologon, fill="red", outline="white")

        return self.overlay_text(image, "label")

    def overlay_text(self, image, which_text):  # which_text = {label|text}
        draw = None
        # Add label if any

        text, text_format, text_font, text_color, text_size, text_position = self.get_text_detail(self._config, which_text)
        logger.warning(f"overlay_text: {text}")
        if text is not None:
            fontname = self.get_font(text_font)
            if fontname is None:
                logger.warning(f"overlay_text: no font, cannot overlay text")
            else:
                # logger.debug(f"overlay_text: font {fontname}")
                image = image.copy()  # we will add text over it
                draw = ImageDraw.Draw(image)
                font = ImageFont.truetype(fontname, text_size)
                inside = round(0.04 * image.width + 0.5)
                w = image.width / 2
                p = "m"
                a = "center"
                if text_position[0] == "l":
                    w = inside
                    p = "l"
                    a = "left"
                elif text_position[0] == "r":
                    w = image.width - inside
                    p = "r"
                    a = "right"
                h = image.height / 2
                if text_position[1] == "t":
                    h = inside + text_size / 2
                elif text_position[1] == "r":
                    h = image.height - inside - text_size / 2
                # logger.debug(f"overlay_text: position {(w, h)}")
                draw.multiline_text((w, h),  # (image.width / 2, 15)
                          text=text,
                          font=font,
                          anchor=p+"m",
                          align=a,
                          fill=text_color)
        return image

    def clean(self):
        """
        Removes icon from deck
        (@todo: Should create a button with no activation and icon representation that has
        default color/icon.)
        """
        icon = None
        deck = self.button.deck
        page = self.button.page
        color = deck.cockpit_color
        if page.empty_key_fill_icon in deck.icons.keys():
            icon = deck.icons[page.empty_key_fill_icon]
        elif page.empty_key_fill_color is not None:
            icon = deck.create_icon_for_key(self.button, colors=page.empty_key_fill_color)
        elif deck.cockpit_color is not None:
            icon = deck.create_icon_for_key(self.button, colors=deck.cockpit_color)

        if icon is not None:
            image = deck.pil_helper.to_native_format(deck.device, icon)
            deck.device.set_key_image(self.button._key, image)
        else:
            logger.warning(f"clean: button {self.button.name}: {type(self).__name__}: no fill icon")


class IconText(Icon):

    def __init__(self, config: dict, button: "Button"):
        Icon.__init__(self, config=config, button=button)

        self.text = config.get("text")
        # self.texts = config.get("texts")  # @todo later

    def get_image(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        image = super().get_image()
        return self.overlay_text(image, "text")


class IconSide(Representation):

    def __init__(self, config: dict, button: "Button"):
        Representation.__init__(self, config=config, button=button)

        self.labels = config.get("labels")  # multi-labels

    def is_dotted(self, label: str):
        # check dataref status
        # AirbusFBW/ALTmanaged, AirbusFBW/HDGmanaged,
        # AirbusFBW/SPDmanaged, and AirbusFBW/BaroStdCapt
        hack = "AirbusFBW/BaroStdCapt" if label.upper() == "QNH" else f"AirbusFBW/{label}managed"
        status = self.is_pushed()
        if hack in self.xp.all_datarefs.keys():
            # logger.debug(f"is_dotted: {hack} = {self.xp.all_datarefs[hack].value()}")
            status = self.xp.all_datarefs[hack].value() == 1
        else:
            logger.warning(f"is_dotted: button {self.name} dataref {hack} not found")
        return status



class MultiIcons(Icon):

    def __init__(self, config: dict, button: "Button"):
        Icon.__init__(self, config=config, button=button)

        self.multi_icons = config.get("multi-icons", [])
        if len(self.multi_icons) > 0:
            for i in range(len(self.multi_icons)):
                self.multi_icons[i] = add_ext(self.multi_icons[i], ".png")
                if self.multi_icons[i] not in self.button.deck.icons.keys():
                    logger.warning(f"__init__: button {self.button.name}: {type(self).__name__}: icon not found {self.multi_icons[i]}")

    def is_valid(self):
        return len(self.multi_icons) > 0 and super().is_valid()

    def num_icons(self):
        return len(self.multi_icons)

    def render(self):
        value = self.get_current_value()
        if value is None:
            logger.warning(f"render: button {self.button.name}: {type(self).__name__}: no current value")
            return None

        if self.num_icons() > 0:
            if  value >= 0 and value < self.num_icons():
                self.icon = self.multi_icons[value]
            else:
                self.icon = self.multi_icons[value % self.num_icons()]
            return super().render()
        else:
            logger.warning(f"render: button {self.button.name}: {type(self).__name__}: icon not found {value}/{self.num_icons()}")
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
        value = self.get_current_value()
        return value is not None and value != 0

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
        value = self.get_current_value()
        return value is not None and value !=0


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
        return self.get_current_value() < maxval


    def render(self):
        maxval = 7 if self.mode == LED_MODE.SPREAD else 13
        v = min(int(self.get_current_value()), maxval)
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
    "text": IconText,
    "icon-text": IconText,
    "icon-color": Icon,
    "multi-icons": MultiIcons,
    "icon-animation": IconAnimation,
    "side": IconSide,
    "led": LED,
    "colored-led": ColoredLED,
    "multi-leds": MultiLEDs,
    "annunciator": Annunciator
}
