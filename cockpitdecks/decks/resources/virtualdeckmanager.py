""" Virtual Deck Manager.

Discover, start, and stop virtual decks
"""

import os
import glob
import logging
from typing import List, Dict

from cockpitdecks.constant import CONFIG_FOLDER, CONFIG_FILE, EXCLUDE_DECKS, RESOURCES_FOLDER, CONFIG_KW, DECKS_FOLDER, DECK_KW, VIRTUAL_DECK_DRIVER, Config

from .virtualdeck import VirtualDeck
from .decktype import DeckType

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


class VirtualDeckManager:
    virtual_decks: Dict[str, VirtualDeck] = {}

    @staticmethod
    def virtual_deck_types() -> Dict[str, DeckType]:
        deck_types = [DeckType(deck_type) for deck_type in glob.glob(os.path.join(os.path.dirname(__file__), "*.yaml"))]
        virtual_deck_types = filter(lambda d: d.is_virtual_deck(), deck_types)
        return {d.name: d for d in virtual_deck_types}

    @staticmethod
    def enumerate(acpath: str, cdip: list) -> Dict[str, VirtualDeck]:
        virtual_deck_types = VirtualDeckManager.virtual_deck_types()
        fn = os.path.join(acpath, CONFIG_FOLDER, CONFIG_FILE)
        config = Config(fn)
        decks = config.get(CONFIG_KW.DECKS.value, {})
        for deck in decks:
            deck_type = deck.get(CONFIG_KW.TYPE.value)
            if deck_type in virtual_deck_types:
                name = deck.get(DECK_KW.NAME.value)
                VirtualDeckManager.virtual_decks[name] = VirtualDeck(name=name, definition=virtual_deck_types.get(deck_type), config=deck, cdip=cdip)
        return VirtualDeckManager.virtual_decks
