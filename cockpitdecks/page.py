# Set of buttons for a deck
#
import logging
from typing import Dict

from cockpitdecks import ID_SEP, DEFAULT_ATTRIBUTE_PREFIX
from cockpitdecks.decks.resources.decktype import DeckType
from cockpitdecks.resources.intvariables import INTERNAL_DATAREF
from cockpitdecks.simulator import SimulatorVariable
from .button import Button, DECK_BUTTON_DEFINITION

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
        self.button_names: Dict[str, Button] = {}
        self.simulator_variable: Dict[str, SimulatorVariable] = {}

        self.fill_empty_keys = config.get("fill-empty-keys", True)

    def get_id(self):
        return ID_SEP.join([self.deck.get_id(), self.name])

    def inc(self, name: str, amount: float = 1.0, cascade: bool = False):
        self.sim.inc_internal_variable(name=ID_SEP.join([self.get_id(), name]), amount=amount, cascade=cascade)

    def is_current_page(self):
        """
        Returns whether button is on current page
        """
        return self.deck.current_page == self

    def get_attribute(self, attribute: str, default=None, propagate: bool = True, silence: bool = True):
        default_attribute = attribute
        if not attribute.startswith(DEFAULT_ATTRIBUTE_PREFIX):
            if not attribute.startswith("cockpit-"):  # no "default" for global cockpit-* attributes
                default_attribute = DEFAULT_ATTRIBUTE_PREFIX + attribute

        # Is there such an attribute in the page defintion?
        value = self._config.get(attribute)

        if value is not None:  # found!
            if silence:
                logger.debug(f"page {self.name} returning {attribute}={value}")
            else:
                logger.info(f"page {self.name} returning {attribute}={value}")
            return self.deck.cockpit.convert_if_color_attribute(attribute=attribute, value=value, silence=silence)

        if propagate:
            if not silence:
                logger.info(f"page {self.name} propagate to deck for {attribute}")
            return self.deck.get_attribute(default_attribute, default=default, propagate=propagate, silence=silence)

        if not silence:
            logger.warning(f"page {self.name}: attribute not found {attribute}")

        return self.deck.cockpit.convert_if_color_attribute(attribute=attribute, value=default, silence=silence)

    def merge_attributes(self, attributes):
        # mainly aimed at merging includes' attributes to page's
        # merging order of includes is random
        ATTRNAME = "_defaults"
        if not hasattr(self, ATTRNAME):
            setattr(self, ATTRNAME, dict())
        ld = getattr(self, ATTRNAME)
        if isinstance(ld, dict) and isinstance(attributes, dict):
            setattr(self, ATTRNAME, ld | attributes)

    def get_simulator_variable_value(self, simulator_variable, default=None):
        d = self.simulator_variable.get(simulator_variable)
        if d is None:
            logger.warning(f"page {self.name}: {simulator_variable} not found")
            return None  # should return default?
        return d.value() if d.value() is not None else default

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

    def load_buttons(self, buttons: dict, deck_type: DeckType, add_to_page: bool = True) -> list:
        built = []
        for button_config in buttons:
            try:
                button = None

                # Where to place the button
                idx = Button.guess_index(button_config)
                if idx is None:
                    logger.error(f"page {self.name}: button has no index, ignoring {button_config}")
                    continue
                if idx not in deck_type.valid_indices():
                    logger.error(f"page {self.name}: button has invalid index '{idx}' (valid={deck_type.valid_indices()}), ignoring '{button_config}'")
                    continue

                # How the button will behave, it is does something
                aty = Button.guess_activation_type(button_config)
                valid_activations = deck_type.valid_activations(idx, source=self.deck.cockpit)
                if aty is None or aty not in valid_activations:
                    logger.error(
                        f"page {self.name}: button has invalid activation type {aty} not in {valid_activations} for index {idx}, ignoring {button_config}"
                    )
                    continue

                # How the button will be represented, if it is
                rty = Button.guess_representation_type(
                    button_config,
                    all_representations=self.deck.cockpit.all_representations,
                    all_hardware_representations=self.deck.cockpit.all_hardware_representations,
                )
                valid_representations = deck_type.valid_representations(idx, source=self.deck.cockpit)
                if rty not in valid_representations:
                    logger.error(
                        f"page {self.name}: button has invalid representation type {rty} not in {valid_representations} for index {idx}, ignoring {button_config}"
                    )
                    continue
                if rty == "none":
                    logger.debug(f"page {self.name}: button has no representation but it is ok")

                button_config[DECK_BUTTON_DEFINITION] = deck_type.get_button_definition(idx)
                button = Button(config=button_config, page=self)
                if button is not None:
                    if add_to_page:
                        self.add_button(idx, button)
                    built.append(button)
                    logger.debug(f"..page {self.name}: added button index {idx} {button.name} ({aty}, {rty})..")
            except:
                logger.warning(f"page {self.name}: could not add button button ({button_config}), ignored", exc_info=True)
        return built

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

    def register_simulator_variable(self, button: Button):
        # Declared string dataref must be create FIRST so that they get the proper type.
        # If they are later used (in expression), at least they were created with STRING type first.
        for d in button.get_string_datarefs():
            if d not in self.simulator_variable:
                ref = self.sim.get_variable(d, is_string=True)  # creates or return already defined dataref
                if ref is not None:
                    self.simulator_variable[d] = ref
                    self.simulator_variable[d].add_listener(button)
                    self.inc(INTERNAL_DATAREF.DATAREF_REGISTERED.value)
                    logger.debug(f"page {self.name}: button {button.name} registered for new string dataref {d} (is_string={ref.is_string})")
                else:
                    logger.error(f"page {self.name}: button {button.name}: failed to create string dataref {d}")
            else:  # dataref already exists in list, just add this button as a listener
                self.simulator_variable[d].add_listener(button)
                logger.debug(
                    f"page {self.name}: button {button.name} registered for existing string dataref {d} (is_string={self.simulator_variable[d].is_string})"
                )

        # Possible issue if a dataref is created here below and is a string dataref
        # ex. it appears in text: "${str-dref}", and str-dref is a previously "undeclared" string dataref
        for d in button.get_simulator_variable():
            if d not in self.simulator_variable:
                ref = self.sim.get_variable(d)  # creates or return already defined dataref
                if ref is not None:
                    self.simulator_variable[d] = ref
                    self.simulator_variable[d].add_listener(button)
                    self.inc(INTERNAL_DATAREF.DATAREF_REGISTERED.value)
                    logger.debug(f"page {self.name}: button {button.name} registered for new dataref {d}")
                else:
                    logger.error(f"page {self.name}: button {button.name}: failed to create dataref {d}")
            else:  # dataref already exists in list, just add this button as a listener
                self.simulator_variable[d].add_listener(button)
                logger.debug(f"page {self.name}: button {button.name} registered for existing dataref {d}")

        logger.debug(f"page {self.name}: button {button.name} datarefs registered")

    def unregister_simulator_variable(self, button: Button):
        for d in button.get_string_datarefs():
            ref = self.simulator_variable.get(d)
            if ref is not None:
                ref.remove_listener(button)

        for d in button.get_simulator_variable():
            ref = self.simulator_variable.get(d)
            if ref is not None:
                ref.remove_listener(button)

        logger.debug(f"page {self.name}: button {button.name} unregistered")

    def find_button(self, button_def):
        btns = list(filter(lambda b: b._def == button_def, self.buttons.values()))
        if len(btns) == 0:
            logger.warning(f"page {self.name}: no button found for definition {button_def}")
            return None
        if len(btns) > 1:
            logger.warning(f"page {self.name}: more than one button for definition {button_def}")
        return btns[0]

    def render(self):
        """
        Renders this page on the deck
        """
        for button in self.buttons.values():
            button.render()
            logger.debug(f"page {self.name}: button {button.name} rendered")

        self.inc(INTERNAL_DATAREF.PAGE_RENDER.value)

        if not self.fill_empty_keys:
            return

        for key in filter(lambda b: b not in self.buttons.keys(), self.deck.valid_indices(with_icon=True)):
            self.deck.fill_empty(key)

        # If virtual deck, we also need to fill unused hardware representations
        if self.deck.is_virtual_deck() and self.deck.is_connected():
            for key in filter(lambda b: b not in self.buttons.keys(), self.deck.deck_type.indices_with_hardware_representations()):
                self.deck.fill_empty_hardware_representation(key, self)

        if self.get_attribute("print-page-dir"):
            self.deck.print_page(self)

    def print(self):
        self.deck.print_page(self)

    def clean(self, disconnected: bool = False):
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
        # If virtual deck, we also need to fill unused hardware representations
        if self.deck.is_virtual_deck() and self.deck.is_connected():
            for key in filter(lambda b: b not in self.buttons.keys(), self.deck.deck_type.indices_with_hardware_representations()):
                self.deck.fill_empty_hardware_representation(key, self)
        logger.debug(f"page {self.name}: ..done")

    def terminate(self, disconnected: bool = False):
        """
        Cleans all individual buttons on the page
        """
        if self.is_current_page() and self.sim is not None:
            self.sim.remove_simulator_variable_to_monitor(self.simulator_variable)
        if not disconnected:
            self.clean()
        for button in self.buttons.values():
            self.unregister_simulator_variable(button)  # otherwise ref to old buttons remain...
        self.buttons = {}
        self.inc(INTERNAL_DATAREF.PAGE_CLEAN.value)
