"""
Virtual deck cockpitdeck interface class
Does not perform any action. Just a wrapper for
"""

import threading
import socket
import struct
import logging

from PIL import Image

from cockpitdecks.constant import DECK_KW

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


DEVICE_MANUFACTURER = "Cockpitdecks"  # verbose descriptive


class VirtualDeck:
    DECK_NAME = "virtualdeck"

    def __init__(self, name: str, definition: dict, config: dict, cdip: list):
        self.name: str = name
        self.virtual_deck_definition: dict = definition  # DeckType
        self.virtual_deck_config: dict = config  # Deck entry in deckconfig/config.yaml

        self.address = self.virtual_deck_config.get("address")
        self.port = self.virtual_deck_config.get("port")
        self.cd_address = cdip[0]
        self.cd_port = cdip[1]

        layout = self.virtual_deck_definition.get(DECK_KW.LAYOUT.value, [3, 2, 128])
        self.keys_horiz = layout[0]
        self.keys_vert = layout[1]
        self.icon_width = layout[2]
        self.icon_height = layout[2]

    def deck_type(self):
        return VirtualDeck.DECK_NAME

    def get_serial_number(self):
        return f"{self.address}:{self.port}"

    def is_visual(self):
        return True

    def key_image_format(self):
        return {
            "size": (self.icon_width, self.icon_height),
            "format": "",
            "flip": (False, False),
            "rotation": 0,
        }

    # #########################################
    #
    def open(self):
        pass

    def close(self):
        pass

    def reset(self):
        pass
