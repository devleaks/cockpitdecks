# Set of buttons for a deck
#
import logging

from .constant import convert_color
from .button import Button

logger = logging.getLogger("Page")
# logger.setLevel(logging.DEBUG)


class Page:
    """
    A Page is a collection of buttons.
    """
    def __init__(self, name: str, config: dict, deck: "Streamdeck"):
        self._config = {}
        self.name = config.get("name")
        self.deck = deck
        self.xp = self.deck.cockpit.xp  # shortcut alias

        self.default_label_font = config.get("default-label-font", deck.default_label_font)
        self.default_label_size = config.get("default-label-size", deck.default_label_size)
        self.default_label_color = config.get("default-label-color", deck.default_label_color)
        self.default_label_color = convert_color(self.default_label_color)
        self.default_icon_name = config.get("default-icon-color", name + deck.default_icon_name)
        self.default_icon_color = config.get("default-icon-color", deck.default_icon_color)
        self.default_icon_color = convert_color(self.default_icon_color)
        self.fill_empty = config.get("fill-empty-keys", deck.fill_empty)
        self.annunciator_style = config.get("annunciator-style", deck.annunciator_style)
        self.cockpit_color = config.get("cockpit-color", deck.cockpit_color)

        self.buttons = {}
        self.datarefs = {}

    def inspect(self):
        """
        This function is called on all buttons of this Page.
        """
        logger.info(f"Page {self.name} -- Statistics")
        for v in self.buttons.values():
            v.inspect()

    def add_button(self, idx, button: Button):
        if idx in self.buttons.keys():
            logger.error(f"add_button: button index {idx} already defined, ignoring {button.name}")
            return
        self.buttons[idx] = button
        logger.debug(f"add_button: page {self.name}: button {button.name} {idx} added")

    def register_datarefs(self, button: Button):
        for d in button.get_datarefs():
            if d not in self.datarefs:
                ref = self.xp.get_dataref(d)  # creates or return already defined dataref
                if ref is not None:
                    self.datarefs[d] = ref
                    self.datarefs[d].add_listener(button)
                    logger.debug(f"register_datarefs: page {self.name}: button {button.name} registered for new dataref {d}")
                else:
                    logger.error(f"register_datarefs: page {self.name}: button {button.name}: failed to create dataref {d}")
            else:
                self.datarefs[d].add_listener(button)
                logger.debug(f"register_datarefs: page {self.name}: button {button.name} registered for existing dataref {d}")
        logger.debug(f"register_datarefs: page {self.name}: button {button.name} registered")

    def dataref_changed(self, dataref):
        """
        For each button on this page, notifies the button if a dataref used by that button has changed.
        """
        if dataref.path in self.datarefs.keys():
            self.datarefs[dataref].notify()
        else:
            logger.warning(f"dataref_changed: page {self.name}: dataref {dataref.path} not found")

    def activate(self, idx: int):
        if idx in self.buttons.keys():
            self.buttons[idx].activate()
        else:
            logger.error(f"activate: page {self.name}: invalid button index {idx}")

    def render(self):
        """
        Renders this page on the deck
        """
        for button in self.buttons.values():
            button.render()
            logger.debug(f"render: page {self.name}: button {button.name} rendered")
        if self.fill_empty is not None:
            logger.debug(f"render: page {self.name}: fill empty keys {self.fill_empty}")
            for key in self.deck.available_keys:
                if key not in self.buttons.keys():
                    icon = None
                    if self.fill_empty.startswith("(") and self.fill_empty.endswith(")"):
                        colors = convert_color(self.fill_empty)
                        icon = self.deck.create_icon_for_key(key, colors=colors)
                    elif self.fill_empty in self.deck.icons.keys():
                        icon = self.deck.icons[self.fill_empty]
                    if icon is not None:
                        image = self.deck.pil_helper.to_native_format(self.deck.device, icon)
                        self.deck.device.set_key_image(key, image)
                    else:
                        logger.warning(f"render: page {self.name}: no fill icon")

    def clean(self):
        """
        Ask each button to stop rendering and clean its mess.
        """
        fill_empty = self.fill_empty if self.fill_empty is not None else "(0, 0, 0)"
        colors = None
        if fill_empty.startswith("(") and fill_empty.endswith(")"):
            colors = convert_color(fill_empty)

        for key, button in self.buttons.items():
            button.clean()
            if button.has_key_image():
                icon = None
                if colors is not None:
                    icon = self.deck.create_icon_for_key(key, colors=colors)
                elif self.fill_empty in self.deck.icons.keys():
                    icon = self.deck.icons[self.fill_empty]
                if icon is not None:
                    image = self.deck.pil_helper.to_native_format(self.deck.device, icon)
                    self.deck.device.set_key_image(key, image)
                else:
                    logger.warning(f"clean: page {self.name}: no fill icon")
