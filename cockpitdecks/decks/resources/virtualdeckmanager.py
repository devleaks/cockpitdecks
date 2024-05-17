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
    virtual_decks: List[VirtualDeck] = {}

    @staticmethod
    def virtual_deck_types() -> Dict[str, DeckType]:
        vd = {}
        for deck_type in glob.glob(os.path.join(os.path.dirname(__file__), "*.yaml")):
            dt = DeckType(deck_type)
            driver = dt.get(DECK_KW.DRIVER.value)
            if driver == VIRTUAL_DECK_DRIVER:
                name = dt.get(DECK_KW.TYPE.value)
                if name is None:
                    logger.warning(f"ignoring unnamed deck type {deck_type}")
                    continue
                if not dt.validate_virtual_deck():
                    logger.warning(f"invalid deck type {deck_type}")
                    continue
                vd[name] = dt
        return vd

    @staticmethod
    def enumerate(acpath: str, cdip: list) -> List[VirtualDeck]:
        vdt = VirtualDeckManager.virtual_deck_types()
        vdt_names = [d.get(DECK_KW.TYPE.value) for d in vdt.values()]
        fn = os.path.join(acpath, CONFIG_FOLDER, CONFIG_FILE)
        config = Config(fn)
        decks = config.get(CONFIG_KW.DECKS.value)
        for deck in decks:
            dt = deck.get(CONFIG_KW.TYPE.value)
            if dt in vdt_names:
                name = deck.get(DECK_KW.NAME.value)
                VirtualDeckManager.virtual_decks[name] = VirtualDeck(name=name, definition=vdt.get(dt), config=deck, cdip=cdip)
        return VirtualDeckManager.virtual_decks
