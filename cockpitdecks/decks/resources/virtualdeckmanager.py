""" Virtual Deck Manager.

Discover virtual web decks
"""

import os
from typing import Dict

from cockpitdecks.constant import (
    CONFIG_FOLDER,
    CONFIG_FILE,
    SECRET_FILE,
    CONFIG_KW,
    DECK_KW,
    Config,
)

from .virtualdeck import VirtualDeck
from .decktype import DeckType


class VirtualDeckManager:
    virtual_decks: Dict[str, VirtualDeck] = {}

    @staticmethod
    def virtual_deck_types() -> Dict[str, DeckType]:
        """Returns the list of virtual deck types.

        Returns:
            Dict[str, DeckType]: [description]
        """
        deck_types = [DeckType(filename=deck_type) for deck_type in DeckType.list()]
        virtual_deck_types = filter(lambda d: d.is_virtual_deck(), deck_types)
        return {d.name: d for d in virtual_deck_types}

    @staticmethod
    def enumerate(acpath: str) -> Dict[str, VirtualDeck]:
        """Returns all the virtual devices available to Cockpitdecks.

        Virtual devices are discovered in the cockpit currently in use.
        Therefore, it is necesary to supply the path to the cockpit configuration.
        At creation time, Virtual Decks require to know the IP addresse where they report their activity.
        """
        virtual_deck_types = VirtualDeckManager.virtual_deck_types()
        fn = os.path.join(acpath, CONFIG_FOLDER, CONFIG_FILE)
        config = Config(fn)
        fn = os.path.join(acpath, CONFIG_FOLDER, SECRET_FILE)
        serials = Config(fn)
        decks = config.get(CONFIG_KW.DECKS.value, {})
        for deck in decks:
            disabled = deck.get(CONFIG_KW.DISABLED.value, False)
            if disabled:
                continue
            deck_type = deck.get(CONFIG_KW.TYPE.value)
            if deck_type in virtual_deck_types:
                name = deck.get(DECK_KW.NAME.value)
                VirtualDeckManager.virtual_decks[name] = VirtualDeck(name=name, definition=virtual_deck_types.get(deck_type), config=deck)
                VirtualDeckManager.virtual_decks[name].set_serial_number(serials.get(name))
        return VirtualDeckManager.virtual_decks
