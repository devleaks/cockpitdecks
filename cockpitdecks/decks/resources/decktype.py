import logging

from functools import reduce

from cockpitdecks import KW, Config, DECK_ACTIONS, DECK_FEEDBACK
from cockpitdecks.buttons.activation import get_activations_for
from cockpitdecks.buttons.activation.activation import Activation
from cockpitdecks.buttons.representation import get_representations_for
from cockpitdecks.buttons.representation.representation import Representation

loggerButtonType = logging.getLogger("ButtonType")
# loggerButtonType.setLevel(logging.DEBUG)

loggerDeckType = logging.getLogger("DeckType")
# loggerDeckType.setLevel(logging.DEBUG)


class ButtonType:
    def __init__(self, config: dict) -> None:

        self.name = config.get(KW.NAME.value, config.get("_intname"))
        self.prefix = config.get(KW.PREFIX.value, "")
        self.repeat = int(config.get(KW.REPEAT.value, 0))

        self.actions = config.get(KW.ACTION.value)
        self.feedbacks = config.get(KW.VIEW.value)

        self.image = config.get(KW.IMAGE.value)

        self.init()

    def init(self):
        if self.actions is None or (type(self.actions) is str and self.actions.lower() == KW.NONE.value):
            self.actions = [KW.NONE.value]
        elif type(self.actions) not in [list, tuple]:
            self.actions = [self.actions]

        if self.feedbacks is None or (type(self.feedbacks) is str and self.feedbacks.lower() == KW.NONE.value):
            self.feedbacks = [KW.NONE.value]
        elif type(self.feedbacks) not in [list, tuple]:
            self.feedbacks = [self.feedbacks]

        self._name_is_int = True
        try:
            dummy = int(self.name)
        except ValueError:
            self._name_is_int = False

        loggerButtonType.debug(f"{self.prefix}/{self.name}: {self.valid_representations()}")

    def valid_indices(self) -> list:
        if self.repeat == 0:
            return [self.prefix + self.name]
        if self._name_is_int:
            start = self.name
            return [self.prefix + str(i) for i in range(start, start + self.repeat)]
        loggerButtonType.warning(f"button type {self.name} cannot repeat from {self.name}")
        return [self.name]

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
        return (KW.NONE.value in self.feedbacks and len(self.feedbacks) == 1) or len(self.feedbacks) == 0

    def can_activate(self, activation: str) -> bool:
        return activation in self.valid_activations()

    def can_represent(self, representation: str) -> bool:
        return representation in self.valid_representations()

    def display_size(self, return_offset: bool = False):
        """Parses info from resources.decks.*.yaml"""
        if self.has_feedback(DECK_FEEDBACK.IMAGE.value) and self.image is not None:
            return self.image[0:2] if not return_offset else self.image[2:4]
        return None

    def is_encoder(self):
        return self.has_action(DECK_ACTIONS.ENCODER.value)

class DeckType(Config):
    """reads and parse deck template file"""

    def __init__(self, filename: str) -> None:
        Config.__init__(self, filename=filename)
        self.name = self[KW.TYPE.value]
        self._buttons = {}
        self._special_displays = None  # cache
        self.init()

    def init(self):
        """Parses a deck definition file and build a list of what's available.

        Mainly a list of buttons, what can be done with each (action), and what the
        button can provide as a feedback.
        """
        cnt = 0
        for bdef in self[KW.BUTTONS.value]:
            bdef["_intname"] = "NO_NAME_" + str(cnt)
            cnt = cnt + 1
            button = ButtonType(bdef)
            for i in button.valid_indices():
                self._buttons[i] = button

        loggerDeckType.debug(f"deck type {self.name}: buttons: {self._buttons.keys()}..")
        loggerDeckType.debug(f"..deck type {self.name} done")

    def special_displays(self):
        """Returns name of all special displays (i.e. not "keys")"""

        if self._special_displays is not None:
            return self._special_displays
        self._special_displays = []
        for b in self.store.get(KW.BUTTONS.value, []):
            if KW.REPEAT.value not in b and b.get(KW.VIEW.value, "") == DECK_FEEDBACK.IMAGE.value and b.get(DECK_FEEDBACK.IMAGE.value) is not None:
                n = b.get(KW.NAME.value)
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
        return self._buttons.get(index)

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
                self._buttons.values(),
            )
            return set(reduce(lambda l, b: l.union(set(b.valid_indices())), with_image, set()))
        # else, returns all of them
        return list(self._buttons.keys())

    def valid_activations(self, index):
        b = self.get_button_definition(index)
        if b is not None:
            if index == "e4":
                print(index, b.actions, b.valid_activations())
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
        for what,value in query.items():
            for button in self[KW.BUTTONS.value]:
                if what == KW.ACTION.value:
                    if value in button[what]:
                        res.append(button)
                elif what == KW.VIEW.value:
                    if value in button[what]:
                        res.append(button)
        # loggerDeckType.debug(f"filter {query} returns {res}")
        return res
