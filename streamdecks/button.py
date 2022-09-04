"""
Different button classes for different purpose.
Button base class does not perform any action, it mainly is an ABC.

Buttons do
1. Execute zero or more X-Plane command
2. Optionally update their representation to confirm the action

"""
import logging
import os

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .constant import add_ext, CONFIG_DIR, ICONS_FOLDER, FONTS_FOLDER, DEFAULT_ICON_NAME

logger = logging.getLogger("Button")


class Button:

    def __init__(self, config: dict, deck: "Streamdeck"):

        self.deck = deck
        self.pressed_count = 0

        self.name = config.get("name", f"bnt-{config['index']}")
        self.index = config.get("index")

        self.options = config.get("options", ["counter"])

        self.label = config.get("label")
        self.label_font = config.get("label-font")
        if self.deck:
            default_font_size = deck.decks.default_size
        self.label_size = int(config.get("label-size", default_font_size))
        self.label_position = config.get("label-position", "cm")
        self.label_color = config.get("label-color", "white")

        self.command = config.get("command")
        self.commands = config.get("commands")

        self.dataref = config.get("dataref")
        self.datarefs = config.get("datarefs")

        self.icon = config.get("icon", DEFAULT_ICON_NAME)
        if self.icon is not None:
            self.icon = add_ext(self.icon, ".png")
            if self.icon not in self.deck.icons.keys():
                logger.warning(f"__init__: button {self.name}: icon not found {self.icon}")

        self.multi_icons = config.get("multi-icons")
        if self.multi_icons is not None:
            for i in range(len(self.multi_icons)):
                self.multi_icons[i] = add_ext(self.multi_icons[i], ".png")
                if self.multi_icons[i] not in self.deck.icons.keys():
                    logger.warning(f"__init__: button {self.name}: icon not found {self.multi_icons[i]}")

        self.key_icon = self.icon  # Working icon that will be displayed, default to self.icon
                                   # If key icon should come from icons, will be selected later
        if self.label_position[0] not in "lcr" or self.label_position[1] not in "tmb":
            logger.warning(f"__init__: button {self.name}: invalid label position code {self.label_position}, using default")
            self.label_position = "cm"

        # working variables
        self.previous_value = None
        self.current_value = None

        self.xp = self.deck.decks.xp  # shortcut alias


        self.dataref_values = {}
        for d in self.get_datarefs():
            self.dataref_values[self.dataref] = None

        self.init()

    @classmethod
    def new(cls, config: dict, deck: "Streamdeck"):
        return cls(config=config, deck=deck)

    def init(self):
        """
        Install button
        """
        pass

    def is_valid(self) -> bool:
        """
        Validate button data once and for all
        """
        return (self.deck is not None) and (self.index is not None) and (self.icon is not None)

    def get_datarefs(self):
        """
        Returns all datarefs used by this button
        """
        r = []
        if self.dataref is not None:
            r.append(self.dataref)
        if self.datarefs is not None:
            for d in self.datarefs:
                r.append(d)
        return r

    def get_font(self):
        """
        Helper function to get valid font, depending on button or global preferences
        """
        if self.label_font is not None and self.label_font in self.deck.decks.fonts.keys():
            return self.deck.decks.fonts[self.label_font]
        elif self.deck.decks.default_font is not None and self.deck.decks.default_font in self.deck.decks.fonts.keys():
            logger.warning(f"get_font: label font not found, using {self.deck.decks.default_font}")
            return self.deck.decks.fonts[self.deck.decks.default_font]
        else:
            logger.error(f"get_font: font not found, tried {self.label_font}, {self.deck.decks.default_font}")
        return None

    def get_image(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation.
        """
        if self.key_icon in self.deck.icons.keys():
            image = self.deck.icons[self.key_icon]
            # Add label if any
            if self.label is not None:
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
                    if self.label_position[0] == "l":
                        w = inside
                        p = "l"
                    elif self.label_position[0] == "r":
                        w = image.width - inside
                        p = "r"
                    h = image.height / 2
                    if self.label_position[1] == "t":
                        h = inside + self.label_size
                    elif self.label_position[1] == "r":
                        h = image.height - inside
                    # logger.debug(f"get_image: position {(w, h)}")
                    draw.text((w, h),  # (image.width / 2, 15)
                              text=self.label,
                              font=font,
                              anchor=p+"d",
                              fill="white")
            return image
        else:
            logger.warning(f"get_image: button {self.name}: icon {self.key_icon} not found")
            # logger.debug(f"{self.deck.icons.keys()}")
        return None

    def dataref_changed(self, dataref, value):
        """
        One of its dataref has changed, records its value and provoke an update of its representation.
        """
        if dataref in self.dataref_values:
            if self.dataref_values[dataref] != value:
                self.dataref_values[dataref] = value
        else:
            logger.warning(f"dataref_changed: {dataref} not registered")
            self.dataref_values[dataref] = value
        self.render()

    def activate(self, state: bool):
        """
        Function that is executed when a button is pressed (state=True) or released (state=False) on the Stream Deck device
        """
        if state:
            self.pressed_count = self.pressed_count + 1
        # logger.debug(f"activate: button {self.name} activated ({state}, {self.pressed_count})")

    def render(self):
        if self.deck is not None:
            self.deck.set_key_image(self)
        # logger.debug(f"render: button {self.name} rendered")


class ButtonPage(Button):
    """
    When pressed, activation change to selected page.
    If new page is not found, issues a warning and remain on current page.
    """
    def __init__(self, config: dict, deck: "Streamdeck"):
        Button.__init__(self, config=config, deck=deck)

    def activate(self, state: bool):
        super().activate(state)
        if state:
            if self.name in self.deck.pages.keys():
                logger.debug(f"activate: button {self.name} change page to {self.name}")
                self.deck.change_page(self.name)
                self.previous_value = self.current_value
                self.current_value = self.name
            else:
                logger.warning(f"activate: button {self.name}: page not found {self.name}")


class ButtonPush(Button):
    """
    Execute command once when key pressed
    """
    def __init__(self, config: dict, deck: "Streamdeck"):
        Button.__init__(self, config=config, deck=deck)

    def is_valid(self):
        return super().is_valid() and (self.command is not None)

    def button_value(self):
        """
        Button ultimately returns one value that is either directly extracted from a single dataref,
        or computed from several dataref values (later).
        """
        if self.dataref is not None and self.dataref in self.dataref_values.keys():
            return self.dataref_values[self.dataref]
        elif "counter" in self.options:
            logger.debug(f"get_image: button {self.name} get cycle icon")
            return self.pressed_count
        return None

    def get_image(self):
        """
        If button has more icons, select one from button current value
        """
        if self.multi_icons is not None and len(self.multi_icons) > 1:
            value = self.button_value()
            if value is None:
                logger.debug(f"get_image: button {self.name}: current value is null, default to 0")
                value = 0

            value = int(value)
            if value < 0 or value >= len(self.multi_icons):
                logger.debug(f"get_image: button {self.name} invalid icon key {value} not in [0,{len(self.multi_icons)}], default to 0")
                value = 0
            else:
                value = value % len(self.multi_icons)
            self.key_icon = self.multi_icons[value]
        else:
            self.key_icon = self.icon
        return super().get_image()

    def activate(self, state: bool):
        super().activate(state)
        if state:
            if self.is_valid():
                # self.label = f"pressed {self.current_value}"
                self.xp.commandOnce(self.command)
                self.render()


class ButtonReload(Button):
    """
    Execute command while the key is pressed.
    Pressing starts the command, releasing stops it.
    """

    def __init__(self, config: dict, deck: "Streamdeck"):
        Button.__init__(self, config=config, deck=deck)

    def is_valid(self):
        return super().is_valid()

    def activate(self, state: bool):
        if state:
            if self.is_valid():
                self.deck.decks.reload_decks()

class ButtonDual(Button):
    """
    Execute command while the key is pressed.
    Pressing starts the command, releasing stops it.
    """

    def __init__(self, config: dict, deck: "Streamdeck"):
        Button.__init__(self, config=config, deck=deck)

    def is_valid(self):
        return super().is_valid() and (self.commands is not None) and (len(self.commands) > 1)

    def activate(self, state: bool):
        if state:
            if self.is_valid():
                self.xp.commandBegin(self.commands[0])
        else:
            if self.is_valid():
                self.xp.commandEnd(self.commands[1])
        self.render()

#
# Mapping butween button types and classes
#
BUTTON_TYPES = {
    "none": Button,
    "page": ButtonPage,
    "push": ButtonPush,
    "dual": ButtonDual,
    "reload": ButtonReload
}
