"""
Virtual deck cockpitdeck interface class
Does not perform any action. Just a wrapper for Cockpitdecks.
Behaves like a "device driver".
"""

from .decktype import DeckType


class VirtualDeck:

    DECK_NAME = "virtualdeck"
    VERSION = "1.0.0"

    def __init__(self, name: str, definition: DeckType, config: dict):
        self.name: str = name
        self.virtual_deck_definition: DeckType = definition  # DeckType
        self.virtual_deck_config: dict = config  # Deck entry in deckconfig/config.yaml
        self.serial_number = None

    def deck_type(self):
        return VirtualDeck.DECK_NAME

    def set_serial_number(self, serial):
        self.serial_number = serial

    def get_serial_number(self):
        return self.serial_number if self.serial_number is not None else f"serial#{self.name.replace(' ', '-')}"

    # #########################################
    #
    def open(self):
        pass

    def close(self):
        pass

    def reset(self):
        pass
