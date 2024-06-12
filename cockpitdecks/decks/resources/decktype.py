import os
import logging
import json
from typing import List, Dict

from functools import reduce

from cockpitdecks import DECK_KW, Config, DECK_ACTIONS, DECK_FEEDBACK, DECK_BUTTON_TYPES
from cockpitdecks import DECKS_FOLDER, RESOURCES_FOLDER
from cockpitdecks.buttons.activation import get_activations_for
from cockpitdecks.buttons.activation.activation import Activation
from cockpitdecks.buttons.representation import get_representations_for
from cockpitdecks.buttons.representation.representation import Representation
from cockpitdecks.constant import VIRTUAL_DECK_DRIVER

loggerButtonType = logging.getLogger("ButtonType")
# loggerButtonType.setLevel(logging.DEBUG)

loggerDeckType = logging.getLogger("DeckType")
# loggerDeckType.setLevel(logging.DEBUG)

DECK_TYPE_LOCATION = os.path.join(os.path.dirname(__file__), DECKS_FOLDER, RESOURCES_FOLDER)
DECK_TYPE_GLOB = "*.new.yaml"


class DeckButton:
    """Defines a button on a deck, its capabilities, its representation.

    For web decks, adds position and sizes information.
    """

    def __init__(self, config: dict) -> None:
        self._config = config
        self.name = config.get(DECK_KW.NAME.value, config.get(DECK_KW.INT_NAME.value))

        self.index = config.get(DECK_KW.INDEX.value)
        self.prefix = config.get(DECK_KW.PREFIX.value, "")

        self.actions = config.get(DECK_KW.ACTION.value)
        self.feedbacks = config.get(DECK_KW.FEEDBACK.value)

        self.position = config.get(DECK_KW.POSITION.value)  # for web decks drawing
        self.sizes = config.get(DECK_KW.DIMENSION.value)

        self.range = config.get(DECK_KW.RANGE.value, [0, 0])  # for sliders

        self.init()

    def init(self):
        if self.actions is None or (type(self.actions) is str and self.actions.lower() == DECK_KW.NONE.value):
            self.actions = [DECK_KW.NONE.value]
        elif type(self.actions) not in [list, tuple]:
            self.actions = [self.actions]

        if self.feedbacks is None or (type(self.feedbacks) is str and self.feedbacks.lower() == DECK_KW.NONE.value):
            self.feedbacks = [DECK_KW.NONE.value]
        elif type(self.feedbacks) not in [list, tuple]:
            self.feedbacks = [self.feedbacks]

        self._name_is_int = True
        try:
            dummy = int(self.name)
        except ValueError:
            self._name_is_int = False

        loggerButtonType.debug(f"{self.prefix}/{self.name}: {self.valid_representations()}")

    def has_drawing(self):
        return self.position is not None and self.sizes is not None

    def valid_indices(self) -> list:
        if self.repeat == 0:
            return [self.prefix + self.name]
        if self._name_is_int:
            start = self.name
            return [self.prefix + str(i) for i in range(start, start + self.repeat)]
        loggerButtonType.warning(f"button type {self.name} cannot repeat from {self.name}")
        return [self.name]

    def has_layout(self) -> bool:
        return self._config.get(DECK_KW.LAYOUT.value) is not None

    def numeric_index(self, idx) -> int:
        if not self._name_is_int:
            loggerButtonType.warning(f"button index {idx} is not numeric")
        if self.prefix == "":
            return int(idx)
        if idx.startswith(self.prefix):
            return int(idx.replace(self.prefix, ""))
        return int(idx)

    def valid_activations(self) -> set:
        ret = [Activation]  # always valid
        for action in self.actions:
            ret = ret + get_activations_for(DECK_ACTIONS(action))
        return set([x.name() for x in ret if x is not None])  # remove duplicates, remove None

    def valid_representations(self) -> set:
        ret = [Representation]  # always valid
        for feedback in self.feedbacks:
            ret = ret + get_representations_for(DECK_FEEDBACK(feedback))
        return set([x.name() for x in ret if x is not None])  # remove duplicates, remove None

    def has_action(self, action: str) -> bool:
        return action in self.actions

    def has_feedback(self, feedback: str) -> bool:
        return feedback in self.feedbacks

    def has_no_feedback(self) -> bool:
        return (DECK_KW.NONE.value in self.feedbacks and len(self.feedbacks) == 1) or len(self.feedbacks) == 0

    def can_activate(self, activation: str) -> bool:
        return activation in self.valid_activations()

    def can_represent(self, representation: str) -> bool:
        return representation in self.valid_representations()

    def display_size(self, return_offset: bool = False):
        """Parses info from resources.decks.*.yaml"""
        if self.has_feedback(DECK_FEEDBACK.IMAGE.value) and self.image is not None:
            return self.image[0:2] if not return_offset else self.image[2:4]
        return None

    def desc(self):
        """Returns a flattened description of the button

        Ready to be used by web deck

        Returns:
            dict: ButtonDeck description, simply flattened for web decks
        """
        return {
            "name": self.name,
            "index": self.index,
            "prefix": self.prefix,
            "actions": self.actions,
            "feedbacks": self.feedbacks,
            "range": self.range,
            "position": self.position,
            "sizes": self.sizes,
        }


class DeckType(Config):
    """Description of a deck capabilities, including its representation for web decks

    Reads and parse deck template file"""

    def __init__(self, filename: str) -> None:
        Config.__init__(self, filename=filename)
        self.name = self[DECK_KW.NAME.value]
        self.driver = self[DECK_KW.DRIVER.value]
        self.buttons: Dict[str | int, DeckButton] = {}
        self.background = self[DECK_KW.BACKGROUND.value]
        self._special_displays = None  # cache
        self.count = 0
        self.init()

    def init(self):
        """Parses a deck definition file and build a list of what's available.

        Mainly a list of buttons, what can be done with each (action), and what the
        button can provide as a feedback.
        """
        cnt = 0
        for button_block in self[DECK_KW.BUTTONS.value]:
            self.buttons = self.buttons | self.parse_deck_button_block(button_block=button_block)
        loggerDeckType.debug(f"deck type {self.name}: buttons: {self.buttons.keys()}..")
        loggerDeckType.debug(f"..deck type {self.name} done")

        print(json.dumps(self.desc(), indent=2))

    def parse_deck_button_block(self, button_block) -> Dict[str | int, DeckButton]:
        """Parses a deck button definition block

        A DeckButton block defines either a single deck button (no repeat attribute)
        or a collection of similar buttons if there is a repeat attribute.
        """
        button_block[DECK_KW.INT_NAME.value] = "NO_NAME_" + str(self.count)  # assign technical name
        self.count = self.count + 1

        repeat = button_block.get(DECK_KW.REPEAT.value)
        if type(repeat) is int:
            repeat = [repeat, 1]
        layout = button_block.get(DECK_KW.LAYOUT.value)
        offset = layout.get(DECK_KW.OFFSET.value, [0, 0])
        spacing = layout.get(DECK_KW.SPACING.value, [0, 0])
        prefix = button_block.get(DECK_KW.PREFIX.value, "")
        start = button_block.get(DECK_KW.NAME.value)

        # this definition is for a single button
        if repeat is None or repeat == [1, 1]:
            name = prefix + str(start)
            return {
                name: DeckButton(
                    config={
                        DECK_KW.NAME.value: name,
                        DECK_KW.INDEX.value: start,
                        DECK_KW.PREFIX.value: button_block.get(DECK_KW.PREFIX.value),
                        DECK_KW.RANGE.value: button_block.get(DECK_KW.RANGE.value),
                        DECK_KW.ACTION.value: button_block.get(DECK_KW.ACTION.value),
                        DECK_KW.FEEDBACK.value: button_block.get(DECK_KW.FEEDBACK.value),
                        DECK_KW.POSITION.value: offset,
                        DECK_KW.DIMENSION.value: button_block.get(DECK_KW.DIMENSION.value, [0, 0]),
                    }
                )
            }

        # definition is a for a collection of similar buttons
        start = int(start)  # should be int, but no test
        button_types = {}
        idx = start
        for x in range(repeat[0]):
            for y in range(repeat[1]):
                name = prefix + str(idx)
                sizes = button_block.get(DECK_KW.DIMENSION.value, [0, 0])
                position = [0, 0]
                position[0] = offset[0] + x * (sizes[0] + spacing[0])
                position[1] = offset[1] + y * (sizes[1] + spacing[1])
                button_types[name] = DeckButton(
                    config={
                        DECK_KW.NAME.value: name,
                        DECK_KW.INDEX.value: idx,
                        DECK_KW.PREFIX.value: button_block.get(DECK_KW.PREFIX.value),
                        DECK_KW.RANGE.value: button_block.get(DECK_KW.RANGE.value),
                        DECK_KW.ACTION.value: button_block.get(DECK_KW.ACTION.value),
                        DECK_KW.FEEDBACK.value: button_block.get(DECK_KW.FEEDBACK.value),
                        DECK_KW.POSITION.value: position,
                        DECK_KW.DIMENSION.value: sizes,
                    }
                )
                idx = idx + 1

        return button_types

    def is_virtual_deck(self) -> bool:
        """Validate consistency between virtual deck parameters.

        Virtual decks need to provide additional information (like layout).
        We check for consistency between layout (used by user interface to create deck)
        and information for Cockpitdecks.

        Returns:
            bool: Virtual deck definition is consistent or not
        """
        return self.driver == VIRTUAL_DECK_DRIVER

    def get_virtual_deck_layout(self):
        if self.is_virtual_deck():
            return self.desc()
        return {}

    def special_displays(self):
        """Returns name of all special displays (i.e. not "keys")"""

        if self._special_displays is not None:
            return self._special_displays
        self._special_displays = []
        for b in self.store.get(DECK_KW.BUTTONS.value, []):
            if (
                DECK_KW.REPEAT.value not in b
                and b.get(DECK_KW.FEEDBACK.value, "") == DECK_FEEDBACK.IMAGE.value
                and b.get(DECK_FEEDBACK.IMAGE.value) is not None
            ):
                n = b.get(DECK_KW.NAME.value)
                if n is not None:
                    self._special_displays.append(n)
        return self._special_displays

    # Convenience function with simple relay to specific index
    # This functions are meant to be used at "Deck" level to check
    # when a button definition is presented:
    # Is the deck's button capable (from its definition)
    # to satify the button's definition.
    #
    def get_button_definition(self, index):
        if type(index) is int:
            index = str(index)
        return self.buttons.get(index)

    def get_index_prefix(self, index):
        b = self.get_button_definition(index)
        if b is not None:
            return b.prefix
        loggerDeckType.warning(f"deck {self.name}: no button index {index}")
        return None

    def get_index_numeric(self, index):
        # Useful to just get the int value of index
        b = self.get_button_definition(index)
        if b is not None:
            return b.get_index_numeric()
        loggerDeckType.warning(f"deck {self.name}: no button index {index}")
        return None

    def valid_indices(self, with_icon: bool = False):
        # If with_icon is True, only returns keys with image icon associted with it
        if with_icon:
            with_image = filter(
                lambda x: DECK_FEEDBACK.IMAGE.value in x.feedbacks,
                self.buttons.values(),
            )
            return set(reduce(lambda l, b: l.union(set(b.valid_indices())), with_image, set()))
        # else, returns all of them
        return list(self.buttons.keys())

    def valid_activations(self, index):
        b = self.get_button_definition(index)
        if b is not None:
            return b.valid_activations()
        loggerDeckType.warning(f"deck {self.name}: no button index {index}")
        return None

    def valid_representations(self, index):
        b = self.get_button_definition(index)
        if b is not None:
            return b.valid_representations()
        loggerDeckType.warning(f"deck {self.name}: no button index {index}")
        return None

    def has_no_feedback(self, index):
        b = self.get_button_definition(index)
        if b is not None:
            return b.has_no_feedback()
        loggerDeckType.warning(f"deck {self.name}: no button index {index}")
        return None

    def display_size(self, index, return_offset: bool = False):
        b = self.get_button_definition(index)
        if b is not None:
            return b.display_size(return_offset)
        loggerDeckType.warning(f"deck {self.name}: no button index {index}")
        return None

    def is_encoder(self, index) -> bool:
        b = self.get_button_definition(index)
        if b is not None:
            return b.is_encoder()
        loggerDeckType.warning(f"deck {self.name}: no button index {index}")
        return None

    def filter(self, query: dict) -> dict:
        res = []
        for what, value in query.items():
            for button in self[DECK_KW.BUTTONS.value]:
                if what == DECK_KW.ACTION.value:
                    if value in button[what]:
                        res.append(button)
                elif what == DECK_KW.FEEDBACK.value:
                    if value in button[what]:
                        res.append(button)
        # loggerDeckType.debug(f"filter {query} returns {res}")
        return res

    def desc(self):
        """Returns a flattened description of the deck

        Ready to be used by web deck

        Returns:
            dict: Deck description (DeckType), simply flattened for web decks
        """
        buttons = [b.desc() for b in self.buttons.values()]
        return {"name": self.name, "driver": self.driver, "buttons": buttons, "background": self.background}
