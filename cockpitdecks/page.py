# Set of buttons for a deck
#
import datetime
import logging
from typing import Dict

from cockpitdecks import ID_SEP
from cockpitdecks.simulator import Dataref, DatarefSet, MAX_COLLECTION_SIZE
from .button import Button, DECK_DEF

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


class Page:
    """
    A Page is a collection of buttons.
    """

    def __init__(self, name: str, config: dict, deck: "Deck"):
        self._config = config
        self.name = name
        self.deck = deck
        self.sim = self.deck.cockpit.sim  # shortcut alias

        self.deck.cockpit.set_logging_level(__name__)

        self.buttons: Dict[str, Button] = {}
        self.button_names = {}
        self.datarefs: Dict[str, Dataref] = {}
        self.dataref_collections: Dict[str, DatarefSet] = {}

        self.fill_empty_keys = config.get("fill-empty-keys", True)

    def get_id(self):
        return ID_SEP.join([self.deck.get_id(), self.name])

    def is_current_page(self):
        """
        Returns whether button is on current page
        """
        return self.deck.current_page == self

    def get_attribute(self, attribute: str, silence: bool = False):
        val = self._config.get(attribute)
        if val is not None:
            return val
        ATTRNAME = "_defaults"
        val = None
        if hasattr(self, ATTRNAME):
            ld = getattr(self, ATTRNAME)
            if isinstance(ld, dict):
                val = ld.get(attribute)
        return val if val is not None else self.deck.get_attribute(attribute, silence=silence)

    def merge_attributes(self, attributes):
        # mainly aimed at merging includes' attributes to page's
        # merging order of includes is random
        ATTRNAME = "_defaults"
        if not hasattr(self, ATTRNAME):
            setattr(self, ATTRNAME, dict())
        ld = getattr(self, ATTRNAME)
        if isinstance(ld, dict) and isinstance(attributes, dict):
            setattr(self, ATTRNAME, ld | attributes)

    def get_dataref_value(self, dataref, default=None):
        d = self.datarefs.get(dataref)
        if d is None:
            logger.warning(f"page {self.name}: {dataref} not found")
            return None
        return d.current_value if d.current_value is not None else default

    def get_button_value(self, name):
        a = name.split(ID_SEP)
        if len(a) > 0:
            if a[0] == self.name:
                b = a[1].split(":")  # button-name:variable-name
                if b[0] in self.button_names.keys():
                    return self.button_names[b[0]].get_button_value(":".join(b[1:]) if len(b) > 1 else None)
                else:
                    logger.warning(f"so such button {b[0]} in {self.buttons.keys()}")
            else:
                logger.warning(f"not my page {a[0]} ({self.name})")
        else:
            logger.warning(f"invalid name {name}")
        return None

    def load_buttons(self, buttons):
        for button_config in buttons:
            button = None

            # Where to place the button
            idx = Button.guess_index(button_config)
            if idx is None:
                logger.error(f"page {self.name}: button has no index, ignoring {button_config}")
                continue
            if idx not in self.deck.valid_indices():
                logger.error(f"page {self.name}: button has invalid index '{idx}' (valid={self.deck.valid_indices()}), ignoring '{button_config}'")
                continue

            # How the button will behave, it is does something
            aty = Button.guess_activation_type(button_config)
            if aty is None or aty not in self.deck.valid_activations(idx):
                logger.error(f"page {self.name}: button has invalid activation type {aty} not in {self.deck.valid_activations(idx)} for index {idx}, ignoring {button_config}")
                continue

            # How the button will be represented, if it is
            rty = Button.guess_representation_type(button_config)
            if rty not in  self.deck.valid_representations(idx):
                logger.error(f"page {self.name}: button has invalid representation type {rty} for index {idx}, ignoring {button_config}")
                continue
            if rty == "none":
                logger.debug(f"page {self.name}: button has no representation but it is ok")

            button_config[DECK_DEF] = self.deck.get_deck_button_definition(idx)
            button = Button(config=button_config, page=self)
            if button is not None:
                self.add_button(idx, button)
                logger.debug(f"..page {self.name}: added button index {idx} {button.name} ({aty}, {rty})..")

    def inspect(self, what: str | None = None):
        """
        This function is called on all buttons of this Page.
        """
        logger.info(f"-" * 60)
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
            collection: Dict[str, Dataref] = {}
            for d in colldesc.get("datarefs"):
                if len(collection) >= MAX_COLLECTION_SIZE:
                    continue
                ref = self.sim.get_dataref(d)  # creates or return already defined dataref
                if ref is not None:
                    collection[d] = ref  # ref DO NOT get added to page datarefs collection
                    logger.debug(f"page {self.name}: button {button.name} added dataref {d} to collection {name}")
                else:
                    logger.error(f"page {self.name}: button {button.name}: failed to create dataref {d} for collection {name}")
            if len(collection) > MAX_COLLECTION_SIZE:
                logger.warning(
                    f"page {self.name}: button {button.name}: collection: {name}: too many datarefs ({len(colldesc['datarefs'])}, maximum is {MAX_COLLECTION_SIZE})"
                )
            dc = DatarefSet(datarefs=collection, sim=button.sim, name=name)
            dc.add_listener(button)
            dc.set_set_dataref(colldesc.get("set-dataref"))
            dc.set_expiration(colldesc.get("expire"))
            dc.set_collect_time(colldesc.get("collection-duration"))
            self.dataref_collections[name] = dc
            logger.debug(f"page {self.name}: button {button.name} collection {name} registered")
        logger.debug(f"page {self.name}: button {button.name} collections registered")

    # def activate(self, idx: str):
    #     if idx in self.buttons.keys():
    #         self.buttons[idx].activate(state=False)
    #     else:
    #         logger.error(f"page {self.name}: invalid button index {idx}")

    def render(self):
        """
        Renders this page on the deck
        """
        for button in self.buttons.values():
            button.render()
            logger.debug(f"page {self.name}: button {button.name} rendered")

        if not self.fill_empty_keys:
            return

        for key in filter(
            lambda b: b not in self.buttons.keys(),
            self.deck.valid_indices(with_icon=True),
        ):
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
        for key in filter(
            lambda b: b not in self.buttons.keys(),
            self.deck.valid_indices(with_icon=True),
        ):
            self.deck.clean_empty(key)
        logger.debug(f"page {self.name}: ..done")

    def terminate(self):
        """
        Cleans all individual buttons on the page
        """
        if self.is_current_page() and self.sim is not None:
            self.sim.remove_collections_to_monitor(self.dataref_collections)
            self.sim.remove_datarefs_to_monitor(self.datarefs)
        self.clean()
        self.buttons = {}
