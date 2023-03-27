"""
Button display and rendering abstraction
"""
import logging
import re
import logging
import threading
import time
from ruamel.yaml import YAML

from PIL import ImageDraw, ImageFont

from XTouchMini.Devices.xtouchmini import LED_MODE
from .color import convert_color, is_integer, has_ext, add_ext
from .constant import DEFAULT_LABEL_POSITION

logger = logging.getLogger("Representation")
# logger.setLevel(logging.DEBUG)


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
        self._sound = config.get("vibrate")
        self.datarefs = None

    def button_name(self):
        return self.button.name if self.button is not None else 'no button'

    def inspect(self, what: str = None):
        logger.info(f"{self.button_name()}:{type(self).__name__}:")
        logger.info(f"is valid: {self.is_valid()}")

    def is_valid(self):
        if self.button is None:
            logger.warning(f"is_valid: representation {type(self).__name__} has no button")
            return False
        return True

    def get_datarefs(self) -> list:
        return []

    def get_current_value(self):
        return self.button.get_current_value()

    def get_status(self):
        return {
            "representation_type": type(self).__name__
        }

    def render(self):
        logger.debug(f"render: button {self.button_name()}: {type(self).__name__} has no rendering")
        return None

    def vibrate(self):
        if self._sound is not None:
            self.button.deck._vibrate(self._sound)

    def clean(self):
        # logger.warning(f"clean: button {self.button_name()}: no cleaning")
        pass

    def describe(self):
        return "The button does not produce any output."

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
        self.label_position = config.get("label-position", DEFAULT_LABEL_POSITION)
        if self.label_position[0] not in "lcr" or self.label_position[1] not in "tmb":
            logger.warning(f"__init__: button {self.button_name()}: {type(self).__name__} invalid label position code {self.label_position}, using default")
            self.label_position = DEFAULT_LABEL_POSITION

        self.icon_color = config.get("icon-color", page.default_icon_color)
        self.icon = config.get("icon")

        deck = self.button.deck
        if self.icon is not None:  # 2.1 if supplied, use it
            self.icon = add_ext(self.icon, ".png")
            if self.icon not in deck.icons.keys():
                logger.warning(f"__init__: button {self.button_name()}: {type(self).__name__}: icon not found {self.icon}")
                self.icon = None

        # If we have no icon, but an icon-color, we create a uniform color icon and store it.
        if self.icon is None:
            self.mk_uniform_icon()

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

    def mk_uniform_icon(self):
        deck = self.button.deck
        if self.icon_color is None:
            self.icon_color = deck.cockpit_color
            logger.debug(f"mk_uniform_icon: button {self.button_name()}: {type(self).__name__}: no icon color, using cockpit color {self.icon_color}")
        self.icon_color = convert_color(self.icon_color)
        self.icon = f"_default_{self.button.page.name}_{self.button_name()}_icon.png"
        deck.icons[self.icon] = deck.create_icon_for_key(self.button, colors=self.icon_color)
        logger.debug(f"mk_uniform_icon: button {self.button_name()}: {type(self).__name__}: created colored icon {self.icon}={self.icon_color}")

    def is_valid(self):
        if super().is_valid():  # so there is a button...
            if self.icon is not None:
                if self.icon not in self.button.deck.icons.keys():
                    logger.warning(f"is_valid: button {self.button_name()}: {type(self).__name__}: icon {self.icon} not in deck")
                    return False
                return True
            if self.icon_color is not None:
                return True
            logger.warning(f"is_valid: button {self.button_name()}: {type(self).__name__}: no icon and no icon color")
        return False

    def render(self):
        return self.get_image()

    def get_text_detail(self, config, which_text):
        DEFAULT_TEXT_POSITION = "cm"  # text centered on icon
        text = self.button.get_text(config, which_text)
        text_format = config.get(f"{which_text}-format")

        page = self.button.page
        text_font = config.get(f"{which_text}-font", page.default_label_font)
        text_size = config.get(f"{which_text}-size", page.default_label_size)
        text_color = config.get(f"{which_text}-color", page.default_label_color)
        text_color = convert_color(text_color)
        text_position = config.get(f"{which_text}-position", DEFAULT_LABEL_POSITION if which_text == "label" else DEFAULT_TEXT_POSITION)
        if text_position[0] not in "lcr" or text_position[1] not in "tmb":
            logger.warning(f"get_text_detail: button {self.button_name()}: {type(self).__name__}: invalid label position code {text_position}, using default")

        return text, text_format, text_font, text_color, text_size, text_position

    def get_font(self, fontname):
        """
        Helper function to get valid font, depending on button or global preferences
        """
        page = self.button.page
        deck = self.button.deck
        cockpit = deck.cockpit
        all_fonts = cockpit.fonts
        fonts_available = list(all_fonts.keys())
        this_button = f"{self.button_name()}: {type(self).__name__}"

        def try_ext(fn):
            if fn is not None:
                if has_ext(fn, ".ttf") or has_ext(fn, ".otf"):
                    if fn in fonts_available:
                        return all_fonts[fn]
                f1 = add_ext(fn, ".ttf")
                if f1 in fonts_available:
                    return all_fonts[f1]
                f2 = add_ext(fn, ".otf")
                if f2 in fonts_available:
                    return all_fonts[f2]
                logger.warning(f"get_font: button {this_button}: button label font '{fn}' not found")
            return None

        # 1. Tries button specific font
        f = try_ext(fontname)
        if f is not None:
            return f

        # 2. Tries default fonts
        #    Tries page default font
        default_font = page.default_label_font
        f = try_ext(default_font)
        if f is not None:
            return f

        # 2. Tries deck default font
        default_font = deck.default_label_font
        f = try_ext(default_font)
        if f is not None:
            return f

        # 3. Tries cockpit default font
        default_font = cockpit.default_label_font
        f = try_ext(default_font)
        if f is not None:
            return f

        # 4. Returns first font, if any
        if len(fonts_available) > 0:
            logger.warning(f"get_font: button {this_button} cockpit default label font not found in {fonts_available}, tried {page.default_label_font}, {deck.default_label_font}, {cockpit.default_label_font}. Returning first font found ({fonts_available[0]})")
            return all_fonts[fonts_available[0]]
        else:
            logger.error(f"get_font: button {this_button}: no font")

        return None

    def get_image_for_icon(self):
        image = None
        deck = self.button.deck
        this_button = f"{self.button_name()}: {type(self).__name__}"
        self.icon = add_ext(self.icon, "png")
        if self.icon in deck.icons.keys():  # look for properly sized image first...
            logger.debug(f"get_image_for_icon: button {this_button}: found {self.icon} in deck")
            image = deck.icons[self.icon]
        elif self.icon in deck.cockpit.icons.keys(): # then icon, but need to resize it if necessary
            logger.debug(f"get_image_for_icon: button {this_button}: found {self.icon} in cockpit")
            image = deck.cockpit.icons[self.icon]
            image = deck.scale_icon_for_key(self.button, image)
        else:
            logger.warning(f"get_image_for_icon: button {this_button}: {self.icon} not found")
        return image

    def get_image(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        image = None
        if self.button.has_option("framed-icon"):
            image = self.get_framed_icon()
        else:
            image = self.get_image_for_icon()

        if image is None:
            logger.warning(f"get_image: button {self.button_name()}: {type(self).__name__} no image")
            return None

        # Add little check mark if not valid/fake
        if not self.button.is_valid() or self.button.has_option("placeholder"):
            image = image.copy()  # we will add text over it
            draw = ImageDraw.Draw(image)
            c = round(0.97 * image.width)  # % from edge
            s = round(0.1 * image.width)   # size
            pologon = ( (c, c), (c, c-s), (c-s, c), (c, c) )  # lower right corner
            draw.polygon(pologon, fill="red", outline="white")

        # Add little check mark if not valid/fake
        # if self.button._config.get("type", "none") == "none":
        #     image = image.copy()  # we will add text over it
        #     draw = ImageDraw.Draw(image)
        #     c1 = round(0.03 * image.width)  # % from edge
        #     s = round(0.1 * image.width)   # size
        #     pologon = ( (c1, image.height-c1), (c1, image.height-c1-s), (c1+s, image.height-c1), ((c1, image.height-c1)) )  # lower left corner
        #     draw.polygon(pologon, fill="orange", outline="white")

        return self.overlay_text(image, "label")

    def get_framed_icon(self):
        FRAME = "FRAME"
        FRAME_SIZE = (400, 400)
        FRAME_CONTENT = (222, 222)
        FRAME_POSITION = (90, 125)
        image = None
        deck = self.button.deck
        this_button = f"{self.button_name()}: {type(self).__name__}"
        frame = add_ext(FRAME, "png")
        if frame in deck.cockpit.icons.keys():  # look for properly sized image first...
            logger.debug(f"frame_icon: button {this_button}: found {frame} in cockpit")
            image = deck.cockpit.icons[frame]
        else:
            logger.warning(f"frame_icon: button {this_button}: {frame} not found")
            return self.get_image_for_icon()

        inside = self.get_image_for_icon()
        if inside is not None:
            inside = inside.resize(FRAME_CONTENT)
            box = (90, 125, )  # FRAME_POSITION + (FRAME_POSITION[0]+FRAME_CONTENT[0],FRAME_POSITION[1]+FRAME_CONTENT[1])
            logger.debug(f"frame_icon: button {this_button}: {self.icon}, {frame}, {image}, {inside}, {box}")
            image.paste(inside, box)
            image = deck.scale_icon_for_key(self.button, image)
            return image
        return None

    def overlay_text(self, image, which_text):  # which_text = {label|text}
        draw = None
        # Add label if any

        text, text_format, text_font, text_color, text_size, text_position = self.get_text_detail(self._config, which_text)

        if which_text == "label":  # hum.
            text_size = int(text_size * image.width / 72)

        # logger.debug(f"overlay_text: {text}")
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
            logger.warning(f"clean: button {self.button_name()}: {type(self).__name__}: no fill icon")

    def describe(self):
        return "The representation produces an icon with optional label overlay."


class IconText(Icon):

    def __init__(self, config: dict, button: "Button"):
        Icon.__init__(self, config=config, button=button)

        self.text = str(config.get("text"))

        self.icon_color = config.get("text-bg-color")
        self.mk_uniform_icon()
        # self.texts = config.get("texts")  # @todo later

    def get_image(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        image = super().get_image()
        return self.overlay_text(image, "text")

    def describe(self):
        return "The representation produces an icon with optional text and label overlay."


class IconSide(Icon):

    def __init__(self, config: dict, button: "Button"):
        Icon.__init__(self, config=config, button=button)

        page = self.button.page
        self.side = config.get("side")  # multi-labels
        self.icon_color = self.side.get("icon-color", page.default_icon_color)
        self.centers = self.side.get("centers", [43, 150, 227])
        self.labels = self.side.get("labels")
        self.label_position = config.get("label-position", "cm")  # "centered" on middle of side image

    def get_datarefs(self):
        if self.datarefs is None:
            self.datarefs = []
            if self.labels is not None:
                for label in self.labels:
                    dref = label.get("managed")
                    if dref is not None:
                        self.datarefs.append(dref)
        return self.datarefs

    def is_valid(self):
        if self.button.index not in ["left", "right"]:
            logger.debug(f"is_valid: button {self.button_name()}: {type(self).__name__}: not a valid index {self.button.index}")
            return False
        return super().is_valid()

    def get_image_for_icon(self):
        """
        Helper function to get button image and overlay label on top of it for SIDE keys (60x270).
        Side keys can have 3 labels placed in front of each knob.
        (Currently those labels are static only. Working to make them dynamic.)
        """
        image = super().get_image_for_icon()

        if image is None:
            return None

        draw = None
        # Add label if any
        if self.labels is not None:
            image = image.copy()  # we will add text over it
            draw = ImageDraw.Draw(image)
            inside = round(0.04 * image.width + 0.5)
            vposition = "TCB"
            vheight = 38 - inside

            vcenter = [43, 150, 227]  # this determines the number of acceptable labels, organized vertically
            cnt = self.side.get("centers")
            if cnt is not None:
                vcenter = [round(270 * i / 100, 0) for i in convert_color(cnt)]  # !

            li = 0
            for label in self.labels:
                txt = label.get("label")
                if li >= len(vcenter) or txt is None:
                    continue
                managed = label.get("managed")
                if managed is not None:
                    value = self.button.get_dataref_value(managed)
                    if value:
                        txt = txt + "•"  # \n•"
                    else:
                        txt = txt + ""   # \n"
                    logger.debug(f"get_image_for_icon: watching {managed}: {value}")

                fontname = self.get_font(label.get("label-font", self.label_font))
                if fontname is None:
                    logger.warning(f"get_image_for_icon: no font, cannot overlay label")
                else:
                    # logger.debug(f"get_image: font {fontname}")
                    lsize = label.get("label-size", self.label_size)
                    font = ImageFont.truetype(fontname, lsize)
                    # Horizontal centering is not an issue...
                    label_position = label.get("label-position", self.label_position)
                    w = image.width / 2
                    p = "m"
                    a = "center"
                    if label_position == "l":
                        w = inside
                        p = "l"
                        a = "left"
                    elif label_position == "r":
                        w = image.width - inside
                        p = "r"
                        a = "right"
                    # Vertical centering is black magic...
                    h = vcenter[li] - lsize / 2
                    if label_position[1] == "t":
                        h = vcenter[li] - vheight
                    elif label_position[1] == "b":
                        h = vcenter[li] + vheight - lsize

                    # logger.debug(f"get_image: position {self.label_position}: {(w, h)}, anchor={p+'m'}")
                    draw.multiline_text((w, h),  # (image.width / 2, 15)
                              text=txt,
                              font=font,
                              anchor=p+"m",
                              align=a,
                              fill=label.get("label-color", self.label_color))
                li = li + 1
        return image

    def describe(self):
        return "The representation produces an icon with optional label overlay for larger side buttons on LoupedeckLive."


class MultiIcons(Icon):

    def __init__(self, config: dict, button: "Button"):
        Icon.__init__(self, config=config, button=button)

        self.multi_icons = config.get("icon-animate")
        if self.multi_icons is None:
            self.multi_icons = config.get("multi-icons", [])
        else:
            logger.debug(f"__init__: button {self.button_name()}: {type(self).__name__}: animation sequence {len(self.multi_icons)}")

        if len(self.multi_icons) > 0:
            for i in range(len(self.multi_icons)):
                self.multi_icons[i] = add_ext(self.multi_icons[i], ".png")
                if self.multi_icons[i] not in self.button.deck.icons.keys():
                    logger.warning(f"__init__: button {self.button_name()}: {type(self).__name__}: icon not found {self.multi_icons[i]}")
        else:
            logger.warning(f"__init__: button {self.button_name()}: {type(self).__name__}: no icon")

    def is_valid(self):
        if self.multi_icons is None:
            logger.warning(f"is_valid: button {self.button_name()}: {type(self).__name__}: no icon")
            return False
        if len(self.multi_icons) == 0:
            logger.warning(f"is_vali: button {self.button_name()}: {type(self).__name__}: no icon")
        return super().is_valid()

    def num_icons(self):
        return len(self.multi_icons)

    def render(self):
        value = self.get_current_value()
        if value is None:
            logger.warning(f"render: button {self.button_name()}: {type(self).__name__}: no current value, no rendering")
            return None
        if type(value) in [str, int, float]:
            value = int(value)
        else:
            logger.warning(f"render: button {self.button_name()}: {type(self).__name__}: complex value {value}")
            return None
        if self.num_icons() > 0:
            if  value >= 0 and value < self.num_icons():
                self.icon = self.multi_icons[value]
            else:
                self.icon = self.multi_icons[value % self.num_icons()]
            return super().render()
        else:
            logger.warning(f"render: button {self.button_name()}: {type(self).__name__}: icon not found {value}/{self.num_icons()}")
        return None

    def describe(self):
        return "\n\r".join([
            f"The representation produces an icon selected from a list of {len(self.multi_icons)} icons."
        ])


class IconAnimation(MultiIcons):
    """
    To start the animation, set the button's current_value to something different from None or 0.
    To stop the anination, set the button's current_value to 0.
    When not running, an optional icon_off can be supplied, otherwise first icon in multi-icons list will be used.
    """
    def __init__(self, config: dict, button: "Button"):
        MultiIcons.__init__(self, config=config, button=button)

        self.speed = float(config.get("animation-speed", 1))
        self.icon_off = config.get("icon-off")

        if self.icon_off is None and len(self.multi_icons) > 0:
            self.icon_off = self.multi_icons[0]

        # Internal variables
        self.counter = 0
        self.exit = None
        self.thread = None
        self.running = False

    def loop(self):
        self.exit = threading.Event()
        while not self.exit.is_set():
            self.button.render()
            self.counter = self.counter + 1
            self.button.set_current_value(self.counter)  # get_current_value() will fetch self.counter value
            self.exit.wait(self.speed)
        logger.debug(f"loop: exited")

    def should_run(self) -> bool:
        """
        Check conditions to animate the icon.
        """
        value = self.get_current_value()
        return value is not None and value != 0

    def anim_start(self):
        """
        Starts animation
        """
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.loop)
            self.thread.name = f"ButtonAnimate::loop({self.button_name()})"
            self.thread.start()
        else:
            logger.warning(f"anim_start: button {self.button_name()}: already started")

    def anim_stop(self, render: bool = True):
        """
        Stops animation
        """
        if self.running:
            self.running = False
            self.exit.set()
            self.thread.join(timeout=2*self.speed)
            if self.thread.is_alive():
                logger.warning(f"anim_stop: ..thread may hang..")
            if render:
                self.render()
        else:
            logger.debug(f"anim_stop: button {self.button_name()}: already stopped")

    def clean(self):
        """
        Stops animation and remove icon from deck
        """
        logger.debug(f"clean: button {self.button_name()}: cleaning requested")
        self.anim_stop(render=False)
        logger.debug(f"clean: button {self.button_name()}: stopped")
        super().clean()

    def render(self):
        """
        Renders icon_off or current icon in list
        """
        if self.should_run():
            self.icon = self.multi_icons[(self.counter % len(self.multi_icons))]
            if not self.running:
                self.anim_start()
            return super().render()
        if self.running:
            self.anim_stop()
        self.icon = self.icon_off
        return super(MultiIcons, self).render()

    def describe(self):
        """
        Describe what the button does in plain English
        """
        a = [
            f"The representation produces an animation by displaying an icon from a list of {len(self.multi_icons)} icons"
            f"and changing it every {self.speed} seconds."
        ]
        if self.icon_off is not None:
            a.append(f"When the animation is not running, it displays an OFF icon {self.icon_off}.")
        return "\n\r".join(a)


#
# ###############################
# LED TYPE REPRESENTATION
#
#
class LED(Representation):

    def __init__(self, config: dict, button: "Button"):
        Representation.__init__(self, config=config, button=button)

        self.mode = config.get("led", "single")  # unused

    def render(self):
        value = self.get_current_value()
        v = value is not None and value != 0
        return (v, self.mode)

    def clean(self):
        self.button.set_current_value(0)
        self.button.render()

    def describe(self):
        """
        Describe what the button does in plain English
        """
        a = [
            f"The representation turns ON or OFF a single LED light"
        ]
        return "\n\r".join(a)


class ColoredLED(Representation):
    """
    @todo: later: Adjust the color of the LED from the button.get_button_value().
    """
    def __init__(self, config: dict, button: "Button"):
        Representation.__init__(self, config=config, button=button)

        color = config.get("colored-led", button.page.deck.cockpit.cockpit_color)  # color should hold a tuple of 3 or 4 int or float
        self.color = convert_color(color)

    def render(self):
        logger.debug(f"render: {type(self).__name__}: {self.color}")
        return self.color

    def clean(self):
        logger.debug(f"clean: {type(self).__name__}")
        self.button.set_current_value(0)
        self.button.render()

    def describe(self):
        """
        Describe what the button does in plain English
        """
        a = [
            f"The representation turns ON or OFF a single LED light and changes the color of the LED."
        ]
        return "\n\r".join(a)


class MultiLEDs(Representation):
    """
    Ring of 13 LEDs surrounding X-Touch Mini encoders
    """
    def __init__(self, config: dict, button: "Button"):
        Representation.__init__(self, config=config, button=button)

        mode = config.get("multi-leds", LED_MODE.SINGLE.name)
        if is_integer(mode) and int(mode) in [l.value for l in LED_MODE]:
            self.mode = LED_MODE(mode)
        elif type(mode) is str and mode.upper() in [l.name for l in LED_MODE]:
            mode = mode.upper()
            self.mode = LED_MODE[mode]
        else:
            logger.warning(f"__init__: {type(self).__name__}: invalid mode {mode}")

    def is_valid(self):
        maxval = 7 if self.mode == LED_MODE.SPREAD else 13
        value = self.get_current_value()
        if value >= maxval:
            logger.warning(f"is_valid: button {self.button_name()}: {type(self).__name__}: value {value} too large for mode {self.mode}")
        return super().is_valid()

    def render(self):
        maxval = 7 if self.mode == LED_MODE.SPREAD else 13
        v = min(int(self.get_current_value()), maxval)
        return (v, self.mode)

    def clean(self):
        self.button.set_current_value(0)
        self.button.render()

    def describe(self):
        """
        Describe what the button does in plain English
        """
        a = [
            f"The representation turns multiple LED ON or OFF"
        ]
        return "\n\r".join(a)

#
# ###############################
#
# "Icon" Buttons that are dynamically drawn
#
from .button_annunciator import Annunciator, AnnunciatorAnimate
from .button_draw import DataIcon, Switch, CircularSwitch, PushSwitch, DrawAnimationFTG

# Calls external services
from .button_ext import WeatherIcon

#
# ###############################
# REPRESENTATIONS
#
#
REPRESENTATIONS = {
    "none": Representation,
    "icon": Icon,
    "text": IconText,
    "icon-color": Icon,
    "multi-icons": MultiIcons,
    "icon-animate": IconAnimation,
    "side": IconSide,
    "led": LED,
    "colored-led": ColoredLED,
    "multi-leds": MultiLEDs,
    "annunciator": Annunciator,
    "annunciator-animate": AnnunciatorAnimate,
    "switch": Switch,
    "circular-switch": CircularSwitch,
    "push-switch": PushSwitch,
    "data": DataIcon,
    "ftg": DrawAnimationFTG,
    "weather": WeatherIcon
}
