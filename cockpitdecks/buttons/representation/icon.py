"""
All representations for Icon/image based.
"""

import logging

from PIL import ImageDraw, ImageFont

from cockpitdecks.resources.color import convert_color, has_ext, add_ext
from cockpitdecks import CONFIG_KW, DECK_FEEDBACK
from .representation import Representation
from cockpitdecks.strvar import TextWithVariables

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


#
# ###############################
# ICON TYPE REPRESENTATION
#
#
NO_ICON = "no-icon"


class IconBase(Representation):
    """Abstract icon class

    This is a container class
    """

    REPRESENTATION_NAME = "icon-base-do-not-use"
    REQUIRED_DECK_FEEDBACKS = DECK_FEEDBACK.IMAGE

    PARAMETERS = {}

    def __init__(self, button: "Button"):
        self._label = None
        Representation.__init__(self, button=button)
        # This is leaf node in hierarchy, so we have to be careful.
        # Button addresses "feature" and if it does not exist we return DEFAULT_ATTRIBUTE_PREFIX + "feature"
        # from hierarchy.
        if self._config.get(CONFIG_KW.LABEL.value) is not None:
            self._label = TextWithVariables(owner=button, config=self._config, prefix=CONFIG_KW.LABEL.value)

        self.cockpit_color = button.get_attribute("cockpit-color")
        self.cockpit_color = convert_color(self.cockpit_color)
        self.cockpit_texture = button.get_attribute("cockpit-texture")

        self._icon_cache = None

    def is_valid(self):
        return super().is_valid()

    def render(self):
        return self.get_image()

    def get_font(self, fontname: str, fontsize: int):
        """
        Helper function to get valid font, depending on button or global preferences
        """
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
                for ext in [".ttf", ".otf"]:
                    f1 = add_ext(fn, ext)
                    if f1 in fonts_available:
                        return all_fonts[f1]
                logger.warning(f"button {this_button}: font '{fn}' not found")
            return None

        # 1. Tries button specific font
        f = try_ext(fontname)
        if f is not None:
            return ImageFont.truetype(f, fontsize)

        # 2. Tries default fonts
        default_font = self.button.get_attribute("label-font")
        if default_font is not None:
            f = try_ext(default_font)
            if f is not None:
                return ImageFont.truetype(f, fontsize)

        # 3. Returns first font, if any
        if len(fonts_available) > 0:
            f = all_fonts[fonts_available[0]]
            logger.warning(f"button {this_button} cockpit default label font not found in {fonts_available}. Returning first font found ({f})")
            return ImageFont.truetype(f, fontsize)

        # 5. Tries cockpit default font
        default_font = cockpit.default_font
        f = try_ext(default_font)
        if f is not None:
            return ImageFont.truetype(f, fontsize)

        logger.error("no font, using pillow default")
        return ImageFont.load_default()

    def get_image_for_icon(self):
        return self.button.deck.create_icon_for_key(index=self.button.index, colors=self.cockpit_color, texture=self.cockpit_texture)

    def get_image(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        image = self.get_image_for_icon()

        if image is None:
            logger.warning(f"button {self.button_name()}: {type(self).__name__} no image")
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
            if self.button._activation is not None and not self.button._activation.is_valid():
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

        return self.overlay_text_new(image, self._label)

    def overlay_text_new(self, image, text: TextWithVariables):
        if text is None:
            logger.debug(f"button {self.button_name()}: no text to lay over")
            return image

        logger.debug(f"button {self.button_name()}: text is from {text.prefix}: {text.message}")

        message = text.get_text()
        if message is None:
            logger.debug(f"button {self.button_name()}: no text")
            return image

        text_size = int(text.size * image.width / 72) if text.prefix == CONFIG_KW.LABEL.value else int(text.size)
        text_font = text.font
        if self.button.is_managed() and text.prefix == CONFIG_KW.TEXT.value:
            txtmod = self.button.manager.get("text-modifier", "dot").lower()
            if txtmod in ["std", "standard"]:  # QNH Std
                text_font = "AirbusFCU"  # hardcoded

        font = self.get_font(text_font, text_size)
        image = image.copy()  # we will add text over it
        draw = ImageDraw.Draw(image)
        inside = round(0.04 * image.width + 0.5)
        w = image.width / 2
        p = "m"
        a = "center"
        if text.position[0] == "l":
            w = inside
            p = "l"
            a = "left"
        elif text.position[0] == "r":
            w = image.width - inside
            p = "r"
            a = "right"
        h = image.height / 2
        if text.position[1] == "t":
            h = inside + text_size / 2
        elif text.position[1] == "b":
            h = image.height - inside - text_size / 2
        # logger.debug(f"position {(w, h)}")
        draw.multiline_text((w, h), text=message, font=font, anchor=p + "m", align=a, fill=text.color)  # (image.width / 2, 15)
        return image

    def clean(self):
        """
        Removes icon from deck
        """
        self.button.deck.fill_empty(self.button.index)
        self.clean_cache()

    def describe(self) -> str:
        return "The representation creates an empty icon for other image display."


class Icon(IconBase):

    REPRESENTATION_NAME = "icon"
    REQUIRED_DECK_FEEDBACKS = DECK_FEEDBACK.IMAGE

    # PARAMETERS = {"icon": {"type": "icon", "prompt": "Icon"}, "frame": {"type": "icon", "prompt": "Frame"}}
    PARAMETERS = {"icon": {"type": "icon", "prompt": "Icon"}}

    def __init__(self, button: "Button"):
        IconBase.__init__(self, button=button)

        self.frame = self._config.get(CONFIG_KW.FRAME.value)

        self.icon = None
        deck = self.button.deck

        candidate_icon = self._config.get("icon")
        if candidate_icon is not None:
            self.icon = deck.cockpit.get_icon(candidate_icon)

        if self.icon is None:
            if self._config.get(NO_ICON, False):
                logger.debug(f"button {self.button_name()}: requested to no do icon")

        self._icon_cache = None

    def is_valid(self):
        if super().is_valid():  # so there is a button...
            if self.icon is not None:
                return True
            if self.cockpit_color is not None:
                return True
            logger.warning(f"button {self.button_name()}: {type(self).__name__}: no icon and no icon color")
        return False

    def get_image_for_icon(self):
        deck = self.button.deck
        image = deck.cockpit.get_icon_image(self.icon)
        if image is None:
            image = self.button.deck.create_icon_for_key(index=self.button.index, colors=self.cockpit_color, texture=self.cockpit_texture)
        else:
            image = deck.scale_icon_for_key(self.button.index, image, name=self.icon)  # this will cache it in the deck as well
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
            logger.warning(f"button {self.button_name()}: {type(self).__name__} no image")
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
            if self.button._activation is not None and not self.button._activation.is_valid():
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

        return self.overlay_text_new(image, self._label)

    def get_framed_icon(self):
        # We assume self.frame is a non null dict
        frame = self.frame.get("frame")
        frame_size = self.frame.get("frame-size")
        frame_content = self.frame.get("content-size")
        frame_position = self.frame.get("content-offset")

        this_button = f"{self.button_name()}: {type(self).__name__}"
        image = None
        deck = self.button.deck
        if frame is None or frame_size is None or frame_position is None or frame_content is None:
            logger.warning(f"button {this_button}: invalid frame {self.frame}, {frame}")
        else:
            image = deck.get_icon_background(
                name=this_button,
                width=frame_size[0],
                height=frame_size[1],
                texture_in=frame,
                color_in=self.cockpit_color,
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
            logger.debug(f"button {this_button}: {self.icon}, {frame}, {image}, {inside}, {box}")
            image.paste(inside, box)
            image = deck.scale_icon_for_key(self.button.index, image)
            return image
        return inside

    def describe(self) -> str:
        return "The representation places an icon with optional label overlay."


class IconColor(IconBase):
    """Uniform color or texture icon

    Attributes:
        REPRESENTATION_NAME: "icon-color"
    """

    REPRESENTATION_NAME = "icon-color"

    PARAMETERS = {"color": {"type": "string", "prompt": "Color"}, "texture": {"type": "icon", "prompt": "Texture"}}

    def __init__(self, button: "Button"):
        IconBase.__init__(self, button=button)

        self.icon_color = self.get_attribute("icon-color")
        self.icon_color = convert_color(self.icon_color)
        self.icon_texture = self.get_attribute("icon-texture")

    def get_image_for_icon(self):
        return self.button.deck.create_icon_for_key(index=self.button.index, colors=self.icon_color, texture=self.icon_texture)

    def describe(self) -> str:
        return "The representation places a uniform color or textured icon."


class IconText(IconColor):
    """Uniform color or texture icon with text laid over.-"""

    REPRESENTATION_NAME = "text"

    PARAMETERS = {
        "text": {"type": "string", "prompt": "Text"},
        "text-font": {"type": "font", "prompt": "Font"},
        "text-size": {"type": "integer", "prompt": "Size"},
        "text-color": {"type": "string", "prompt": "Color"},
        "text-position": {"type": "choice", "prompt": "Position", "choices": ["lt", "ct", "rt", "lm", "cm", "rm", "lb", "cb", "rb"]},
    }

    def __init__(self, button: "Button"):
        text_config = button._config.get(CONFIG_KW.TEXT.value)  # where to get text from
        # Now should be indented
        # - index: 9
        #   typ: push
        #   name: ATCCLR
        #   command: AirbusFBW/ATCCodeKeyCLR
        #   text:    <-- text is dict()
        #       text: CLR
        #       text-color: white
        if type(text_config) is not dict:
            # Handle this presentation structure (legacy, text unindented)
            # - index: 9
            #   typ: push
            #   name: ATCCLR
            #   command: AirbusFBW/ATCCodeKeyCLR
            #   text: CLR    <-- text is not dict()
            #   text-color: white
            text_config = button._config

        self.bg_texture = None
        self.bg_color = None
        self.notify = None
        self._text = None
        if text_config is not None:
            self._text = TextWithVariables(owner=button, config=text_config, prefix=CONFIG_KW.TEXT.value)

            self.bg_texture = self._text._config.get("text-bg-texture")
            self.bg_color = self._text._config.get("text-bg-color")
            self.notify = self._text._config.get("text-notify")

        IconColor.__init__(self, button=button)

        # Overwrite icon-* with text-bg-*
        if self.bg_color is not None:
            self.icon_color = convert_color(self.bg_color)
            self.icon_texture = None  # if there is a color, we do not use the texture, unless explicitely supplied

        if self.bg_texture is not None:
            self.icon_texture = self.bg_texture

    def get_variables(self) -> set:
        datarefs = set()
        if self._text is not None:
            datarefs = self._text.get_variables()
        return datarefs

    def get_image(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        image = super().get_image()
        if self.notify is not None:
            logger.info(f"notification from {self.button.name}: {self.notify} {self._text.message}")
        return self.overlay_text_new(image, self._text)

    def describe(self) -> str:
        return "The representation places an icon with optional text and label overlay."


class MultiTexts(IconText):
    """Same as TextIcon, except we select _text from a list (_milti_texts) based on button value."""

    REPRESENTATION_NAME = "multi-texts"

    PARAMETERS = {
        "multi-texts": {
            "type": "multi",
            "multi": {
                "text": {"type": "string", "prompt": "Text"},
                "text-font": {"type": "font", "prompt": "Font"},
                "text-size": {"type": "integer", "prompt": "Size"},
                "text-color": {"type": "string", "prompt": "Color"},
                "text-position": {"type": "choice", "prompt": "Position", "choices": ["lt", "ct", "rt", "lm", "cm", "rm", "lb", "cb", "rb"]},
            },
            "prompt": "Text list",
        }
    }

    def __init__(self, button: "Button"):
        IconText.__init__(self, button=button)
        multi_texts = self._config.get("multi-texts", [])
        self._multi_texts = []
        for text in multi_texts:
            self._multi_texts.append(TextWithVariables(owner=button, config=text, prefix=CONFIG_KW.TEXT.value))

    @property
    def num_texts(self):
        return len(self._multi_texts)

    def get_variables(self) -> set:
        datarefs = set()
        for text in self._multi_texts:
            drefs = text.get_variables()
            if len(drefs) > 0:
                datarefs = datarefs | drefs
        return datarefs

    def is_valid(self):
        if self._multi_texts is None:
            logger.warning(f"button {self.button_name()}: {type(self).__name__}: no icon")
            return False
        if self.num_texts == 0:
            logger.warning(f"button {self.button_name()}: {type(self).__name__}: no icon")
            return False
        return super().is_valid()

    def render(self):
        value = self.get_button_value()
        if value is None:
            logger.warning(f"button {self.button_name()}: {type(self).__name__}: no current value, no rendering")
            return None
        if type(value) in [str, int, float]:
            value = int(float(value))  # int('1.0') does not work
        else:
            logger.warning(f"button {self.button_name()}: {type(self).__name__}: complex value {value}")
            return None
        if self.num_texts > 0:
            self._text = self._multi_texts[value % self.num_texts]
            return super().render()
        else:
            logger.warning(f"button {self.button_name()}: {type(self).__name__}: icon not found {value}/{self.num_texts}")
        return None

    def describe(self) -> str:
        return "\n\r".join(
            [f"The representation produces an icon with text, text is selected from a list of {self.num_texts} texts bsaed on the button's value."]
        )


class MultiIcons(Icon):

    REPRESENTATION_NAME = "multi-icons"

    PARAMETERS = {"multi-icon": {"type": "multi", "multi": {"texture": {"type": "icon", "prompt": "Icon"}}, "prompt": "Icon list"}}

    def __init__(self, button: "Button"):
        Icon.__init__(self, button=button)

        self.multi_icons = self._config.get("icon-animate", [])  # type: ignore
        if len(self.multi_icons) == 0:
            self.multi_icons = self._config.get("multi-icons", [])
        else:
            logger.debug(f"button {self.button_name()}: {type(self).__name__}: animation sequence {len(self.multi_icons)}")

        if len(self.multi_icons) > 0:
            invalid = []
            for i in range(len(self.multi_icons)):
                icon = self.button.deck.cockpit.get_icon(self.multi_icons[i])
                if icon is not None:
                    self.multi_icons[i] = icon
                else:
                    logger.warning(f"button {self.button_name()}: {type(self).__name__}: icon not found {self.multi_icons[i]}")
                    invalid.append(i)
            for i in invalid:
                if i in self.multi_icons:
                    del self.multi_icons[i]
        else:
            logger.warning(f"button {self.button_name()}: {type(self).__name__}: no icon")

    def is_valid(self):
        if self.multi_icons is None or len(self.multi_icons) == 0:
            logger.warning(f"button {self.button_name()}: {type(self).__name__}: no icon")
            return False
        return super().is_valid()

    def num_icons(self):
        return len(self.multi_icons)

    def render(self):
        value = self.get_button_value()
        if value is None:
            logger.warning(f"button {self.button_name()}: {type(self).__name__}: no current value, no rendering")
            return None
        if type(value) in [str, int, float]:
            value = int(value)
        else:
            logger.warning(f"button {self.button_name()}: {type(self).__name__}: complex value {value}")
            return None
        if self.num_icons() > 0:
            if value >= 0 and value < self.num_icons():
                self.icon = self.multi_icons[value]
            else:
                self.icon = self.multi_icons[value % self.num_icons()]
            return super().render()
        else:
            logger.warning(f"button {self.button_name()}: {type(self).__name__}: icon not found {value}/{self.num_icons()}")
        return None

    def describe(self) -> str:
        return "\n\r".join([f"The representation produces an icon selected from a list of {len(self.multi_icons)} icons."])
