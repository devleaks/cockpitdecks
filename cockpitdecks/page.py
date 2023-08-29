# Set of buttons for a deck
#
import logging

from cockpitdecks import ID_SEP, ANNUNCIATOR_STYLES
from cockpitdecks.resources.color import convert_color
from cockpitdecks.simulator import DatarefSet, MAX_COLLECTION_SIZE
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
        self.sim = self.deck.cockpit.sim  # shortcut alias

        self.deck.cockpit.set_logging_level(__name__)
        self.load_defaults(config, deck)

        self.buttons = {}
        self.button_names = {}
        self.datarefs = {}
        self.dataref_collections = {}

    def get_id(self):
        return ID_SEP.join([self.deck.get_id(), self.name])

    def is_current_page(self):
        """
        Returns whether button is on current page
        """
        return self.deck.current_page == self

    def get_button_value(self, name):
        a = name.split(ID_SEP)
        if len(a) > 0:
            if a[0] == self.name:
                b = a[1].split(":")   # button-name:variable-name
                if b[0] in self.button_names.keys():
                    return self.button_names[b[0]].get_button_value(":".join(b[1:]) if len(b) > 1 else None)
                else:
                    logger.warning(f"so such button {b[0]} in {self.buttons.keys()}")
            else:
                logger.warning(f"not my page {a[0]} ({self.name})")
        else:
            logger.warning(f"invalid name {name}")
        return None

    def load_defaults(self, config: dict, base):
        self.default_label_font = config.get("default-label-font", base.default_label_font)
        self.default_label_size = config.get("default-label-size", base.default_label_size)
        self.default_label_color = config.get("default-label-color", base.default_label_color)
        self.default_label_color = convert_color(self.default_label_color)
        self.default_label_position = config.get("default-label-position", base.default_label_position)
        self.default_icon_name = config.get("default-icon-color", self.name + base.default_icon_name)
        self.default_icon_texture = config.get("default-icon-texture", base.default_icon_texture)
        self.default_icon_color = config.get("default-icon-color", base.default_icon_color)
        self.default_icon_color = convert_color(self.default_icon_color)
        self.default_annun_texture = config.get("default-annunciator-texture", base.default_annun_texture)
        self.default_annun_color = config.get("default-annunciator-color", base.default_annun_color)
        self.default_annun_color = convert_color(self.default_annun_color)
        self.annunciator_style = config.get("annunciator-style", base.annunciator_style)
        self.annunciator_style = ANNUNCIATOR_STYLES(self.annunciator_style)
        self.cockpit_color = config.get("cockpit-color", base.cockpit_color)
        self.cockpit_color = convert_color(self.cockpit_color)
        self.cockpit_texture = config.get("cockpit-texture", base.cockpit_texture)
        self.fill_empty_keys = config.get("fill-empty-keys", base.fill_empty_keys)

    def load_buttons(self, buttons):
        for a in buttons:
            button = None

            # Where to place the button
            idx = Button.guess_index(a)
            if idx is None:
                logger.error(f"page {self.name}: button has no index, ignoring {a}")
                continue
            if idx not in self.deck.valid_indices():
                logger.error(f"page {self.name}: button has invalid index '{idx}' (valid={self.deck.valid_indices()}), ignoring '{a}'")
                continue

            # How the button will behave, it is does something
            aty = Button.guess_activation_type(a)
            if aty is None or aty not in self.deck.valid_activations(idx):
                logger.error(f"page {self.name}: button has invalid activation type {aty} for index {idx}, ignoring {a}")
                continue

            # How the button will be represented, if it is
            valid_representations = self.deck.valid_representations(idx)
            rty = Button.guess_representation_type(a, valid_representations)
            if rty not in valid_representations:
                logger.error(f"page {self.name}: button has invalid representation type {rty} for index {idx}, ignoring {a}")
                continue
            if rty == "none":
                logger.debug(f"page {self.name}: button has no representation but it is ok")

            button = Button(config=a, page=self)
            if button is not None:
                self.add_button(idx, button)
                logger.debug(f"..page {self.name}: added button index {idx} {button.name} ({aty}, {rty})..")


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
            logger.error(f"page {self.name}: button index {idx} already defined, ignoring {button.name}")
            return
        if button.name is not None and button.name in self.button_names.keys():
            logger.error(f"page {self.name}: button named {button.name} already defined, ignoring {button.name}")
            return
        self.buttons[idx] = button
        self.button_names[button.name] = button
        logger.debug(f"page {self.name}: button {idx} {button.name} added")

    def register_datarefs(self, button: Button):
        for d in button.get_datarefs():
            if d not in self.datarefs:
                ref = self.sim.get_dataref(d)  # creates or return already defined dataref
                if ref is not None:
                    self.datarefs[d] = ref
                    self.datarefs[d].add_listener(button)
                    logger.debug(f"page {self.name}: button {button.name} registered for new dataref {d}")
                else:
                    logger.error(f"page {self.name}: button {button.name}: failed to create dataref {d}")
            else:  # dataref already exists in list, just add this button as a listener
                self.datarefs[d].add_listener(button)
                logger.debug(f"page {self.name}: button {button.name} registered for existing dataref {d}")
        logger.debug(f"page {self.name}: button {button.name} datarefs registered")

    def register_dataref_collections(self, button: Button):
        # Transform dataref paths into Dataref().
        for name, colldesc in button.get_dataref_collections().items():
            collection = {}
            for d in colldesc.get("datarefs"):
                if len(collection) >= MAX_COLLECTION_SIZE:
                    continue
                ref = self.sim.get_dataref(d)  # creates or return already defined dataref
                if ref is not None:
                    ref.add_listener(button.sim.collector)
                    collection[d] = ref  # ref DO NOT get added to page datarefs collection
                    logger.debug(f"page {self.name}: button {button.name} added dataref {d} to collection {name}")
                else:
                    logger.error(f"page {self.name}: button {button.name}: failed to create dataref {d} for collection {name}")
            if len(collection) >= MAX_COLLECTION_SIZE:
                logger.warning(f"page {self.name}: button {button.name}: collection: {name}: too many datarefs ({len(colldesc[0])}, maximum is {MAX_COLLECTION_SIZE})")
            dc = DatarefSet(datarefs=collection, sim=button.sim, name=name)
            dc.add_listener(button)
            dc.set_dataref = colldesc.get("set_dataref")
            dc.expire = colldesc.get("expire")
            self.dataref_collections[name] = dc
            logger.debug(f"page {self.name}: button {button.name} collection {name} registered")
        logger.debug(f"page {self.name}: button {button.name} collections registered")

    def dataref_changed(self, dataref):
        """
        For each button on this page, notifies the button if a dataref used by that button has changed.
        """
        if dataref is None:
            logger.error(f"page {self.name}: no dataref")
            return
        if dataref.path not in self.datarefs.keys():
            logger.warning(f"page {self.name}: dataref {dataref.path} not found")
            return
        self.datarefs[dataref].notify()

    def activate(self, idx: int):
        if idx in self.buttons.keys():
            self.buttons[idx].activate()
        else:
            logger.error(f"page {self.name}: invalid button index {idx}")

    def render(self):
        """
        Renders this page on the deck
        """
        for button in self.buttons.values():
            button.render()
            logger.debug(f"page {self.name}: button {button.name} rendered")

        if not self.fill_empty_keys:
            return

        for key in filter(lambda b: b not in self.buttons.keys(), self.deck.valid_indices(with_icon=True)):
            self.deck.fill_empty(key)

    def print(self):
        self.deck.print_page(self)

    def clean(self):
        """
        Ask each button to stop rendering and clean its mess.
        """
        logger.debug(f"page {self.name}: cleaning..")
        for button in self.buttons.values():
            button.clean()  # knows how to clean itself
        logger.debug(f"page {self.name}: ..done")

    def terminate(self):
        """
        Cleans all individual buttons on the page
        """
        if self.is_current_page() and self.sim is not None:
            self.sim.remove_datarefs_to_monitor(self.datarefs)
        self.clean()
        self.buttons = {}
