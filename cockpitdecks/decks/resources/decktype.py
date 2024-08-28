import os
import logging
import json
import glob
import posixpath
from typing import List, Dict, Tuple

from py3rtree import RTree, Rect
from PIL import Image

from cockpitdecks import DECK_KW, Config, DECK_ACTIONS, DECK_FEEDBACK
from cockpitdecks import DECKS_FOLDER, RESOURCES_FOLDER, TYPES_FOLDER
from cockpitdecks.button import Button
from cockpitdecks.buttons.activation import get_activations_for
from cockpitdecks.buttons.activation.activation import Activation
from cockpitdecks.buttons.representation import get_representations_for
from cockpitdecks.buttons.representation.representation import Representation
from cockpitdecks import ICON_SIZE, VIRTUAL_DECK_DRIVER

loggerButtonType = logging.getLogger("ButtonType")
# loggerButtonType.setLevel(logging.DEBUG)

loggerDeckType = logging.getLogger("DeckType")
# loggerDeckType.setLevel(logging.DEBUG)


class DeckButton:
    """Defines a button on a deck, its capabilities, its representation.

    For web decks, adds position and sizes information.
    """

    def __init__(self, config: dict, button_block: dict) -> None:
        self._config = config
        self._button_block = button_block
        self._inited = False

        self.name = config.get(DECK_KW.NAME.value, config.get(DECK_KW.INT_NAME.value))

        self.index = config.get(DECK_KW.INDEX.value)
        self.prefix = config.get(DECK_KW.PREFIX.value, "")

        self.actions = config.get(DECK_KW.ACTION.value, "")
        self.feedbacks = config.get(DECK_KW.FEEDBACK.value, "")

        self.position = config.get(DECK_KW.POSITION.value)  # for web decks drawing
        self.dimension = config.get(DECK_KW.DIMENSION.value)

        self.options = config.get(DECK_KW.OPTIONS.value)

        self.handle = config.get(DECK_KW.HANDLE.value, [0, 0])  # for sliders
        self.range = config.get(DECK_KW.RANGE.value, [0, 0])  # for sliders

        self.layout: dict | None = config.get(DECK_KW.LAYOUT.value)

        self.hardware_representation: dict | None = None
        if self.layout is not None:
            self.hardware_representation = self.layout.get(DECK_KW.HARDWARE_REPRESENTATION.value)

        self.mosaic = None
        self._tile = False
        mosaic = config.get(DECK_KW.MOSAIC.value)
        if mosaic is not None:
            self.mosaic = DeckTypeBase(config={"name": "mosaic", "driver": "virtualdeck", "buttons": mosaic})
            # Mark all mosaic buttons as tile of this mosaic
            self.mosaic._parent_deck = self
            for b in self.mosaic.buttons.values():
                b._tile = True

        self.init()

    def init(self):
        if self._inited:
            return
        if self.actions is None or (type(self.actions) is str and self.actions.lower() == DECK_KW.NONE.value):
            self.actions = []
        elif type(self.actions) not in [list, tuple]:
            self.actions = [self.actions]

        if self.feedbacks is None or (type(self.feedbacks) is str and self.feedbacks.lower() == DECK_KW.NONE.value):
            self.feedbacks = []
        elif type(self.feedbacks) not in [list, tuple]:
            self.feedbacks = [self.feedbacks]

        self._name_is_int = True
        try:
            dummy = int(self.name)
        except ValueError:
            self._name_is_int = False

        # rearrange options
        # options: a=2,b -> options: {"a":2, b:True}
        options_new = {}
        if self.options is not None:
            for opt in self.options.split(","):
                opt_arr = opt.split("=")
                if len(opt_arr) > 1:
                    options_new[opt_arr[0]] = "=".join(opt_arr[1:])
                else:
                    options_new[opt_arr[0]] = True
        self.options = options_new

        loggerButtonType.debug(f"{self.prefix}/{self.name}: {self.valid_representations()}")
        self._inited = True

    def get_option(self, option):
        return self.options.get(option)

    def set_block_wallpaper(self, wallpaper):
        # wallpaper is full path
        self._button_block["wallpaper"] = wallpaper

    def resized_wallpaper(self):
        # build it on first call, cache it for after
        bb = self._button_block
        if "resized-wallpaper" not in bb:
            if "wallpaper-image" not in bb:
                bb["wallpaper-image"] = Image.open(bb["wallpaper"])
            r1 = bb["wallpaper-image"].width / bb["wallpaper-image"].height
            r2 = bb["block-size"][0] / bb["block-size"][1]
            if round(r1, 1) != round(r2, 1):
                loggerButtonType.warning(f"wallpaper aspect ratio differ ({r1}/{r2}, {bb['wallpaper-image'].size}/{bb['block-size']})")
            bb["resized-wallpaper"] = bb["wallpaper-image"].resize(bb["block-size"])
        return bb["resized-wallpaper"]

    def has_wallpaper(self) -> bool:
        return "wallpaper" in self._button_block and self._button_block["wallpaper"] is not None

    def get_wallpaper(self) -> bool:
        if not self.has_wallpaper():
            return None
        wallpaper = self.resized_wallpaper()
        if wallpaper is None:
            loggerButtonType.warning(f"no wallpaper")
        portion = self.get_corners()
        if portion is None:
            loggerButtonType.warning(f"no corners")
        return wallpaper.crop(portion)

    def has_drawing(self):
        return self.position is not None and self.dimension is not None

    def has_hardware_representation(self):
        return self.hardware_representation is not None and len(self.hardware_representation) > 0

    def get_hardware_representation(self):
        if self.has_hardware_representation():
            return self.hardware_representation.get("type")
        return None

    def has_icon(self) -> bool:
        return self.has_feedback(DECK_FEEDBACK.IMAGE.value) and self.dimension is not None

    def has_layout(self) -> bool:
        return self._config.get(DECK_KW.LAYOUT.value) is not None

    def is_encoder(self) -> bool:
        return self.has_action("encoder")

    def is_mosaic(self) -> bool:
        return self.mosaic is not None

    def is_tile(self) -> bool:
        return self._tile

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
        return (DECK_KW.NONE.value in self.feedbacks and len(self.feedbacks) == 1) or len(self.feedbacks) == 0

    def can_activate(self, activation: str) -> bool:
        return activation in self.valid_activations()

    def can_represent(self, representation: str) -> bool:
        return representation in self.valid_representations()

    def display_size(self) -> Tuple[int, int] | None:
        """Parses info from resources.decks.*.yaml"""
        if self.has_feedback(DECK_FEEDBACK.IMAGE.value) and self.dimension is not None:
            return (2 * self.dimension, 2 * self.dimension) if type(self.dimension) is int else self.dimension
        return None

    def get_offset(self, return_offset: bool = False) -> Tuple[int, int] | None:
        """Parses info from resources.decks.*.yaml"""
        if self.has_feedback(DECK_FEEDBACK.IMAGE.value) and self.dimension is not None:
            return self.position
        return None

    def get_drawing_size(self, length: int = ICON_SIZE) -> Tuple[int, int] | None:
        sizes = self.display_size()
        if sizes is not None:
            lmin = min(sizes)
            return (int(length * sizes[0] / lmin), int(length * sizes[1] / lmin))
        return None

    def get_corners(self):
        # (left, bottom, right, top)
        sizes = self.display_size()
        if sizes is None:
            loggerButtonType.debug(f"{self.name}: no size")
            return None
        return (self.position[0], self.position[1], self.position[0] + sizes[0], self.position[1] + sizes[1])

    def desc(self):
        """Returns a flattened description of the button

        Ready to be used by web deck

        Returns:
            dict: ButtonDeck description, simply flattened for web decks
        """
        return {  # @todo: should add only if not null
            "name": self.name,
            "index": self.index,
            "prefix": self.prefix,
            "actions": self.actions,
            "feedbacks": self.feedbacks,
            "range": self.range,
            "handle": self.handle,
            "position": self.position,
            "dimension": self.dimension,
            "layout": self.layout,
            "options": self.options,
            "mosaic": self.mosaic.desc() if self.mosaic is not None else None,
            "tile": self._tile,
        }


DECK_TYPE_LOCATION = os.path.join(os.path.dirname(__file__), TYPES_FOLDER)
DECK_TYPE_GLOB = "*.yaml"


class DeckTypeBase:
    """Description of a deck capabilities, including its representation for web decks

    Reads and parse deck template file"""

    def __init__(self, config: dict) -> None:
        self._config = config
        self.name = self._config.get(DECK_KW.NAME.value)
        self.driver = self._config.get(DECK_KW.DRIVER.value)
        self.buttons: Dict[str | int, DeckButton] = {}
        self.background = self._config.get(DECK_KW.BACKGROUND.value)
        self._special_displays = None  # cache
        self._map = None  # display layout (RTree)
        self.count = 0
        self._aircraft = False
        self._parent_deck = None
        self.init()

    @staticmethod
    def list(path: str = DECK_TYPE_LOCATION):
        return glob.glob(os.path.join(path, DECK_TYPE_GLOB))

    @property
    def store(self):
        return self._config

    def init(self):
        """Parses a deck definition file and build a list of what's available.

        Mainly a list of buttons, what can be done with each (action), and what the
        button can provide as a feedback.
        """
        cnt = 0
        for button_block in self._config[DECK_KW.BUTTONS.value]:
            self.buttons = self.buttons | self.parse_deck_button_block(button_block=button_block)
        loggerDeckType.debug(f"deck type {self.name}: buttons: {self.buttons.keys()}..")
        loggerDeckType.debug(f"..deck type {self.name} done")

        # with open(self.name+".json", "w") as fd:
        #     json.dump(self.desc(), fd, indent=2)

    def parse_deck_button_block(self, button_block) -> Dict[str | int, DeckButton]:
        """Parses a deck button definition block

        A DeckButton block defines either a single deck button (no repeat attribute)
        or a collection of similar buttons if there is a repeat attribute.
        """
        button_block[DECK_KW.INT_NAME.value] = "NO_NAME_" + str(self.count)  # assign technical name
        self.count = self.count + 1

        repeat = button_block.get(DECK_KW.REPEAT.value)
        if type(repeat) is int:
            repeat = [repeat, 1]
        layout = button_block.get(DECK_KW.LAYOUT.value)
        offset = [0, 0]
        spacing = [0, 0]
        if layout is not None:
            offset = layout.get(DECK_KW.OFFSET.value, [0, 0])
            spacing = layout.get(DECK_KW.SPACING.value, [0, 0])
        prefix = button_block.get(DECK_KW.PREFIX.value, "")
        start = button_block.get(DECK_KW.NAME.value)

        # this definition is for a single button
        if repeat is None or repeat == [1, 1]:
            name = f"{prefix}{start}"
            return {
                name: DeckButton(
                    config={
                        DECK_KW.NAME.value: name,
                        DECK_KW.INDEX.value: start,
                        DECK_KW.PREFIX.value: button_block.get(DECK_KW.PREFIX.value),
                        DECK_KW.RANGE.value: button_block.get(DECK_KW.RANGE.value),
                        DECK_KW.HANDLE.value: button_block.get(DECK_KW.HANDLE.value),
                        DECK_KW.ACTION.value: button_block.get(DECK_KW.ACTION.value),
                        DECK_KW.FEEDBACK.value: button_block.get(DECK_KW.FEEDBACK.value),
                        DECK_KW.POSITION.value: offset,
                        DECK_KW.DIMENSION.value: button_block.get(DECK_KW.DIMENSION.value, [0, 0]),
                        DECK_KW.LAYOUT.value: button_block.get(DECK_KW.LAYOUT.value),
                        DECK_KW.MOSAIC.value: button_block.get(DECK_KW.MOSAIC.value),
                        DECK_KW.OPTIONS.value: button_block.get(DECK_KW.OPTIONS.value),
                    },
                    button_block=button_block
                )
            }

        # definition is a for a collection of similar buttons
        start = int(start)  # should be int, but no test
        button_types = {}
        idx = start
        last = None
        for y in range(repeat[1]): # top to bottom
            for x in range(repeat[0]): # left to right
                name = f"{prefix}{idx}"
                sizes = button_block.get(DECK_KW.DIMENSION.value)
                if sizes is None:
                    sizes = [0, 0]
                if type(sizes) is int:  # radius
                    sizes = [2 * sizes, 2 * sizes]  # "bounding box"
                position = [0, 0]
                position[0] = offset[0] + x * (sizes[0] + spacing[0])
                position[1] = offset[1] + y * (sizes[1] + spacing[1])
                button_types[name] = DeckButton(
                    config={
                        DECK_KW.NAME.value: name,
                        DECK_KW.INDEX.value: idx,
                        DECK_KW.PREFIX.value: button_block.get(DECK_KW.PREFIX.value),
                        DECK_KW.RANGE.value: button_block.get(DECK_KW.RANGE.value),
                        DECK_KW.HANDLE.value: button_block.get(DECK_KW.HANDLE.value),
                        DECK_KW.ACTION.value: button_block.get(DECK_KW.ACTION.value),
                        DECK_KW.FEEDBACK.value: button_block.get(DECK_KW.FEEDBACK.value),
                        DECK_KW.POSITION.value: position,
                        DECK_KW.DIMENSION.value: button_block.get(DECK_KW.DIMENSION.value),
                        DECK_KW.LAYOUT.value: button_block.get(DECK_KW.LAYOUT.value),
                        DECK_KW.MOSAIC.value: button_block.get(DECK_KW.MOSAIC.value),
                        DECK_KW.OPTIONS.value: button_block.get(DECK_KW.OPTIONS.value),
                    },
                    button_block=button_block
                )
                idx = idx + 1
                last = button_types[name]

        corners = last.get_corners()
        if corners is not None:
            button_block["block-size"] = corners[2:]
            loggerDeckType.info(f"{self.driver}: {self.name}: {last.name}: screen size {corners[2:]}")

        return button_types

    def is_virtual_deck(self) -> bool:
        """Validate consistency between virtual deck parameters.

        Virtual decks need to provide additional information (like layout).
        We check for consistency between layout (used by user interface to create deck)
        and information for Cockpitdecks.

        Returns:
            bool: Virtual deck definition is consistent or not
        """
        return self.driver == VIRTUAL_DECK_DRIVER

    def get_virtual_deck_layout(self):
        if self.is_virtual_deck():
            return self.desc()
        return {}

    def special_displays(self):
        """Returns name of all special displays (i.e. not "keys")"""
        # Empirical, need better handling
        if self._special_displays is not None:
            return self._special_displays
        self._special_displays = []
        for b in self._config.get(DECK_KW.BUTTONS.value, []):
            if DECK_KW.REPEAT.value not in b and DECK_FEEDBACK.IMAGE.value in b.get(DECK_KW.FEEDBACK.value, "") and b.get(DECK_KW.DIMENSION.value) is not None:
                n = b.get(DECK_KW.NAME.value)
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
        # 1. search in all mosaic first...
        for b in self.buttons.values():
            if b.is_mosaic():
                if index in b.mosaic.valid_indices():
                    loggerDeckType.debug(f"returning index {index} for {self.name} from mosaic")
                    return b.mosaic.get_button_definition(index)
        return self.buttons.get(index)

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
                lambda x: x.has_icon(),
                self.buttons.values(),
            )
            return [b.name for b in with_image]
        # else, returns all of them
        return list(self.buttons.keys())

    def valid_activations(self, index):
        b = self.get_button_definition(index)
        if b is not None:
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

    def display_size(self, index):
        b = self.get_button_definition(index)
        if b is not None:
            return b.display_size()
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
        for what, value in query.items():
            for button in self._config[DECK_KW.BUTTONS.value]:
                if what == DECK_KW.ACTION.value:
                    if what in button and value in button[what]:
                        res.append(button)
                elif what in button and what == DECK_KW.FEEDBACK.value:
                    if value in button[what]:
                        res.append(button)
        # loggerDeckType.debug(f"filter {query} returns {res}")
        return res

    def desc(self):
        """Returns a flattened description of the deck

        Ready to be used by web deck

        Returns:
            dict: Deck description (DeckType), simply flattened for web decks
        """
        buttons = [b.desc() for b in self.buttons.values()]
        return {"name": self.name, "driver": self.driver, "background": self.background, "aircraft": self._aircraft, "buttons": buttons}

    def get_button(self, x: int, y: int) -> DeckButton | None:
        # Don't force it. Use a bigger hammer. (/usr/bin/fortune, circa 1980, a motto of mine.)
        if self._map is None:
            # make map
            self._map = RTree()
            for b in self.buttons.values():
                self._map.insert(b, Rect(*b.get_corners()))
                # print("map>", b.name, b.get_corners())
        real_point_res = [r.leaf_obj() for r in self._map.query_point((x, y)) if r.is_leaf()]
        # print("query>", (x, y), [b.name for b in real_point_res])
        if len(real_point_res) > 1:
            loggerDeckType.warning(f"touched more than one button ({len(real_point_res)}), returning first button only")
        return real_point_res[0] if len(real_point_res) > 0 else None


class DeckType(DeckTypeBase):
    """Description of a deck capabilities, including its representation for web decks

    Reads and parse deck template file"""

    def __init__(self, filename: str) -> None:
        file = Config(filename=filename)
        DeckTypeBase.__init__(self, config=file.store)

    def get(self, what: str):
        return self._config.get(what)
