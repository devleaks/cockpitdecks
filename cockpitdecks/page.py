# Set of buttons for a deck
#
import logging

from .constant import ID_SEP, ANNUNCIATOR_STYLES
from .color import convert_color
from .button import Button

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


class Page:
    """
    A Page is a collection of buttons.
    """
    def __init__(self, name: str, config: dict, deck: "Deck"):
        self.logging_level = "INFO"
        self._config = config
        self.name = name
        self.deck = deck
        self.xp = self.deck.cockpit.xp  # shortcut alias

        self.deck.cockpit.set_logging_level(__name__)
        self.load_defaults(config, deck)

        self.buttons = {}
        self.button_names = {}
        self.datarefs = {}

    def get_id(self):
        return ID_SEP.join([self.deck.get_id(), self.name])

    def get_button_value(self, name):
        a = name.split(ID_SEP)
        if len(a) > 0:
            if a[0] == self.name:
                b = a[1].split(":")   # button-name:variable-name
                if b[0] in self.button_names.keys():
                    return self.button_names[b[0]].get_button_value(":".join(b[1:]) if len(b) > 1 else None)
                else:
                    logger.warning(f"get_button_value: so such button {b[0]} in {self.buttons.keys()}")
            else:
                logger.warning(f"get_button_value: not my page {a[0]} ({self.name})")
        else:
            logger.warning(f"get_button_value: invalid name {name}")
        return None

    def set_logging_level(self):
        if self.deck is not None and self.deck.cockpit is not None and self.deck.cockpit.needs_debug(type(self).__name__):
            logger.setLevel(logging.DEBUG)
            logger.debug(f"set_logging_level: {type(self).__name__ } set to debug")

    def load_defaults(self, config: dict, base):
        self.default_label_font = config.get("default-label-font", base.default_label_font)
        self.default_label_size = config.get("default-label-size", base.default_label_size)
        self.default_label_color = config.get("default-label-color", base.default_label_color)
        self.default_label_color = convert_color(self.default_label_color)
        self.default_label_position = config.get("default-label-position", base.default_label_position)
        self.default_icon_name = config.get("default-icon-color", self.name + base.default_icon_name)
        self.default_icon_color = config.get("default-icon-color", base.default_icon_color)
        self.default_icon_color = convert_color(self.default_icon_color)
        self.fill_empty_keys = config.get("fill-empty-keys", base.fill_empty_keys)
        self.annunciator_style = config.get("annunciator-style", base.annunciator_style)
        self.annunciator_style = ANNUNCIATOR_STYLES(self.annunciator_style)
        self.cockpit_color = config.get("cockpit-color", base.cockpit_color)
        self.cockpit_color = convert_color(self.cockpit_color)
        self.cockpit_texture = config.get("cockpit-texture")

    def get_default_icon(self):
        # Add default icon for this page
        if not hasattr(self.deck, "get_default_icon"): # deck cannot display icon anyway
            return None
        deck = self.deck
        icons = self.deck.icons
        if self.default_icon_name not in icons.keys():
            image = deck.cockpit.mk_icon_bg(self.cockpit_texture, self.default_icon_color, f"Page {self.name}")
            if deck.device is not None:
                icons[self.default_icon_name] = deck.pil_helper.create_scaled_image(deck.device, image, margins=[0, 0, 0, 0])
            else:
                icons[self.default_icon_name] = image
            logger.debug(f"get_default_icon: page {self.name}: created default {self.default_icon_name} icon")
        return icons[self.default_icon_name]

    def load_buttons(self, buttons):
        for a in buttons:
            button = None

            # Where to place the button
            idx = Button.guess_index(a)
            if idx is None:
                logger.error(f"load: page {self.name}: button has no index, ignoring {a}")
                continue
            if str(idx) not in self.deck.valid_indices():
                logger.error(f"load: page {self.name}: button has invalid index '{idx}', ignoring {a}")
                continue

            # How the button will behave, it is does something
            bty = Button.guess_activation_type(a)
            if bty is None or bty not in self.deck.valid_activations(str(idx)):
                logger.error(f"load: page {self.name}: button has invalid activation type {bty} for index {idx}, ignoring {a}")
                continue

            # How the button will be represented, if it is
            valid_representations = self.deck.valid_representations(str(idx))
            bty = Button.guess_representation_type(a, valid_representations)
            if bty not in valid_representations:
                logger.error(f"load: page {self.name}: button has invalid representation type {bty} for index {idx}, ignoring {a}")
                continue
            if bty == "none":
                logger.debug(f"load: page {self.name}: button has no representation but it is ok")

            button = Button(config=a, page=self)
            if button is not None:
                self.add_button(idx, button)
                logger.debug(f"load: ..page {self.name}: added button index {idx} {button.name}..")


    def inspect(self, what: str = None):
        """
        This function is called on all buttons of this Page.
        """
        logger.info(f"-"*60)
        logger.info(f"Page {self.name} -- {what}")
        if what == "print":
            self.print()
        else:
            for v in self.buttons.values():
                v.inspect(what)

    def add_button(self, idx, button: Button):
        if idx in self.buttons.keys():
            logger.error(f"add_button: page {self.name}: button index {idx} already defined, ignoring {button.name}")
            return
        if button.name is not None and button.name in self.button_names.keys():
            logger.error(f"add_button: page {self.name}: button named {button.name} already defined, ignoring {button.name}")
            return
        self.buttons[idx] = button
        self.button_names[button.name] = button
        logger.debug(f"add_button: page {self.name}: button {idx} {button.name} added")

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
            else:  # dataref already exists in list, just add this button as a listener
                self.datarefs[d].add_listener(button)
                logger.debug(f"register_datarefs: page {self.name}: button {button.name} registered for existing dataref {d}")
        logger.debug(f"register_datarefs: page {self.name}: button {button.name} registered")

    def dataref_changed(self, dataref):
        """
        For each button on this page, notifies the button if a dataref used by that button has changed.
        """
        if dataref is None:
            logger.error(f"dataref_changed: page {self.name}: no dataref")
            return
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
                    if self.default_icon_name in self.deck.icons.keys():
                        image = self.deck.icons[self.default_icon_name]
                    elif self.default_icon_color is not None:
                        class Butemp:
                            index = key
                        button = Butemp()
                        # setattr(button, "index", key)
                        image = self.deck.create_icon_for_key(button, colors=self.default_icon_color)
                    if image is None:
                        image = self.get_default_icon()
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

    def print(self):
        self.deck.print_page(self)

    def is_current_page(self):
        """
        Returns whether button is on current page
        """
        return self.deck.current_page == self

    def terminate(self):
        if self.is_current_page() and self.xp is not None:
            self.xp.remove_datarefs_to_monitor(self.datarefs)
        self.clean()
        self.buttons = {}
