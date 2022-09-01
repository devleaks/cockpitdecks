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

from .constant import add_ext, CONFIG_DIR, ICONS_FOLDER, FONTS_FOLDER

logger = logging.getLogger("Button")


class Button:

    def __init__(self, config: dict, deck: "Streamdeck"):

        self.deck = deck
        self.name = config.get("name", f"bnt-{config['index']}")
        self.index = config.get("index")

        self.pressed_count = 0
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

        self.icon = config.get("icon", "icon")
        if self.icon is not None:
            self.icon = add_ext(self.icon, ".png")
            if self.icon not in self.deck.icons.keys():
                logger.warning(f"__init__: button {self.name}: icon not found {self.icon}")

        self.icons = config.get("icons")
        if self.icons is not None:
            for i in range(len(self.icons)):
                self.icons[i] = add_ext(self.icons[i], ".png")
                if self.icons[i] not in self.deck.icons.keys():
                    logger.warning(f"__init__: button {self.name}: icon not found {self.icons[i]}")

        if self.label_position[0] not in "lcr" or self.label_position[1] not in "tmb":
            logger.warning(f"__init__: button {self.name}: invalid label position code {self.label_position}, using default")
            self.label_position = "cm"

        # working variables
        self.previous_value = None
        self.current_value = None

        self.xp = self.deck.decks.xp  # shortcut alias

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

    def changed(self) -> bool:
        """
        Fetches button latest values and return True if value has changed
        """
        self.current_value = self.fetch()
        if self.current_value is None and self.previous_value is None:
            return True
        elif self.current_value is None and self.previous_value is not None:
            return True
        elif self.current_value is not None and self.previous_value is None:
            return True
        return self.previous_value == self.current_value

    def update(self, force: bool = False):
        """
        Renders button if it has changed
        """
        if force or self.changed():
            self.previous_value == self.current_value
            self.render()

    def fetch(self):
        """
        Read button value(s)
        """
        return 0

    def activate(self, state: bool):
        """
        Function that is executed when a button is pressed (state=True) or released (state=False)
        """
        if state:
            self.pressed_count = self.pressed_count + 1
        logger.debug(f"activate: button {self.name} activated ({state}, {self.pressed_count})")

    def get_font(self):
        """
        Helper function to get valid font, depending on button or global preferences
        """
        if self.label_font is not None:
            return self.deck.decks.fonts[self.label_font]
        elif self.deck.decks.default_font is not None:
            return self.deck.decks.fonts[self.deck.decks.default_font]

    def get_image(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation.
        """
        if self.icon in self.deck.icons.keys():
            image = self.deck.icons[self.icon]
            # Add label if any
            if self.label is not None:
                fontname = self.get_font()
                logger.debug(f"get_image: font {fontname}")
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

                logger.debug(f"get_image: position {(w, h)}")

                draw.text((w, h),  # (image.width / 2, 15)
                          text=self.label,
                          font=font,
                          anchor=p+"d",
                          fill="white")
            return image
        else:
            logger.warning(f"get_image: button {self.name} has no icon {self.icon}")
            logger.debug(f"{self.deck.icons.keys()}")
        return None

    def render(self):
        if self.deck is not None:
            self.deck.set_key_image(self)
        logger.debug(f"render: button {self.name} rendered")


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
            logger.debug(f"activate: button {self.name} change page to {self.name}")
            self.deck.change_page(self.name)


class ButtonPush(Button):
    """
    Execute command once when key pressed
    """

    def __init__(self, config: dict, deck: "Streamdeck"):
        Button.__init__(self, config=config, deck=deck)
        self.current_value = self.fetch()

    def is_valid(self):
        return super().is_valid() and (self.command is not None)

    def activate(self, state: bool):

        super().activate(state)
        if state:
            if self.is_valid():
                self.label = f"pressed {self.current_value}"
                self.xp.commandOnce(self.command)
                self.update()

    def fetch(self):
        """
        Read button value(s)
        """
        if self.dataref is not None:
            return self.xp.read(self.dataref)
        return self.pressed_count

    def get_image(self):
        """
        If button has more icons, cycle through them
        """
        if self.icons is not None and len(self.icons) > 1:
            self.icon = self.icons[ self.current_value % len(self.icons) ]
            logger.debug(f"get_image: button {self.name} get cycle icon {self.icon}")
        return super().get_image()


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

BUTTON_TYPES = {
    "none": Button,
    "page": ButtonPage,
    "push": ButtonPush,
    "dual": ButtonDual,
    "dir": ButtonPage
}