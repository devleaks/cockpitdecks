import logging

from PIL import Image

from cockpitdecks import DECK_KW
from cockpitdecks.resources.color import TRANSPARENT_PNG_COLOR
from .icon import Icon

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


class Mosaic(Icon):
    """A Mosaic is an icon that is split into several smaller icon"""

    REPRESENTATION_NAME = "mosaic"

    PARAMETERS = {}

    def __init__(self, button: "Button"):
        Icon.__init__(self, button=button)
        self.mosaic = self._config.get(self.REPRESENTATION_NAME, {})
        self.tiles = {}

        self.init2()

    def init2(self):
        # make buttons!
        buttons = self.mosaic.get(DECK_KW.TILES.value)
        if buttons is not None:
            pseudo_deck_type = self.button._def.mosaic
            self.tiles = self.button.page.load_buttons(buttons=buttons, deck_type=pseudo_deck_type)

    def get_background(self):
        size = self.button._def.display_size()
        return Image.new(mode="RGBA", size=size, color=TRANSPARENT_PNG_COLOR)

    def place_tile(self, tile, image):
        dimensions = tile._def.display_size()
        portion = tile.get_representation()
        portion.resize(dimensions)
        position = tile._def.get_offset()
        dest = (position[0], position[1], position[0] + dimensions[0], position[1] + dimensions[1])
        image.paste(portion, dest, portion)

    def render(self):
        image = self.get_background()
        for tile in self.tiles:
            self.place_tile(tile, image)
        return image
