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
from cockpitdecks import KW, DECK_FEEDBACK

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

    REQUIRED_DECK_FEEDBACKS = DECK_FEEDBACK.NONE

    @classmethod
    def get_required_capability(cls) -> list | tuple:
        r = cls.REQUIRED_DECK_FEEDBACKS
        return r if type(r) in [list, tuple] else [r]

    def __init__(self, config: dict, button: "Button"):
        self._config = config
        self.button = button
        self._sound = config.get("vibrate")
        self.datarefs = None

        self.button.deck.cockpit.set_logging_level(__name__)

        self.init()

    def init(self):  # ~ABC
        if type(self.REQUIRED_DECK_FEEDBACKS) not in [list, tuple]:
            self.REQUIRED_DECK_FEEDBACKS = [self.REQUIRED_DECK_FEEDBACKS]

    def can_render(self) -> bool:
        button_cap = self.button._def[KW.VIEW.value]
        if button_cap not in self.REQUIRED_DECK_FEEDBACKS:
            logger.warning(
                f"button {self.button_name()} has feedback capability {button_cap}, representation expects {self.REQUIRED_DECK_FEEDBACKS}."
            )
            return False
        return True

    def button_name(self):
        return self.button.name if self.button is not None else "no button"

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
        logger.debug(
            f"button {self.button_name()}: {type(self).__name__} has no rendering"
        )
        return None

    def vibrate(self):
        if self._sound is not None and hasattr(self.button.deck, "_vibrate"):
            self.button.deck._vibrate(self._sound)

    def clean(self):
        # logger.warning(f"button {self.button_name()}: no cleaning")
        pass

    def describe(self):
        return "The button does not produce any output."


#
# ###############################
# ICON TYPE REPRESENTATION
#
#
class Icon(Representation):

    REQUIRED_DECK_FEEDBACKS = DECK_FEEDBACK.IMAGE

    def __init__(self, config: dict, button: "Button"):
        Representation.__init__(self, config=config, button=button)

        # This is leaf node in hierarchy, so we have to be careful.
        # Button addresses "feature" and if it does not exist we return "default-feature"
        # from hierarchy.
        self.label = config.get("label")
        self.label_format = config.get("label-format")
        self.label_font = config.get(
            "label-font", button.get_attribute("default-label-font")
        )
        self.label_size = int(
            config.get("label-size", button.get_attribute("default-label-size"))
        )
        self.label_color = config.get(
            "label-color", button.get_attribute("default-label-color")
        )
        self.label_color = convert_color(self.label_color)
        self.label_position = config.get(
            "label-position", button.get_attribute("default-label-position")
        )
        if self.label_position[0] not in "lcr" or self.label_position[1] not in "tmb":
            logger.warning(
                f"button {self.button_name()}: {type(self).__name__} invalid label position code {self.label_position}, using default"
            )
            self.label_position = button.get_attribute("default-label-position")

        self.icon_color = config.get(
            "icon-color", button.get_attribute("default-icon-color")
        )
        self.icon_color = convert_color(self.icon_color)
        self.icon_texture = config.get(
            "icon-texture", button.get_attribute("default-icon-texture")
        )

        self.text_config = config  # where to get text from

        self.frame = config.get(KW.FRAME.value)

        self.icon = None
        deck = self.button.deck
        candidate_icon = config.get("icon")
        if candidate_icon is not None:
            for ext in [".png", ".jpg", ".jpeg"]:
                fn = add_ext(candidate_icon, ext)
                if self.icon is None and fn in deck.icons.keys():
                    self.icon = fn
                    logger.debug(
                        f"button {self.button_name()}: {type(self).__name__}: icon {self.icon} found"
                    )
            if self.icon is None:
                logger.warning(
                    f"button {self.button_name()}: {type(self).__name__}: icon not found {candidate_icon}"
                )

        if self.icon is None:
            self.make_icon()

    def make_icon(self, force: bool = False):
        self.icon = self.button.get_id()
        if force and self.icon in self.button.deck.icons:
            del self.button.deck.icons[self.icon]
        image = self.button.deck.create_icon_for_key(
            index=self.button.index,
            colors=self.icon_color,
            texture=self.icon_texture,
            name=self.icon,
        )
        logger.debug(
            f"button {self.button_name()}: {type(self).__name__}: created icon {self.icon}"
        )

    def is_valid(self):
        if super().is_valid():  # so there is a button...
            if self.icon is not None:
                if self.icon not in self.button.deck.icons.keys():
                    logger.warning(
                        f"button {self.button_name()}: {type(self).__name__}: icon {self.icon} not in deck"
                    )
                    return False
                return True
            if self.icon_color is not None:
                return True
            logger.warning(
                f"button {self.button_name()}: {type(self).__name__}: no icon and no icon color"
            )
        return False

    def render(self):
        return self.get_image()

    def icon_size(self) -> list:
        return self.button.deck.deck_content.display_size(self.button.index)

    def get_text_detail(self, config, which_text):
        text = self.button.get_text(config, which_text)
        text_format = config.get(f"{which_text}-format")
        page = self.button.page

        dflt_system_font = self.button.get_attribute(f"default-system-font")
        if dflt_system_font is None:
            logger.error(f"button {self.button_name()}: no system font")

        dflt_text_font = self.button.get_attribute(f"default-{which_text}-font")
        if dflt_text_font is None:
            dflt_text_font = self.button.get_attribute("default-label-font")
            if dflt_text_font is None:
                logger.warning(
                    f"button {self.button_name()}: no default label font, using system font"
                )
                dflt_text_font = dflt_system_font

        text_font = config.get(f"{which_text}-font", dflt_text_font)

        dflt_text_size = self.button.get_attribute(f"default-{which_text}-size")
        if dflt_text_size is None:
            dflt_text_size = self.button.get_attribute("default-label-size")
            if dflt_text_size is None:
                logger.warning(
                    f"button {self.button_name()}: no default label size, using 10"
                )
                dflt_text_size = 16
        text_size = config.get(f"{which_text}-size", dflt_text_size)

        dflt_text_color = self.button.get_attribute(f"default-{which_text}-color")
        if dflt_text_color is None:
            dflt_text_color = self.button.get_attribute("default-label-color")
            if dflt_text_color is None:
                logger.warning(
                    f"button {self.button_name()}: no default label color, using {DEFAULT_COLOR}"
                )
                dflt_text_color = DEFAULT_COLOR
        text_color = config.get(f"{which_text}-color", dflt_text_color)
        text_color = convert_color(text_color)

        dflt_text_position = self.button.get_attribute(f"default-{which_text}-position")
        if dflt_text_position is None:
            dflt_text_position = self.button.get_attribute("default-label-position")
            if dflt_text_position is None:
                logger.warning(
                    f"button {self.button_name()}: no default label position, using cm"
                )
                dflt_text_position = "cm"  # middle of icon
        text_position = config.get(f"{which_text}-position", dflt_text_position)
        if text_position[0] not in "lcr":
            text_position = DEFAULT_VALID_TEXT_POSITION
            logger.warning(
                f"button {self.button_name()}: {type(self).__name__}: invalid horizontal label position code {text_position}, using default"
            )
        if text_position[1] not in "tmb":
            text_position = DEFAULT_VALID_TEXT_POSITION
            logger.warning(
                f"button {self.button_name()}: {type(self).__name__}: invalid vertical label position code {text_position}, using default"
            )

        # print(f">>>> {self.button.get_id()}:{which_text}", dflt_text_font, dflt_text_size, dflt_text_color, dflt_text_position)

        if text is not None and not isinstance(text, str):
            logger.warning(
                f"button {self.button_name()}: converting text {text} to string (type {type(text)})"
            )
            text = str(text)

        return text, text_format, text_font, text_color, text_size, text_position

    def get_font(self, fontname: str, fontsize: int):
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
                logger.warning(f"button {this_button}: font '{fn}' not found")
            return None

        # 1. Tries button specific font
        f = try_ext(fontname)
        if f is not None:
            return ImageFont.truetype(f, fontsize)

        # 2. Tries default fonts
        default_font = self.button.get_attribute("default-label-font")
        if default_font is not None:
            f = try_ext(default_font)
            if f is not None:
                return ImageFont.truetype(f, fontsize)

        # 3. Returns first font, if any
        if len(fonts_available) > 0:
            f = all_fonts[fonts_available[0]]
            logger.warning(
                f"button {this_button} cockpit default label font not found in {fonts_available}, tried {page.default_label_font}, {deck.default_label_font}, {cockpit.default_label_font}. Returning first font found ({f})"
            )
            return ImageFont.truetype(f, fontsize)

        # 5. Tries cockpit default font
        default_font = cockpit.default_font
        f = try_ext(default_font)
        if f is not None:
            return ImageFont.truetype(f, fontsize)

        logger.error(f"no font, using pillow default")
        return ImageFont.load_default()

    def get_image_for_icon(self):
        deck = self.button.deck
        if self.icon in deck.icons.keys():
            return deck.icons.get(self.icon)
        # Else, search for it and cache it
        image = None
        this_button = f"{self.button_name()}: {type(self).__name__}"
        for ext in ["png", "jpg"]:
            if image is None:
                fn = add_ext(self.icon, ext)
                if fn in deck.icons.keys():  # look for properly sized image first...
                    logger.debug(f"button {this_button}: found {fn} in deck")
                    self.icon = fn
                    image = deck.icons[self.icon]
                elif (
                    fn in deck.cockpit.icons.keys()
                ):  # then icon, but need to resize it if necessary
                    logger.debug(f"button {this_button}: found {fn} in cockpit")
                    self.icon = fn
                    image = deck.cockpit.icons[self.icon]
                    image = deck.scale_icon_for_key(
                        self.button.index, image, name=self.icon
                    )  # this will cache it in the deck as well
        if image is None:
            logger.warning(f"button {this_button}: {self.icon} not found")
        return image

    def get_image(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        image = None
        if self.frame is not None:
            image = self.get_framed_icon()
        else:
            image = self.get_image_for_icon()

        if image is None:
            logger.warning(
                f"button {self.button_name()}: {type(self).__name__} no image"
            )
            return None

        if self.button.has_option("placeholder"):
            # Add little blue check mark if placeholder
            image = image.copy()  # we will add text over it
            draw = ImageDraw.Draw(image)
            c = round(0.97 * image.width)  # % from edge
            s = round(0.10 * image.width)  # size
            pologon = ((c, c), (c, c - s), (c - s, c), (c, c))  # lower right corner
            draw.polygon(pologon, fill="deepskyblue")
        else:
            # Button is invalid, add a little red mark
            # if not self.button.is_valid():
            #     image = image.copy()  # we will add text over it
            #     draw = ImageDraw.Draw(image)
            #     c = round(0.97 * image.width)  # % from edge
            #     s = round(0.10 * image.width)  # size
            #     pologon = ( (c, c), (c, c-s), (c-s, c), (c, c) )  # lower right corner
            #     draw.polygon(pologon, fill="red", outline="white")

            # Representation is invalid, add a little orange mark
            if not self.is_valid():
                image = image.copy()  # we will add text over it
                draw = ImageDraw.Draw(image)
                c = round(0.97 * image.width)  # % from edge
                s = round(0.15 * image.width)  # size
                pologon = ((c, c), (c, c - s), (c - s, c), (c, c))  # lower right corner
                draw.polygon(pologon, fill="orange")

            # Activation is invalid, add a little red mark (may be on top of above mark...)
            if (
                self.button._activation is not None
                and not self.button._activation.is_valid()
            ):
                image = image.copy()  # we will add text over it
                draw = ImageDraw.Draw(image)
                c = round(0.97 * image.width)  # % from edge
                s = round(0.08 * image.width)  # size
                pologon = ((c, c), (c, c - s), (c - s, c), (c, c))  # lower right corner
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
        # We assume self.frame is a non null dict
        frame = self.frame.get("frame")
        frame_size = self.frame.get("frame-size")
        frame_content = self.frame.get("content-size")
        frame_position = self.frame.get("content-offset")

        this_button = f"{self.button_name()}: {type(self).__name__}"
        image = None
        deck = self.button.deck
        if (
            frame is None
            or frame_size is None
            or frame_position is None
            or frame_content is None
        ):
            logger.warning(f"button {this_button}: invalid frame {self.frame}, {frame}")
        else:
            image = deck.get_icon_background(
                name=this_button,
                width=frame_size[0],
                height=frame_size[1],
                texture_in=frame,
                color_in=self.icon_color,
                use_texture=True,
                who="Frame",
            )

        inside = self.get_image_for_icon()
        if inside is not None and image is not None:
            inside = inside.resize(frame_content)
            box = (
                90,
                125,
            )  # frame_position + (frame_position[0]+frame_content[0],frame_position[1]+frame_content[1])
            logger.debug(
                f"button {this_button}: {self.icon}, {frame}, {image}, {inside}, {box}"
            )
            image.paste(inside, box)
            image = deck.scale_icon_for_key(self.button, image)
            return image
        return inside

    def overlay_text(self, image, which_text):  # which_text = {label|text}
        draw = None
        # Add label if any

        text_dict = self._config
        if which_text == "text":  # hum.
            text_dict = self.text_config

        text, text_format, text_font, text_color, text_size, text_position = (
            self.get_text_detail(text_dict, which_text)
        )

        if which_text == "label":
            text_size = int(text_size * image.width / 72)

        if text is None:
            return image

        if self.button.is_managed() and which_text == "text":
            txtmod = self.button.manager.get(f"text-modifier", "dot").lower()
            if txtmod in ["std", "standard"]:  # QNH Std
                text_font = "AirbusFCU"  # hardcoded

        font = self.get_font(text_font, text_size)
        image = image.copy()  # we will add text over it
        draw = ImageDraw.Draw(image)
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
        elif text_position[1] == "b":
            h = image.height - inside - text_size / 2
        # logger.debug(f"position {(w, h)}")
        draw.multiline_text(
            (w, h), text=text, font=font, anchor=p + "m", align=a, fill=text_color
        )  # (image.width / 2, 15)
        return image

    def clean(self):
        """
        Removes icon from deck
        """
        # icon = self.get_default_icon()  # does not work for loupedeck left/right
        icon = None
        deck = self.button.deck
        page = self.button.page
        icon = deck.create_icon_for_key(
            self.button.index,
            colors=self.button.get_attribute("cockpit-color"),
            texture=self.button.get_attribute("cockpit-texture"),
            name=f"{self.button_name()}:clean",
        )
        if icon is not None:
            deck._send_key_image_to_device(self.button._key, icon)
        else:
            logger.warning(
                f"button {self.button_name()}: {type(self).__name__}: no clean icon"
            )

    def describe(self):
        return "The representation places an icon with optional label overlay."


class IconText(Icon):
    def __init__(self, config: dict, button: "Button"):
        Icon.__init__(self, config=config, button=button)

        self.text = str(config.get("text"))
        self.icon_color = config.get("text-bg-color", self.icon_color)

    def get_image(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        bgcolor = self.text_config.get("text-bg-color")
        if bgcolor is not None:
            self.icon_color = convert_color(bgcolor)
        bgtexture = self.text_config.get("text-bg-texture")
        if bgtexture is not None:
            self.icon_texture = bgtexture
        self.make_icon(force=True)
        image = super().get_image()
        return self.overlay_text(image, "text")

    def describe(self):
        return "The representation places an icon with optional text and label overlay."


class MultiTexts(IconText):
    def __init__(self, config: dict, button: "Button"):
        IconText.__init__(self, config=config, button=button)

        self.multi_texts = config.get("text-animate")
        if self.multi_texts is None:
            self.multi_texts = config.get("multi-texts", [])
        else:
            logger.debug(
                f"button {self.button_name()}: {type(self).__name__}: animation sequence {len(self.multi_texts)}"
            )

    def get_datarefs(self):
        datarefs = []
        for text in self.multi_texts:
            drefs = self.button.scan_datarefs(text)
            if len(drefs) > 0:
                datarefs = datarefs + drefs
        return datarefs

    def is_valid(self):
        if self.multi_texts is None:
            logger.warning(
                f"button {self.button_name()}: {type(self).__name__}: no icon"
            )
            return False
        if len(self.multi_texts) == 0:
            logger.warning(
                f"button {self.button_name()}: {type(self).__name__}: no icon"
            )
        return super().is_valid()

    def num_texts(self):
        return len(self.multi_texts)

    def render(self):
        value = self.get_current_value()
        if value is None:
            logger.warning(
                f"button {self.button_name()}: {type(self).__name__}: no current value, no rendering"
            )
            return None
        if type(value) in [str, int, float]:
            value = int(value)
        else:
            logger.warning(
                f"button {self.button_name()}: {type(self).__name__}: complex value {value}"
            )
            return None
        if self.num_texts() > 0:
            if value >= 0 and value < self.num_texts():
                self.text_config = self.multi_texts[value]
            else:
                self.text_config = self.multi_texts[value % self.multi_texts()]
            return super().render()
        else:
            logger.warning(
                f"button {self.button_name()}: {type(self).__name__}: icon not found {value}/{self.num_texts()}"
            )
        return None

    def describe(self):
        return "\n\r".join(
            [
                f"The representation produces an icon with text, text is selected from a list of {len(self.multi_texts)} texts bsaed on the button's value."
            ]
        )


class IconSide(Icon):
    def __init__(self, config: dict, button: "Button"):
        Icon.__init__(self, config=config, button=button)

        page = self.button.page
        self.side = config.get("side")  # multi-labels
        self.icon_color = self.side.get("icon-color", page.default_icon_color)  # type: ignore
        if self.icon_color is not None:
            self.icon_color = convert_color(self.icon_color)
        self.centers = self.side.get("centers", [43, 150, 227])  # type: ignore
        self.labels: str | None = self.side.get("labels")  # type: ignore
        self.label_position = config.get(
            "label-position", "cm"
        )  # "centered" on middle of side image

    def get_datarefs(self):
        if self.datarefs is None:
            self.datarefs = []
            if self.labels is not None:
                for label in self.labels:
                    dref = label.get(KW.MANAGED.value)
                    if dref is not None:
                        logger.debug(
                            f"button {self.button_name()}: added label dataref {dref}"
                        )
                        self.datarefs.append(dref)
        return self.datarefs

    def is_valid(self):
        if self.button.index not in ["left", "right"]:
            logger.debug(
                f"button {self.button_name()}: {type(self).__name__}: not a valid index {self.button.index}"
            )
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
            vheight = 38 - inside
            vcenter = [
                43,
                150,
                227,
            ]  # this determines the number of acceptable labels, organized vertically
            cnt = self.side.get("centers")
            if cnt is not None:
                vcenter = [round(270 * i / 100, 0) for i in convert_color(cnt)]  # !

            li = 0
            for label in self.labels:
                txt = label.get("label")
                if li >= len(vcenter) or txt is None:
                    continue
                managed = label.get(KW.MANAGED.value)
                if managed is not None:
                    value = self.button.get_dataref_value(managed)
                    txto = txt
                    if value:
                        txt = txt + "•"  # \n•"
                    else:
                        txt = txt + " "  # \n"
                    logger.debug(f"watching {managed}: {value}, {txto} -> {txt}")

                # logger.debug(f"font {fontname}")
                lfont = label.get("label-font", self.label_font)
                lsize = label.get("label-size", self.label_size)
                font = self.get_font(lfont, lsize)
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

                # logger.debug(f"position {self.label_position}: {(w, h)}, anchor={p+'m'}")
                draw.multiline_text(
                    (w, h),
                    text=txt,
                    font=font,
                    anchor=p + "m",
                    align=a,
                    fill=label.get(
                        "label-color", self.label_color
                    ),  # (image.width / 2, 15)
                )
                li = li + 1
        return image

    def describe(self):
        return "The representation produces an icon with optional label overlay for larger side buttons on LoupedeckLive."


class MultiIcons(Icon):
    def __init__(self, config: dict, button: "Button"):
        Icon.__init__(self, config=config, button=button)

        self.multi_icons = config.get("icon-animate", [])  # type: ignore
        if len(self.multi_icons) == 0:
            self.multi_icons = config.get("multi-icons", [])
        else:
            logger.debug(
                f"button {self.button_name()}: {type(self).__name__}: animation sequence {len(self.multi_icons)}"
            )

        if len(self.multi_icons) > 0:
            for i in range(len(self.multi_icons)):
                self.multi_icons[i] = add_ext(self.multi_icons[i], ".png")
                if self.multi_icons[i] not in self.button.deck.icons.keys():
                    logger.warning(
                        f"button {self.button_name()}: {type(self).__name__}: icon not found {self.multi_icons[i]}"
                    )
        else:
            logger.warning(
                f"button {self.button_name()}: {type(self).__name__}: no icon"
            )

    def is_valid(self):
        if self.multi_icons is None:
            logger.warning(
                f"button {self.button_name()}: {type(self).__name__}: no icon"
            )
            return False
        if len(self.multi_icons) == 0:
            logger.warning(
                f"button {self.button_name()}: {type(self).__name__}: no icon"
            )
        return super().is_valid()

    def num_icons(self):
        return len(self.multi_icons)

    def render(self):
        value = self.get_current_value()
        if value is None:
            logger.warning(
                f"button {self.button_name()}: {type(self).__name__}: no current value, no rendering"
            )
            return None
        if type(value) in [str, int, float]:
            value = int(value)
        else:
            logger.warning(
                f"button {self.button_name()}: {type(self).__name__}: complex value {value}"
            )
            return None
        if self.num_icons() > 0:
            if value >= 0 and value < self.num_icons():
                self.icon = self.multi_icons[value]
            else:
                self.icon = self.multi_icons[value % self.num_icons()]
            return super().render()
        else:
            logger.warning(
                f"button {self.button_name()}: {type(self).__name__}: icon not found {value}/{self.num_icons()}"
            )
        return None

    def describe(self):
        return "\n\r".join(
            [
                f"The representation produces an icon selected from a list of {len(self.multi_icons)} icons."
            ]
        )


#
# ###############################
# LED TYPE REPRESENTATION
#
#
class LED(Representation):

    REQUIRED_DECK_FEEDBACKS = DECK_FEEDBACK.LED

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
        a = [f"The representation turns ON or OFF a single LED light"]
        return "\n\r".join(a)


class ColoredLED(Representation):

    REQUIRED_DECK_FEEDBACKS = DECK_FEEDBACK.COLORED_LED

    def __init__(self, config: dict, button: "Button"):
        self._color = config.get(
            KW.COLORED_LED.value, button.get_attribute("cockpit-color")
        )
        self.color = (128, 128, 256)
        Representation.__init__(self, config=config, button=button)

    def init(self):
        if type(self._color) == dict:  # @todo: does not currently work
            self.datarefs = self.button.scan_datarefs(self._color)
            if self.datarefs is not None and len(self.datarefs) > 0:
                logger.debug(
                    f"button {self.button_name()}: adding datarefs {self.datarefs} for color"
                )
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
        KW_FORMULA_STR = f"${{{KW.FORMULA.value}}}"  # "${formula}"
        hue = 0  # red
        if KW_FORMULA_STR in str(color_str):
            dataref_rpn = base.get(KW.FORMULA.value)
            if dataref_rpn is not None:
                hue = self.button.execute_formula(formula=dataref_rpn)
        else:
            hue = int(color_str)
            logger.warning(
                f"button {self.button_name()}: color contains {KW_FORMULA_STR} but no {KW.FORMULA.value} attribute found"
            )

        color_rgb = colorsys.hsv_to_rgb((int(hue) % 360) / 360, 1, 1)
        self.color = [int(255 * i) for i in color_rgb]  # type: ignore
        logger.debug(
            f"{color_str}, {hue}, {[(int(hue) % 360)/360,1,1]}, {color_rgb}, {self.color}"
        )
        return self.color

    def render(self):
        color = self.get_color()
        logger.debug(f"{type(self).__name__}: {color}")
        return color

    def clean(self):
        logger.debug(f"{type(self).__name__}")
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


# from XTouchMini.Devices.XTouchMini import LED_MODE


class LED_MODE(Enum):
    SINGLE = 0
    TRIM = 1
    FAN = 2
    SPREAD = 3


class MultiLEDs(Representation):
    """
    Ring of 13 LEDs surrounding X-Touch Mini encoders
    """

    REQUIRED_DECK_FEEDBACKS = DECK_FEEDBACK.MULTI_LEDS

    def __init__(self, config: dict, button: "Button"):
        Representation.__init__(self, config=config, button=button)

        mode = config.get("multi-leds", LED_MODE.SINGLE.name)
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
            logger.warning(
                f"button {self.button_name()}: {type(self).__name__}: value {value} too large for mode {self.mode}"
            )
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
        a = [f"The representation turns multiple LED ON or OFF"]
        return "\n\r".join(a)


#
# #############################################################################################
# #############################################################################################
#
# REPRESENTATIONS
#
# "Icon" Buttons that are dynamically drawn
#
from .annunciator import Annunciator, AnnunciatorAnimate
from .draw import DataIcon, Switch, CircularSwitch, PushSwitch
from .animation import IconAnimation, DrawAnimationFTG

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
}

#
# ###############################
# OPTIONAL REPRESENTATIONS
#
#
# Will only load if AVWX is installed
try:
    from .button_ext import WeatherIcon

    REPRESENTATIONS["weather"] = WeatherIcon
    logger.info(f"WeatherIcon installed")
except ImportError:
    pass
