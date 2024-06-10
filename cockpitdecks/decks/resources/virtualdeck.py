"""
Virtual deck cockpitdeck interface class
Does not perform any action. Just a wrapper for
"""

import logging
import struct
import socket

from cockpitdecks.constant import CONFIG_KW

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


class VirtualDeck:
    DECK_NAME = "virtualdeck"

    def __init__(self, name: str, definition: "DeckType", config: dict, cdip: list):
        self.name: str = name
        self.virtual_deck_definition: dict = definition  # DeckType
        self.virtual_deck_config: dict = config  # Deck entry in deckconfig/config.yaml

        self.serial_number = None
        self.cd_address = cdip[0]
        self.cd_port = cdip[1]

        layout = self.virtual_deck_definition.get_virtual_deck_layout()
        self.keys_horiz = layout.get("h")
        self.keys_vert = layout.get("v")
        self.icon_width = layout.get("s")
        self.icon_height = layout.get("s")

    def deck_type(self):
        return VirtualDeck.DECK_NAME

    def set_serial_number(self, serial):
        self.serial_number = serial

    def get_serial_number(self):
        return self.serial_number

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
