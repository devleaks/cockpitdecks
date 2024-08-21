import logging

from PIL import Image

from cockpitdecks import DECK_KW
from cockpitdecks.resources.color import TRANSPARENT_PNG_COLOR
from .icon import IconBase

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


class Mosaic(IconBase):
    """A Mosaic is an icon that is split into several smaller icon"""

    REPRESENTATION_NAME = "mosaic"

    PARAMETERS = {}

    def __init__(self, button: "Button"):
        IconBase.__init__(self, button=button)
        self.mosaic = self._representation_config
        self.tiles = {}

        self.load_tiles()  # need to delay init2 after Icon is inited().

    def load_tiles(self):
        # make buttons!
        buttons = self.mosaic.get(DECK_KW.TILES.value)
        if buttons is not None:
            pseudo_deck_type = self.button._def.mosaic
            if pseudo_deck_type is not None:
                self.tiles = self.button.page.load_buttons(buttons=buttons, deck_type=pseudo_deck_type)
                logger.debug(f"load_tiles: loaded tiles {', '.join([t.name for t in self.tiles])}")
            else:
                logger.warning(f"{self.button.name}: no mosaic definition, not button loaded")
        else:
            logger.warning(f"{self.button.name}: no tile buttons")

    def place_tile(self, tile, image):
        dimensions = tile._def.display_size()
        portion = tile.get_representation()
        if portion is None:
            logger.warning(f"mosaic: tile {tile.name} has no image")
            return
        portion = portion.resize(dimensions)
        position = tile._def.get_offset()
        dest = (position[0], position[1], position[0] + dimensions[0], position[1] + dimensions[1])
        logger.debug(f"place_tile: {self.button.name}, {image.size}, {tile.name}, {dimensions}, {position}, {dest}")
        image.paste(portion, dest, portion)

    def render(self):
        # Warning: Do not update Mosaic too often because it may lead to performance issue:
        # Recall that a mosaic update request the update of all underlying tiles.
        # Make sure individual tiles DO cache their representation to speed up process.
        # IF all "but one" representation is invalid and all other are cached, there is no problem.
        # The overhead here, to paste together all tiles is negligible.
        # But the building of each individual tile is not.

        image = self.button.deck.create_icon_for_key(self.button.index, colors=self.cockpit_color, texture=self.cockpit_texture)
        for tile in self.tiles:
            self.place_tile(tile, image)
        return image
