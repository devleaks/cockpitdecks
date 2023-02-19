# Set of buttons for a deck
#
import logging

from .constant import ID_SEP
from .color import convert_color
from .button import Button

logger = logging.getLogger("Page")
# logger.setLevel(logging.DEBUG)


class Page:
    """
    A Page is a collection of buttons.
    """
    def __init__(self, name: str, config: dict, deck: "Streamdeck"):
        self._config = config
        self.name = name
        self.deck = deck
        self.xp = self.deck.cockpit.xp  # shortcut alias

        self.load_defaults(config, deck)
        # self.default_label_font = config.get("default-label-font", deck.default_label_font)
        # self.default_label_size = config.get("default-label-size", deck.default_label_size)
        # self.default_label_color = config.get("default-label-color", deck.default_label_color)
        # self.default_label_color = convert_color(self.default_label_color)
        # self.default_icon_name = config.get("default-icon-color", name + deck.default_icon_name)
        # self.default_icon_color = config.get("default-icon-color", deck.default_icon_color)
        # self.default_icon_color = convert_color(self.default_icon_color)
        # self.light_off_intensity = config.get("light-off", deck.light_off_intensity)
        # self.fill_empty_keys = config.get("fill-empty-keys", deck.fill_empty_keys)
        # self.empty_key_fill_color = config.get("empty-key-fill-color", deck.empty_key_fill_color)
        # self.empty_key_fill_color = convert_color(self.empty_key_fill_color)
        # self.empty_key_fill_icon = config.get("empty-key-fill-icon", deck.empty_key_fill_icon)
        # self.annunciator_style = config.get("annunciator-style", deck.annunciator_style)
        # self.cockpit_color = config.get("cockpit-color", deck.cockpit_color)
        # self.cockpit_color = convert_color(self.cockpit_color)

        self.buttons = {}
        self.datarefs = {}

    def get_id(self):
        return ID_SEP.join([self.deck.get_id(), self.name])

    def get_button_value(self, name):
        a = name.split(ID_SEP)
        if len(a) > 0:
            if a[0] == self.name:
                if a[1] in self.buttons.keys():
                    return self.buttons[a[1]].get_button_value(ID_SEP.join(a[1:]))
                else:
                    logger.warning(f"get_button_value: so such button {a[1]}")
            else:
                logger.warning(f"get_button_value: not my page {a[0]} ({self.name})")
        else:
            logger.warning(f"get_button_value: invalid name {name}")

    def load_defaults(self, config, src):
        self.default_label_font = config.get("default-label-font", src.default_label_font)
        self.default_label_size = config.get("default-label-size", src.default_label_size)
        self.default_label_color = config.get("default-label-color", src.default_label_color)
        self.default_label_color = convert_color(self.default_label_color)
        self.default_icon_name = config.get("default-icon-color", self.name + src.default_icon_name)
        self.default_icon_color = config.get("default-icon-color", src.default_icon_color)
        self.default_icon_color = convert_color(self.default_icon_color)
        self.light_off_intensity = config.get("light-off", src.light_off_intensity)
        self.fill_empty_keys = config.get("fill-empty-keys", src.fill_empty_keys)
        self.empty_key_fill_color = config.get("empty-key-fill-color", src.empty_key_fill_color)
        self.empty_key_fill_color = convert_color(self.empty_key_fill_color)
        self.empty_key_fill_icon = config.get("empty-key-fill-icon", src.empty_key_fill_icon)
        self.annunciator_style = config.get("annunciator-style", src.annunciator_style)
        self.cockpit_color = config.get("cockpit-color", src.cockpit_color)
        self.cockpit_color = convert_color(self.cockpit_color)

    def inspect(self, what: str = None):
        """
        This function is called on all buttons of this Page.
        """
        logger.info(f"Page {self.name} -- {what}")
        for v in self.buttons.values():
            v.inspect(what)

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
        if self.fill_empty_keys:
            busy_keys = [str(i) for i in self.buttons.keys()]
            for key in self.deck.valid_indices_with_image():
                if key not in busy_keys:
                    image = None
                    if self.empty_key_fill_icon in self.deck.icons.keys():
                        image = self.deck.icons[self.empty_key_fill_icon]
                    elif self.empty_key_fill_color is not None:
                        class Butemp:
                            index = key
                        button = Butemp()
                        # setattr(button, "index", key)
                        image = self.deck.create_icon_for_key(button, colors=self.empty_key_fill_color)
                    if image is not None:
                        self.deck._send_key_image_to_device(key, image)
                    else:
                        logger.warning(f"render: page {self.name}: {key}: no fill icon")

    def clean(self):
        """
        Ask each button to stop rendering and clean its mess.
        """
        logger.debug(f"clean: page {self.name}: cleaning..")
        for button in self.buttons.values():
            button.clean()  # knows how to clean itself
        logger.debug(f"clean: page {self.name}: ..done")
