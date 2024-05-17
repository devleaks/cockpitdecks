""" Virtual Deck Manager.

Discover, start, and stop virtual decks
"""

import os
import glob
import logging
import pyglet
from typing import List, Dict

from cockpitdecks.constant import CONFIG_FOLDER, CONFIG_FILE, EXCLUDE_DECKS, RESOURCES_FOLDER, CONFIG_KW, DECKS_FOLDER, DECK_KW, VIRTUAL_DECK_DRIVER, Config

from .virtualdeck import VirtualDeck
from .decktype import DeckType

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


class VirtualDeckManager:
    virtual_decks = {}

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
                vd[name] = dt
        return vd

    @staticmethod
    def enumerate(acpath: str) -> List[VirtualDeck]:
        vdt = VirtualDeckManager.virtual_deck_types()
        vdt_names = [d.get(DECK_KW.TYPE.value) for d in vdt.values()]
        fn = os.path.join(acpath, CONFIG_FOLDER, CONFIG_FILE)
        config = Config(fn)
        decks = config.get(CONFIG_KW.DECKS.value)
        for deck in decks:
            dt = deck.get(CONFIG_KW.TYPE.value)
            if dt in vdt_names:
                name = deck.get(DECK_KW.NAME.value)
                VirtualDeckManager.virtual_decks[name] = VirtualDeck(name=name, definition=vdt.get(dt), config=deck)
        return VirtualDeckManager.virtual_decks

    def __init__(self):
        self.event_loop = pyglet.app.EventLoop()

    def add(self, deck):
        VirtualDeckManager.virtual_decks[deck.name] = deck

    def start(self):
        self.event_loop.run(interval=0.5)

    def stop(self):
        self.event_loop.exit()
